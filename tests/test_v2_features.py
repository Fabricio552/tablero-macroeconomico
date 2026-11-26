import numpy as np
import pandas as pd
import pytest

from src.analyze import (
    compute_correlations,
    compute_summary_metrics,
    detect_alerts,
    format_whatsapp_report,
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


def _clear_notification_env(monkeypatch):
    for var in (
        "SLACK_WEBHOOK_URL",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID",
        "DASHBOARD_URL",
        "GITHUB_REPOSITORY",
        "TWILIO_ACCOUNT_SID",
        "TWILIO_AUTH_TOKEN",
        "TWILIO_WHATSAPP_FROM",
        "TWILIO_WHATSAPP_TO",
        "WHATSAPP_WEBHOOK_URL",
        "WHATSAPP_WEBHOOK_TOKEN",
        "WHATSAPP_WEBHOOK_TO",
    ):
        monkeypatch.delenv(var, raising=False)


def test_send_optional_alerts_noop_without_env(monkeypatch):
    _clear_notification_env(monkeypatch)
    alerts = [{"severity": "high", "title": "Test", "detail": "D", "action": "A"}]
    assert send_optional_alerts(alerts, ["Brief"], "2026-11-25") is False


def test_format_whatsapp_report_includes_quotes_alerts_and_link(monkeypatch):
    _clear_notification_env(monkeypatch)
    dates = pd.bdate_range("2026-11-01", periods=10)
    df = pd.DataFrame(
        {
            "USD/UYU": np.linspace(39.8, 40.77, 10),
            "BRL/UYU": np.linspace(7.4, 7.22, 10),
            "UI (BCU)": np.linspace(6.68, 6.7172, 10),
            "DXY": np.linspace(102.5, 103.77, 10),
            "USD/BRL": np.linspace(5.80, 5.74, 10),
        },
        index=dates,
    )
    summary = compute_summary_metrics(df)
    alerts = detect_alerts(summary)
    brief = generate_morning_brief(summary, alerts)

    msg_alert = format_whatsapp_report(alerts, brief, "2026-11-26", summary_df=summary)
    assert "Monitor Macro UY/LatAm — 2026-11-26" in msg_alert
    assert "USD/UYU: *40.77*" in msg_alert
    assert "BRL/UYU: *7.22*" in msg_alert
    assert "UI (BCU): *6.7172*" in msg_alert
    assert "DXY: *103.77*" in msg_alert
    assert "https://fabricio552.github.io/tablero-macroeconomico/" in msg_alert
    assert "**" not in msg_alert
    assert len(msg_alert) <= 1550

    calm_alerts = [{"severity": "info", "asset": "Mercado", "title": "Sin alertas", "detail": "Normal", "action": "Ok"}]
    msg_calm = format_whatsapp_report(calm_alerts, brief, "2026-11-26", summary_df=summary)
    assert "Sin alertas críticas hoy" in msg_calm


def test_send_optional_alerts_twilio_whatsapp_sends_daily_even_without_critical_alerts(monkeypatch):
    _clear_notification_env(monkeypatch)
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC123")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "secret")
    monkeypatch.setenv("TWILIO_WHATSAPP_TO", "+59899111222, whatsapp:+59899333444")
    monkeypatch.setenv("GITHUB_REPOSITORY", "Fabricio552/tablero-macroeconomico")

    calls = []

    class DummyResp:
        def raise_for_status(self):
            return None

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return DummyResp()

    monkeypatch.setattr("src.analyze.requests.post", fake_post)

    calm_alerts = [{"severity": "info", "asset": "Mercado", "title": "Normal", "detail": "Ok", "action": "Ok"}]
    dates = pd.bdate_range("2026-11-01", periods=8)
    df = pd.DataFrame({"USD/UYU": np.full(8, 40.50), "DXY": np.full(8, 103.5)}, index=dates)
    summary = compute_summary_metrics(df)

    ok = send_optional_alerts(calm_alerts, ["**Costos locales:** sin cambios"], "2026-11-26", summary_df=summary)
    assert ok is True
    assert len(calls) == 2
    assert calls[0][0] == "https://api.twilio.com/2010-04-01/Accounts/AC123/Messages.json"
    assert calls[0][1]["auth"] == ("AC123", "secret")
    assert calls[0][1]["data"]["From"] == "whatsapp:+14155238886"
    assert calls[0][1]["data"]["To"] == "whatsapp:+59899111222"
    assert calls[1][1]["data"]["To"] == "whatsapp:+59899333444"
    assert "Sin alertas críticas hoy" in calls[0][1]["data"]["Body"]
    assert "https://fabricio552.github.io/tablero-macroeconomico/" in calls[0][1]["data"]["Body"]


def test_send_optional_alerts_whatsapp_webhook_and_evolution_mode(monkeypatch):
    _clear_notification_env(monkeypatch)
    monkeypatch.setenv("WHATSAPP_WEBHOOK_URL", "https://hooks.example.com/macro-wa")
    monkeypatch.setenv("WHATSAPP_WEBHOOK_TOKEN", "tok-99")
    monkeypatch.setenv("DASHBOARD_URL", "https://mi-tablero.example.com/")

    calls = []

    class DummyResp:
        def raise_for_status(self):
            return None

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return DummyResp()

    monkeypatch.setattr("src.analyze.requests.post", fake_post)

    alerts = [{"severity": "high", "asset": "USD/UYU", "title": "Tope 52S", "detail": "40.77", "action": "Cubrir"}]
    assert send_optional_alerts(alerts, ["Resumen"], "2026-11-26") is True
    assert len(calls) == 1
    _, kwargs = calls[0]
    assert kwargs["headers"]["Authorization"] == "Bearer tok-99"
    assert kwargs["headers"]["apikey"] == "tok-99"
    assert kwargs["json"]["alerts_count"] == 1
    assert kwargs["json"]["has_critical_alerts"] is True
    assert kwargs["json"]["dashboard_url"] == "https://mi-tablero.example.com/"

    # Evolution API /message/sendText mode with group/target ID
    calls.clear()
    monkeypatch.setenv("WHATSAPP_WEBHOOK_URL", "https://evo.example.com/message/sendText/finanzas")
    monkeypatch.setenv("WHATSAPP_WEBHOOK_TO", "12036300112233@g.us")
    assert send_optional_alerts(alerts, ["Resumen"], "2026-11-26") is True
    assert calls[0][1]["json"]["number"] == "12036300112233@g.us"
    assert "text" in calls[0][1]["json"]
    assert set(calls[0][1]["json"].keys()) == {"number", "text"}
