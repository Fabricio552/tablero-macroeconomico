import time
import pandas as pd
import requests
import yfinance as yf

TICKERS = {
    "USD/UYU": "UYU=X",
    "USD/BRL": "BRL=X",
    "USD/ARS": "ARS=X",
    "US 10Y Yield": "^TNX",
    "WTI Oil": "CL=F",
    "Gold": "GC=F",
    "DXY": "DX-Y.NYB",
}

ASSET_METADATA = {
    "USD/UYU": {"category": "fx", "unit": "UYU", "is_rate": False},
    "USD/BRL": {"category": "fx", "unit": "BRL", "is_rate": False},
    "BRL/UYU": {"category": "fx", "unit": "UYU/BRL", "is_rate": False},
    "USD/ARS": {"category": "fx", "unit": "ARS (Oficial)", "is_rate": False},
    "UI (BCU)": {"category": "index", "unit": "UYU/UI", "is_rate": False},
    "DXY": {"category": "fx", "unit": "Índice", "is_rate": False},
    "WTI Oil": {"category": "commodity", "unit": "USD/bbl", "is_rate": False},
    "Gold": {"category": "commodity", "unit": "USD/oz", "is_rate": False},
    "US 10Y Yield": {"category": "rate", "unit": "% anual", "is_rate": True},
}

RATE_ASSETS = {name for name, meta in ASSET_METADATA.items() if meta["is_rate"]}
NON_MARKET_CORR_ASSETS = {"UI (BCU)"}
FX_ASSETS = ["USD/UYU", "USD/BRL", "BRL/UYU", "USD/ARS", "DXY"]
COMMODITY_ASSETS = ["WTI Oil", "Gold"]

DATOS_URUGUAY_ENDPOINTS = {
    "USD/UYU": ("https://datosuruguay.com/api/v1/exchange-rates/usd", 320),
    "UI (BCU)": ("https://datosuruguay.com/api/v1/indexed-units/ui", 450),
    "BRL/UYU": ("https://datosuruguay.com/api/v1/exchange-rates/brl", 320),
}


def _extract_close_frame(raw_data: pd.DataFrame) -> pd.DataFrame:
    """Normalize yfinance output into a clean Close DataFrame with readable columns."""
    if raw_data is None or raw_data.empty:
        raise ValueError("yfinance devolvió un DataFrame vacío.")

    if isinstance(raw_data.columns, pd.MultiIndex):
        if "Close" not in raw_data.columns.get_level_values(0):
            raise ValueError("La respuesta de yfinance no contiene la columna 'Close'.")
        close_df = raw_data["Close"].copy()
    elif "Close" in raw_data.columns:
        close_df = raw_data[["Close"]].copy()
        if len(TICKERS) == 1:
            only_name = next(iter(TICKERS.keys()))
            close_df.columns = [only_name]
    else:
        close_df = raw_data.copy()

    inv_tickers = {v: k for k, v in TICKERS.items()}
    close_df = close_df.rename(columns=inv_tickers)
    ordered_cols = [name for name in TICKERS if name in close_df.columns]
    if not ordered_cols:
        raise ValueError("No se encontró ninguno de los tickers esperados en los datos descargados.")

    close_df = close_df[ordered_cols].sort_index()
    close_df.columns.name = None
    close_df.index.name = "Date"
    return close_df.dropna(how="all")


def parse_datos_uruguay_series(payload: dict, name: str) -> pd.Series:
    """Parse datosUruguay REST JSON payload into a clean ascending Series."""
    records = payload.get("data", []) if isinstance(payload, dict) else []
    if not records:
        return pd.Series(dtype=float, name=name)

    df_tmp = pd.DataFrame(records)
    if "date" not in df_tmp.columns or "value" not in df_tmp.columns:
        return pd.Series(dtype=float, name=name)

    df_tmp["date"] = pd.to_datetime(df_tmp["date"], errors="coerce")
    df_tmp["value"] = pd.to_numeric(df_tmp["value"], errors="coerce")
    df_tmp = df_tmp.dropna(subset=["date", "value"]).sort_values("date")
    df_tmp = df_tmp.drop_duplicates(subset=["date"], keep="last")
    series = pd.Series(df_tmp["value"].to_numpy(dtype=float), index=df_tmp["date"], name=name)
    series.index.name = "Date"
    return series


def sanitize_isolated_spikes(series: pd.Series, pct_threshold: float = 0.10) -> pd.Series:
    """Remove non-positive values and isolated 1-day data-feed glitches that snap back immediately."""
    cleaned = series.where(series > 0).copy()
    valid = cleaned.dropna()
    if len(valid) < 3:
        return cleaned

    prev_vals = valid.shift(1)
    next_vals = valid.shift(-1)
    jump_in = (valid / prev_vals - 1.0).abs() > pct_threshold
    jump_out = (next_vals / valid - 1.0).abs() > pct_threshold
    reverts = ((valid - prev_vals) * (next_vals - valid)) < 0
    edge_drop = valid.isna()
    bad_idx = valid.index[jump_in & jump_out & reverts & (~edge_drop)]

    # Also catch an edge glitch on the very first point if it jumps >15% on day 2
    if len(valid) >= 2 and abs(valid.iloc[1] / valid.iloc[0] - 1.0) > 0.15:
        bad_idx = bad_idx.union(pd.Index([valid.index[0]]))

    if len(bad_idx) > 0:
        cleaned.loc[bad_idx] = pd.NA
    return cleaned


