import pandas as pd

try:
    from extract import ASSET_METADATA, RATE_ASSETS
except ImportError:
    from src.extract import ASSET_METADATA, RATE_ASSETS


def _validate_dataframe(df: pd.DataFrame, min_rows: int = 2) -> None:
    if df is None or df.empty:
        raise ValueError("El DataFrame de entrada está vacío.")
    if len(df) < min_rows:
        raise ValueError(f"Se requieren al menos {min_rows} filas; se recibieron {len(df)}.")


def _get_ytd_baseline(series: pd.Series, current_year: int) -> float:
    """Use the last close of the prior year as YTD baseline when available."""
    prior_year = series[series.index.year < current_year]
    if not prior_year.empty:
        return float(prior_year.iloc[-1])
    current_ytd = series[series.index.year == current_year]
    if not current_ytd.empty:
        return float(current_ytd.iloc[0])
    return float(series.iloc[0])


def _format_delta(value: float, unit_delta: str) -> str:
    if unit_delta == "bps":
        return f"{value:+.1f} bps"
    return f"{value:+.2f}%"


def compute_summary_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Compute 1D, 5D, YTD, 1Y variations (% for prices, bps for yields) and 52W range."""
    _validate_dataframe(df, min_rows=2)
    current_year = int(df.index.max().year)
    summary = []

    for col in df.columns:
        series = df[col].dropna()
        if len(series) < 2:
            continue

        meta = ASSET_METADATA.get(col, {"unit": "-", "is_rate": False})
        is_rate = col in RATE_ASSETS or bool(meta.get("is_rate", False))
        unit_delta = "bps" if is_rate else "%"

        latest = float(series.iloc[-1])
        prev_1d = float(series.iloc[-2])
        prev_5d = float(series.iloc[-6]) if len(series) >= 6 else float(series.iloc[0])
        start_ytd = _get_ytd_baseline(series, current_year)
        start_1y = float(series.iloc[0])

        low_52w = float(series.min())
        high_52w = float(series.max())
        pos_52w = ((latest - low_52w) / (high_52w - low_52w) * 100.0) if high_52w > low_52w else 50.0

        if is_rate:
            var_1d = round((latest - prev_1d) * 100.0, 1)
            var_5d = round((latest - prev_5d) * 100.0, 1)
            var_ytd = round((latest - start_ytd) * 100.0, 1)
            var_1y = round((latest - start_1y) * 100.0, 1)
        else:
            var_1d = round(((latest / prev_1d) - 1.0) * 100.0, 2)
            var_5d = round(((latest / prev_5d) - 1.0) * 100.0, 2)
            var_ytd = round(((latest / start_ytd) - 1.0) * 100.0, 2)
            var_1y = round(((latest / start_1y) - 1.0) * 100.0, 2)

        summary.append({
            "Activo": col,
            "Unidad": meta["unit"],
            "Último": round(latest, 2),
            "Var 1D": _format_delta(var_1d, unit_delta),
            "Var 5D": _format_delta(var_5d, unit_delta),
            "YTD": _format_delta(var_ytd, unit_delta),
            "1A": _format_delta(var_1y, unit_delta),
            "Rango 52S": f"{low_52w:.2f} – {high_52w:.2f} ({pos_52w:.0f}%)",
            "var_1d_num": var_1d,
            "var_5d_num": var_5d,
            "var_ytd_num": var_ytd,
            "var_1y_num": var_1y,
            "low_52w": round(low_52w, 2),
            "high_52w": round(high_52w, 2),
            "pos_52w_pct": round(pos_52w, 1),
            "is_rate": is_rate,
            "unit_delta": unit_delta,
        })

    return pd.DataFrame(summary)


def format_markdown_summary(summary_df: pd.DataFrame) -> pd.DataFrame:
    """Return display columns only for README markdown table rendering."""
    display_cols = ["Activo", "Unidad", "Último", "Var 1D", "Var 5D", "YTD", "1A", "Rango 52S"]
    return summary_df[display_cols].copy()


def compute_correlations(
    df: pd.DataFrame,
    window: int = 60,
    raw_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Compute pairwise correlation of daily moves (% returns for prices, diff for rates)."""
    _validate_dataframe(df, min_rows=3)
    source = raw_df if raw_df is not None else df
    changes = pd.DataFrame(index=source.index)

    for col in source.columns:
        valid = source[col].dropna()
        if col in RATE_ASSETS:
            series_changes = valid.diff()
        else:
            series_changes = valid.pct_change()
        changes[col] = series_changes.reindex(source.index)

    recent = changes.dropna(how="all").tail(window)
    corr = recent.corr().round(2)
    corr.index.name = None
    corr.columns.name = None
    return corr