import numpy as np
import pandas as pd
import pytest

from src.analyze import (
    compute_correlations,
    compute_summary_metrics,
    detect_alerts,
    generate_morning_brief,
    save_history_snapshot,
    send_optional_alerts,
)
from src.extract import (
    enrich_with_local_macro,
    parse_datos_uruguay_series,
    sanitize_isolated_spikes,
)


def test_sanitize_isolated_spikes_filters_single_day_glitches():
    dates = pd.date_range("2026-05-05", periods=5, freq="B")
    dirty = pd.Series([7.90, 7.92, 0.029, 7.95, 7.98], index=dates)
    cleaned = sanitize_isolated_spikes(dirty)
    assert pd.isna(cleaned.iloc[2])
    assert cleaned.ffill().iloc[2] == pytest.approx(7.92)


def test_parse_datos_uruguay_series_sorts_and_deduplicates():
    payload = {
        "data": [
            {"date": "2026-11-25", "value": 6.720},
            {"date": "2026-11-24", "value": 6.715},
            {"date": "2026-11-25", "value": 6.729},
        ]
    }
    series = parse_datos_uruguay_series(payload, name="UI (BCU)")
    assert list(series.index.strftime("%Y-%m-%d")) == ["2026-11-24", "2026-11-25"]
    assert series.iloc[-1] == pytest.approx(6.729)


def test_enrich_with_local_macro_uses_bcu_and_falls_back_to_cross():
    dates = pd.date_range("2026-01-02", periods=25, freq="B")
    raw_close = pd.DataFrame(
        {
            "USD/UYU": np.linspace(39.0, 40.5, 25),
            "USD/BRL": np.linspace(5.0, 5.5, 25),
        },
        index=dates,
    )

    def fake_bcu(url: str, name: str, limit: int = 350) -> pd.Series:
        if "ui" in url:
            return pd.Series(np.linspace(6.3, 6.7, 25), index=dates, name=name)
        return pd.Series(dtype=float, name=name)

    enriched, sources = enrich_with_local_macro(raw_close, bcu_fetcher=fake_bcu)
    assert "BRL/UYU" in enriched.columns
    assert "UI (BCU)" in enriched.columns
    assert "Cruce derivado" in sources["brl_uyu"]
    assert "BCU" in sources["ui_bcu"]
    assert enriched["BRL/UYU"].iloc[-1] == pytest.approx(40.5 / 5.5)


def test_correlations_exclude_non_market_ui_index():
    dates = pd.date_range("2026-01-02", periods=10, freq="B")
    df = pd.DataFrame(
        {
            "USD/UYU": [39.0, 39.2, 39.1, 39.4, 39.5, 39.8, 39.7, 40.0, 40.1, 40.5],
            "BRL/UYU": [7.1, 7.2, 7.15, 7.25, 7.3, 7.35, 7.32, 7.4, 7.45, 7.5],
            "UI (BCU)": np.linspace(6.4, 6.5, 10),
        },
        index=dates,
    )
    corr = compute_correlations(df, window=10)
    assert "UI (BCU)" not in corr.columns
    assert list(corr.columns) == ["USD/UYU", "BRL/UYU"]


def test_detect_alerts_and_morning_brief_identify_shock_and_52w_high():
    dates = pd.bdate_range("2025-12-20", periods=30)
    uyu = np.concatenate([np.full(28, 39.0), [39.02, 41.50]])
    ui = np.linspace(6.40, 6.45, 30)
    brl_uyu = np.linspace(7.20, 7.40, 30)
    us10y = np.linspace(4.20, 4.90, 30)

    df = pd.DataFrame(
        {
            "USD/UYU": uyu,
            "BRL/UYU": brl_uyu,
            "UI (BCU)": ui,
            "US 10Y Yield": us10y,
        },
        index=dates,
    )
    summary = compute_summary_metrics(df)
    alerts = detect_alerts(summary)
    titles = " | ".join(a["title"] for a in alerts)

    assert "USD/UYU en máximo anual" in titles
    assert "Movimiento diario atípico en USD/UYU" in titles
    assert "Tipo de cambio por encima de la UI" in titles

    brief = generate_morning_brief(summary, alerts)
    assert len(brief) == 4
    assert "USD/UYU" in brief[0]
    assert "UI (BCU)" in brief[1]


def test_save_history_snapshot_merges_without_duplicates(tmp_path):
    csv_path = tmp_path / "data" / "macro_history.csv"
    d1 = pd.date_range("2026-11-20", periods=3, freq="B")
    df1 = pd.DataFrame({"USD/UYU": [40.0, 40.1, 40.2]}, index=d1)
    save_history_snapshot(df1, str(csv_path))

    d2 = pd.date_range("2026-11-23", periods=3, freq="B")
    df2 = pd.DataFrame({"USD/UYU": [40.15, 40.3, 40.5]}, index=d2)
    merged = save_history_snapshot(df2, str(csv_path))

    assert len(merged) == 4
    assert merged.loc[pd.Timestamp("2026-11-23"), "USD/UYU"] == pytest.approx(40.15)
    assert merged.loc[pd.Timestamp("2026-11-25"), "USD/UYU"] == pytest.approx(40.5)


def test_send_optional_alerts_noop_without_env(monkeypatch):
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    alerts = [{"severity": "high", "title": "Test", "detail": "D", "action": "A"}]
    assert send_optional_alerts(alerts, ["Brief"], "2026-11-25") is False