def fetch_bcu_series(url: str, name: str, limit: int = 350, timeout: int = 10) -> pd.Series:
    """Fetch an official BCU daily series via datosUruguay REST API (returns empty Series on failure)."""
    try:
        resp = requests.get(url, params={"limit": limit}, timeout=timeout)
        resp.raise_for_status()
        return parse_datos_uruguay_series(resp.json(), name=name)
    except Exception:
        return pd.Series(dtype=float, name=name)


def enrich_with_local_macro(
    raw_close: pd.DataFrame,
    bcu_fetcher=fetch_bcu_series,
) -> tuple[pd.DataFrame, dict[str, str]]:
    """Enrich Yahoo Finance close frame with official BCU USD/UYU, BRL/UYU, and UI series."""
    enriched = raw_close.copy()
    sources: dict[str, str] = {"market": "Yahoo Finance (yfinance)"}
    target_idx = enriched.index
    max_date = target_idx.max()

    # 1) USD/UYU: prefer official BCU closing rate (more reliable than Yahoo UYU=X), fallback to Yahoo
    usd_url, usd_limit = DATOS_URUGUAY_ENDPOINTS["USD/UYU"]
    usd_bcu = bcu_fetcher(usd_url, "USD/UYU", limit=usd_limit)
    if not usd_bcu.empty:
        usd_bcu = sanitize_isolated_spikes(usd_bcu[usd_bcu.index <= max_date])
        usd_aligned = usd_bcu.reindex(target_idx)
        if usd_aligned.notna().sum() >= max(int(len(target_idx) * 0.6), 20):
            enriched["USD/UYU"] = usd_aligned
            sources["usd_uyu"] = "BCU oficial (vía datosUruguay.com)"

    # 2) BRL/UYU: prefer sanitized BCU rate, fallback to Yahoo cross (USD/UYU / USD/BRL)
    brl_url, brl_limit = DATOS_URUGUAY_ENDPOINTS["BRL/UYU"]
    brl_bcu = bcu_fetcher(brl_url, "BRL/UYU", limit=brl_limit)
    if not brl_bcu.empty:
        brl_bcu = sanitize_isolated_spikes(brl_bcu[brl_bcu.index <= max_date])
        brl_aligned = brl_bcu.reindex(target_idx)
    else:
        brl_aligned = pd.Series(dtype=float)

    if brl_aligned.notna().sum() >= max(int(len(target_idx) * 0.6), 20):
        enriched["BRL/UYU"] = brl_aligned
        sources["brl_uyu"] = "BCU oficial (vía datosUruguay.com)"
    elif "USD/UYU" in enriched.columns and "USD/BRL" in enriched.columns:
        enriched["BRL/UYU"] = enriched["USD/UYU"] / enriched["USD/BRL"]
        sources["brl_uyu"] = "Cruce derivado USD/UYU ÷ USD/BRL (Yahoo)"

    # 3) UI (BCU): align up to latest market date (UI is forward-published)
    ui_url, ui_limit = DATOS_URUGUAY_ENDPOINTS["UI (BCU)"]
    ui_bcu = bcu_fetcher(ui_url, "UI (BCU)", limit=ui_limit)
    if not ui_bcu.empty:
        ui_clipped = ui_bcu[ui_bcu.index <= max_date]
        ui_aligned = ui_clipped.reindex(target_idx).ffill()
        if ui_aligned.notna().sum() >= 20:
            enriched["UI (BCU)"] = ui_aligned
            sources["ui_bcu"] = "BCU oficial (vía datosUruguay.com)"

    ordered = [col for col in ASSET_METADATA if col in enriched.columns]
    remaining = [col for col in enriched.columns if col not in ordered]
    enriched = enriched[ordered + remaining]
    enriched.columns.name = None
    return enriched, sources


def fetch_macro_bundle(period: str = "1y", retries: int = 2) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, str]]:
    """Download daily closes, enrich with Uruguay BCU data, and return (filled_df, raw_close_df, sources)."""
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            raw_download = yf.download(
                list(TICKERS.values()),
                period=period,
                interval="1d",
                progress=False,
                auto_adjust=False,
            )
            raw_close = _extract_close_frame(raw_download)
            raw_enriched, sources = enrich_with_local_macro(raw_close)
            filled_df = raw_enriched.ffill().dropna()
            if len(filled_df) < 2:
                raise ValueError("Se necesitan al menos 2 días hábiles válidos para calcular variaciones.")
            return filled_df, raw_enriched, sources
        except Exception as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Error al descargar datos macroeconómicos: {last_error}") from last_error


def fetch_macro_data(period: str = "1y") -> pd.DataFrame:
    """Backward-compatible helper returning the aligned daily close DataFrame."""
    filled_df, _, _ = fetch_macro_bundle(period=period)
    return filled_df