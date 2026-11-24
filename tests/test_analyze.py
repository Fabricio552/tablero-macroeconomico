import numpy as np
import pandas as pd
import pytest

from src.analyze import (
    compute_correlations,
    compute_summary_metrics,
    format_markdown_summary,
)
from src.extract import _extract_close_frame


def _sample_macro_df() -> pd.DataFrame:
    dates = pd.to_datetime(
        [
            "2025-12-30",
            "2025-12-31",
            "2026-01-02",
            "2026-01-05",
            "2026-01-06",
            "2026-01-07",
            "2026-01-08",
        ]
    )
    return pd.DataFrame(
        {
            "USD/UYU": [39.5, 40.0, 40.4, 40.8, 41.0, 41.5, 42.0],
            "USD/BRL": [5.5, 5.0, 5.1, 5.2, 5.3, 5.4, 5.5],
            "US 10Y Yield": [4.00, 4.10, 4.15, 4.20, 4.25, 4.30, 4.40],
        },
        index=dates,
    )


def test_compute_summary_metrics_uses_prior_year_ytd_and_bps_for_rates():
    df = _sample_macro_df()
    summary = compute_summary_metrics(df).set_index("Activo")

    # USD/UYU: latest=42.0 vs prev_1d=41.5 (+1.20%), prev_5d=40.0 (+5.00%), YTD vs 2025-12-31=40.0 (+5.00%)
    assert summary.loc["USD/UYU", "var_1d_num"] == pytest.approx(1.20, abs=0.01)
    assert summary.loc["USD/UYU", "var_5d_num"] == pytest.approx(5.00, abs=0.01)
    assert summary.loc["USD/UYU", "var_ytd_num"] == pytest.approx(5.00, abs=0.01)
    assert summary.loc["USD/UYU", "unit_delta"] == "%"
    assert summary.loc["USD/UYU", "pos_52w_pct"] == pytest.approx(100.0)

    # US 10Y Yield: latest=4.40 vs prev_1d=4.30 (+10.0 bps), YTD vs 2025-12-31=4.10 (+30.0 bps)
    assert summary.loc["US 10Y Yield", "var_1d_num"] == pytest.approx(10.0, abs=0.1)
    assert summary.loc["US 10Y Yield", "var_ytd_num"] == pytest.approx(30.0, abs=0.1)
    assert summary.loc["US 10Y Yield", "unit_delta"] == "bps"
    assert summary.loc["US 10Y Yield", "YTD"] == "+30.0 bps"


def test_format_markdown_summary_columns():
    df = _sample_macro_df()
    summary = compute_summary_metrics(df)
    table = format_markdown_summary(summary)
    assert list(table.columns) == [
        "Activo",
        "Unidad",
        "Último",
        "Var 1D",
        "Var 5D",
        "YTD",
        "1A",
        "Rango 52S",
    ]


def test_compute_correlations_skips_holiday_zero_returns_with_raw_df():
    dates = pd.date_range("2026-01-01", periods=6, freq="B")
    raw_df = pd.DataFrame(
        {
            "USD/UYU": [40.0, 40.4, 40.8, 41.2, 41.6, 42.0],
            "US 10Y Yield": [4.00, 4.10, np.nan, 4.30, 4.40, 4.50],
        },
        index=dates,
    )
    filled_df = raw_df.ffill()
    corr = compute_correlations(filled_df, window=10, raw_df=raw_df)

    assert corr.index.name is None
    assert corr.columns.name is None
    assert corr.loc["USD/UYU", "USD/UYU"] == pytest.approx(1.0)
    assert -1.0 <= corr.loc["USD/UYU", "US 10Y Yield"] <= 1.0


def test_extract_close_frame_clears_ticker_name_and_renames_columns():
    dates = pd.date_range("2026-01-02", periods=2, freq="B")
    cols = pd.MultiIndex.from_product([["Close"], ["UYU=X", "DX-Y.NYB"]], names=["Price", "Ticker"])
    raw = pd.DataFrame([[40.1, 102.5], [40.3, 103.0]], index=dates, columns=cols)

    cleaned = _extract_close_frame(raw)
    assert list(cleaned.columns) == ["USD/UYU", "DXY"]
    assert cleaned.columns.name is None


def test_validate_dataframe_rejects_empty_or_single_row():
    empty_df = pd.DataFrame()
    with pytest.raises(ValueError):
        compute_summary_metrics(empty_df)

    one_row = _sample_macro_df().iloc[:1]
    with pytest.raises(ValueError):
        compute_summary_metrics(one_row)
