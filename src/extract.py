import time
import pandas as pd
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
    "USD/ARS": {"category": "fx", "unit": "ARS (Oficial)", "is_rate": False},
    "DXY": {"category": "fx", "unit": "Índice", "is_rate": False},
    "WTI Oil": {"category": "commodity", "unit": "USD/bbl", "is_rate": False},
    "Gold": {"category": "commodity", "unit": "USD/oz", "is_rate": False},
    "US 10Y Yield": {"category": "rate", "unit": "% anual", "is_rate": True},
}

RATE_ASSETS = {name for name, meta in ASSET_METADATA.items() if meta["is_rate"]}
FX_ASSETS = [name for name, meta in ASSET_METADATA.items() if meta["category"] == "fx"]
COMMODITY_ASSETS = [name for name, meta in ASSET_METADATA.items() if meta["category"] == "commodity"]


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


def fetch_macro_bundle(period: str = "1y", retries: int = 2) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Download daily closes and return (filled_df, raw_close_df)."""
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
            filled_df = raw_close.ffill().dropna()
            if len(filled_df) < 2:
                raise ValueError("Se necesitan al menos 2 ruedas válidas para calcular variaciones.")
            return filled_df, raw_close
        except Exception as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Error al descargar datos desde Yahoo Finance: {last_error}") from last_error


def fetch_macro_data(period: str = "1y") -> pd.DataFrame:
    """Backward-compatible helper returning the aligned daily close DataFrame."""
    filled_df, _ = fetch_macro_bundle(period=period)
    return filled_df