from email.message import EmailMessage
from email.utils import make_msgid
import html
import os
import re
import smtplib
import ssl
import numpy as np
import pandas as pd
import requests

try:
    from extract import ASSET_METADATA, NON_MARKET_CORR_ASSETS, RATE_ASSETS
except ImportError:
    from src.extract import ASSET_METADATA, NON_MARKET_CORR_ASSETS, RATE_ASSETS


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


def _compute_vol_and_zscore(
    series: pd.Series,
    is_rate: bool,
    is_index: bool,
    window: int = 20,
) -> tuple[float, float]:
    """Compute 20-day volatility (annualized % for prices, daily bps for rates) and 1D z-score."""
    if is_rate:
        daily_moves = series.diff().dropna() * 100.0
    else:
        daily_moves = series.pct_change().dropna() * 100.0

    if len(daily_moves) < 2:
        return 0.0, 0.0

    prior_moves = daily_moves.iloc[:-1].tail(window)
    last_move = float(daily_moves.iloc[-1])

    if is_rate:
        vol_val = round(float(daily_moves.tail(window).std(ddof=1)), 1)
    else:
        vol_val = round(float(daily_moves.tail(window).std(ddof=1) * np.sqrt(252)), 1)

    if is_index or len(prior_moves) < 5:
        return vol_val, 0.0

    mu = float(prior_moves.mean())
    sigma = float(prior_moves.std(ddof=1))
    if sigma <= 1e-8:
        return vol_val, 0.0
    z_val = round((last_move - mu) / sigma, 2)
    return vol_val, z_val


def compute_summary_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Compute 1D, 5D, YTD, 1Y variations (% or bps), 52W range, 20D volatility, and 1D z-score."""
    _validate_dataframe(df, min_rows=2)
    current_year = int(df.index.max().year)
    summary = []

    for col in df.columns:
        series = df[col].dropna()
        if len(series) < 2:
            continue

        meta = ASSET_METADATA.get(col, {"category": "fx", "unit": "-", "is_rate": False})
        is_rate = col in RATE_ASSETS or bool(meta.get("is_rate", False))
        is_index = col in NON_MARKET_CORR_ASSETS or meta.get("category") == "index"
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

        vol_20d, z_score_1d = _compute_vol_and_zscore(series, is_rate=is_rate, is_index=is_index)
        vol_str = f"{vol_20d:.1f} bps/d" if is_rate else f"{vol_20d:.1f}%"
        z_str = "n/a" if is_index else f"{z_score_1d:+.1f}σ"
        decimals = 4 if is_index else 2

        summary.append({
            "Activo": col,
            "Unidad": meta["unit"],
            "Último": round(latest, decimals),
            "Var 1D": _format_delta(var_1d, unit_delta),
            "Var 5D": _format_delta(var_5d, unit_delta),
            "YTD": _format_delta(var_ytd, unit_delta),
            "1A": _format_delta(var_1y, unit_delta),
            "Vol 20D": vol_str,
            "Z-Score 1D": z_str,
            "Rango 52S": f"{low_52w:.2f} – {high_52w:.2f} ({pos_52w:.0f}%)",
            "var_1d_num": var_1d,
            "var_5d_num": var_5d,
            "var_ytd_num": var_ytd,
            "var_1y_num": var_1y,
            "vol_20d_num": vol_20d,
            "z_score_1d": z_score_1d,
            "low_52w": round(low_52w, decimals),
            "high_52w": round(high_52w, decimals),
            "pos_52w_pct": round(pos_52w, 1),
            "is_rate": is_rate,
            "is_index": is_index,
            "unit_delta": unit_delta,
        })

    return pd.DataFrame(summary)


def format_markdown_summary(summary_df: pd.DataFrame) -> pd.DataFrame:
    """Return display columns only for README markdown table rendering."""
    display_cols = [
        "Activo",
        "Unidad",
        "Último",
        "Var 1D",
        "Var 5D",
        "YTD",
        "1A",
        "Vol 20D",
        "Z-Score 1D",
        "Rango 52S",
    ]
    return summary_df[display_cols].copy()


def compute_correlations(
    df: pd.DataFrame,
    window: int = 60,
    raw_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Compute pairwise correlation of daily moves (% returns for market prices, diff for rates)."""
    _validate_dataframe(df, min_rows=3)
    source = raw_df if raw_df is not None else df
    changes = pd.DataFrame(index=source.index)

    for col in source.columns:
        if col in NON_MARKET_CORR_ASSETS:
            continue
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


def detect_alerts(summary_df: pd.DataFrame) -> list[dict[str, str]]:
    """Evaluate business-risk thresholds (52W breakouts, z-score shocks, 5D drift, and FX vs UI gap)."""
    alerts: list[dict[str, str]] = []
    by_name = summary_df.set_index("Activo")

    for asset, row in by_name.iterrows():
        is_rate = bool(row["is_rate"])
        is_index = bool(row.get("is_index", False))
        if is_index:
            continue

        pos = float(row["pos_52w_pct"])
        z1 = float(row["z_score_1d"])
        v1 = float(row["var_1d_num"])
        v5 = float(row["var_5d_num"])
        cat = ASSET_METADATA.get(asset, {}).get("category", "fx")

        # 1) 52W Extreme
        if pos >= 98.0:
            alerts.append({
                "severity": "high",
                "asset": asset,
                "title": f"{asset} en máximo anual ({pos:.0f}% del rango 52S)",
                "detail": f"Cierre en {row['Último']} ({row['YTD']} YTD).",
                "action": "Revisar cobertura cambiaria, costos de reposición o ajuste de listas de precios.",
            })
        elif pos <= 2.0:
            alerts.append({
                "severity": "medium",
                "asset": asset,
                "title": f"{asset} en piso anual ({pos:.0f}% del rango 52S)",
                "detail": f"Cierre en {row['Último']} ({row['YTD']} YTD).",
                "action": "Evaluar oportunidad de compra o fijación de precios en niveles bajos.",
            })

        # 2) Statistical anomaly / sharp daily shock
        shock_threshold = 10.0 if is_rate else (3.0 if cat == "commodity" else 1.2)
        if abs(z1) >= 2.0 or abs(v1) >= shock_threshold:
            sev = "high" if abs(z1) >= 2.5 else "medium"
            alerts.append({
                "severity": sev,
                "asset": asset,
                "title": f"Movimiento diario atípico en {asset} ({row['Var 1D']})",
                "detail": f"Desvío de {row['Z-Score 1D']} respecto a su volatilidad de últimos 20 días hábiles.",
                "action": "Validar si responde a shock global (DXY/US 10Y) o evento puntual antes de fijar precio.",
            })

        # 3) 5-day cumulative pressure
        wk_threshold = 15.0 if is_rate else (5.0 if cat == "commodity" else 2.5)
        if abs(v5) >= wk_threshold:
            alerts.append({
                "severity": "medium",
                "asset": asset,
                "title": f"Presión semanal acumulada en {asset} ({row['Var 5D']} en 5D)",
                "detail": f"Volatilidad 20D actual: {row['Vol 20D']}.",
                "action": "Monitorear impacto en capital de trabajo y márgenes de la semana.",
            })

    # 4) FX vs Local Inflation (UI BCU) real gap
    if "USD/UYU" in by_name.index and "UI (BCU)" in by_name.index:
        fx_ytd = float(by_name.loc["USD/UYU", "var_ytd_num"])
        ui_ytd = float(by_name.loc["UI (BCU)", "var_ytd_num"])
        real_gap = round(fx_ytd - ui_ytd, 2)
        if abs(real_gap) >= 1.5:
            direction = "por encima de" if real_gap > 0 else "por debajo de"
            action = (
                "Mejora competitividad exportadora; vigilar traslado a precios de bienes importados."
                if real_gap > 0
                else "Costos locales en UI suben más rápido que el dólar: vigilar compresión de márgenes en USD."
            )
            alerts.append({
                "severity": "medium" if abs(real_gap) >= 3.0 else "info",
                "asset": "USD vs UI",
                "title": f"Tipo de cambio {direction} la UI ({real_gap:+.2f} p.p. YTD)",
                "detail": f"USD/UYU {fx_ytd:+.2f}% YTD vs. UI (BCU) {ui_ytd:+.2f}% YTD.",
                "action": action,
            })

    rank = {"high": 0, "medium": 1, "info": 2}
    alerts.sort(key=lambda item: rank.get(item["severity"], 9))

    if not alerts:
        alerts.append({
            "severity": "info",
            "asset": "Mercado",
            "title": "Sin alertas críticas hoy — variables dentro de rangos normales",
            "detail": "No se registran rupturas de 52S ni desvíos estadísticos ≥ 2.0σ.",
            "action": "Mantener seguimiento habitual de tesorería y compras.",
        })
    return alerts


def generate_morning_brief(summary_df: pd.DataFrame, alerts: list[dict[str, str]]) -> list[str]:
    """Generate concise executive bullet points explaining market regime for business readers."""
    by_name = summary_df.set_index("Activo")
    bullets: list[str] = []

    if "USD/UYU" in by_name.index:
        uy = by_name.loc["USD/UYU"]
        brl_txt = ""
        if "BRL/UYU" in by_name.index:
            bu = by_name.loc["BRL/UYU"]
            brl_txt = f" y el cruce bilateral **BRL/UYU** en **{bu['Último']}** ({bu['YTD']} YTD)"
        dxy_txt = ""
        if "DXY" in by_name.index:
            dx = by_name.loc["DXY"]
            dxy_txt = f", frente a un dólar global (**DXY**) en **{dx['YTD']} YTD**"
        bullets.append(
            f"**Frente cambiario UY/Brasil:** `USD/UYU` cerró en **{uy['Último']}** ({uy['Var 1D']} 1D | {uy['YTD']} YTD | pos. 52S: {uy['pos_52w_pct']:.0f}%){brl_txt}{dxy_txt}."
        )

    if "USD/UYU" in by_name.index and "UI (BCU)" in by_name.index:
        fx_ytd = float(by_name.loc["USD/UYU", "var_ytd_num"])
        ui_ytd = float(by_name.loc["UI (BCU)", "var_ytd_num"])
        gap = fx_ytd - ui_ytd
        estado = "encima de la inflación medida en UI" if gap >= 0 else "debajo de la UI (atraso cambiario real)"
        bullets.append(
            f"**Costos locales vs. Dólar:** la **UI (BCU)** acumula **{ui_ytd:+.2f}% YTD** vs. **{fx_ytd:+.2f}% YTD** del `USD/UYU` (brecha real **{gap:+.2f} p.p.**, dólar por {estado})."
        )

    drv_parts = []
    if "US 10Y Yield" in by_name.index:
        r = by_name.loc["US 10Y Yield"]
        drv_parts.append(f"Tasa US 10Y en **{r['Último']:.2f}%** ({r['YTD']} YTD)")
    if "WTI Oil" in by_name.index:
        w = by_name.loc["WTI Oil"]
        drv_parts.append(f"WTI en **${w['Último']}** ({w['YTD']} YTD)")
    if "Gold" in by_name.index:
        g = by_name.loc["Gold"]
        drv_parts.append(f"Oro en **${g['Último']}** ({g['YTD']} YTD)")
    if drv_parts:
        bullets.append("**Drivers globales (financiamiento y energía):** " + " • ".join(drv_parts) + ".")

    high_med = [a for a in alerts if a["severity"] in ("high", "medium")]
    if high_med:
        top_titles = "; ".join(a["title"] for a in high_med[:3])
        bullets.append(f"**Alertas activas ({len(high_med)}):** {top_titles}.")
    else:
        bullets.append("**Alertas activas (0):** jornada sin desvíos estadísticos (|Z| < 2σ) ni rupturas de máximos/mínimos anuales.")

    return bullets


def save_history_snapshot(df: pd.DataFrame, history_path: str) -> pd.DataFrame:
    """Persist and merge daily close series into an accumulative CSV for Excel/Power BI."""
    os.makedirs(os.path.dirname(history_path), exist_ok=True)
    current = df.copy()
    current.index = pd.to_datetime(current.index).normalize()
    current.index.name = "Date"

    if os.path.exists(history_path):
        existing = pd.read_csv(history_path, index_col="Date", parse_dates=True)
        existing.index = pd.to_datetime(existing.index).normalize()
        merged = current.combine_first(existing)
    else:
        merged = current

    merged = merged.sort_index()
    merged = merged[~merged.index.duplicated(keep="last")]
    merged.to_csv(history_path, float_format="%.4f")
    return merged


DEFAULT_DASHBOARD_URL = "https://fabricio552.github.io/tablero-macroeconomico/"
TWILIO_SANDBOX_WHATSAPP_FROM = "whatsapp:+14155238886"


def _strip_markdown(text: str) -> str:
    return text.replace("**", "").replace("`", "")


def _resolve_dashboard_url(explicit_url: str | None = None) -> str:
    if explicit_url and explicit_url.strip():
        return explicit_url.strip()
    env_url = os.environ.get("DASHBOARD_URL", "").strip()
    if env_url:
        return env_url
    gh_repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if "/" in gh_repo:
        owner, repo = gh_repo.split("/", 1)
        return f"https://{owner.lower()}.github.io/{repo}/"
    return DEFAULT_DASHBOARD_URL


def _normalize_whatsapp_address(raw_value: str) -> str:
    value = raw_value.strip()
    if not value:
        return ""
    if value.lower().startswith("whatsapp:"):
        suffix = value.split(":", 1)[1].strip()
        return f"whatsapp:{suffix}"
    if not value.startswith("+"):
        value = f"+{value}"
    return f"whatsapp:{value}"


def format_whatsapp_report(
    alerts: list[dict[str, str]],
    brief: list[str],
    date_str: str,
    summary_df: pd.DataFrame | None = None,
    dashboard_url: str | None = None,
    max_chars: int = 1550,
) -> str:
    """Build a concise WhatsApp-ready daily macro report within provider length limits."""
    resolved_url = _resolve_dashboard_url(dashboard_url)
    actionable = [a for a in alerts if a["severity"] in ("high", "medium")]

    header = [f"🌎 *Monitor Macro UY/LatAm — {date_str}*", ""]

    if actionable:
        alert_lines = [f"🚨 *Alertas del día ({len(actionable)}):*"]
        for a in actionable[:3]:
            icon = "🔴" if a["severity"] == "high" else "🟠"
            alert_lines.append(f"{icon} {a['title']} — {a['detail']}")
        if len(actionable) > 3:
            alert_lines.append(f"• ... y {len(actionable) - 3} alerta(s) más en el tablero.")
    else:
        alert_lines = ["🟢 *Sin alertas críticas hoy:* variables dentro de rangos normales."]

    quotes_lines: list[str] = []
    if summary_df is not None and not summary_df.empty and "Activo" in summary_df.columns:
        by_name = summary_df.set_index("Activo")
        key_assets = ["USD/UYU", "BRL/UYU", "UI (BCU)", "DXY", "USD/BRL"]
        picked = [asset for asset in key_assets if asset in by_name.index]
        if picked:
            quotes_lines.append("💱 *Cierres clave:*")
            for asset in picked:
                row = by_name.loc[asset]
                if asset == "UI (BCU)":
                    quotes_lines.append(f"• UI (BCU): *{float(row['Último']):.4f}* ({row['YTD']} YTD)")
                else:
                    pos_suffix = f" | 52S: {row['pos_52w_pct']:.0f}%" if asset in ("USD/UYU", "BRL/UYU") else ""
                    quotes_lines.append(
                        f"• {asset}: *{row['Último']}* ({row['Var 1D']} 1D | {row['YTD']} YTD{pos_suffix})"
                    )

    brief_lines: list[str] = []
    clean_brief = [_strip_markdown(b) for b in brief if not b.strip().startswith("**Alertas activas")]
    if quotes_lines:
        clean_brief = [b for b in clean_brief if not b.startswith("Frente cambiario UY/Brasil:")]
    if clean_brief:
        brief_lines.append("📝 *Lectura ejecutiva:*")
        for b in clean_brief[:2]:
            brief_lines.append(f"• {b}")

    footer = [f"📊 *Tablero y simulador:*\n{resolved_url}"]

    sections = [
        "\n".join(header + alert_lines),
        "\n".join(quotes_lines) if quotes_lines else "",
        "\n".join(brief_lines) if brief_lines else "",
        "\n".join(footer),
    ]
    message = "\n\n".join(sec for sec in sections if sec)

    if len(message) > max_chars and brief_lines:
        sections[2] = ""
        message = "\n\n".join(sec for sec in sections if sec)

    if len(message) > max_chars:
        budget = max_chars - len(sections[3]) - 5
        head_body = "\n\n".join(sec for sec in sections[:2] if sec)
        message = f"{head_body[:max(budget, 80)].rstrip()}...\n\n{sections[3]}"

    return message


def _send_twilio_whatsapp(message: str) -> bool:
    sid = os.environ.get("TWILIO_ACCOUNT_SID", "").strip()
    token = os.environ.get("TWILIO_AUTH_TOKEN", "").strip()
    to_raw = os.environ.get("TWILIO_WHATSAPP_TO", "").strip()
    if not (sid and token and to_raw):
        return False

    from_raw = os.environ.get("TWILIO_WHATSAPP_FROM", "").strip() or TWILIO_SANDBOX_WHATSAPP_FROM
    from_addr = _normalize_whatsapp_address(from_raw)
    recipients = [_normalize_whatsapp_address(item) for item in to_raw.split(",") if item.strip()]

    sent_any = False
    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
    for to_addr in recipients:
        try:
            resp = requests.post(
                url,
                auth=(sid, token),
                data={"From": from_addr, "To": to_addr, "Body": message},
                timeout=10,
            )
            resp.raise_for_status()
            sent_any = True
            print(f"[INFO] Reporte diario enviado por Twilio WhatsApp a {to_addr}.")
        except Exception as exc:
            print(f"[WARN] No se pudo enviar WhatsApp vía Twilio a {to_addr}: {exc}")
    return sent_any


def _build_whatsapp_webhook_payload(
    webhook_url: str,
    message: str,
    date_str: str,
    actionable: list[dict[str, str]],
    dashboard_url: str,
    target: str = "",
) -> dict[str, object]:
    if "sendtext" in webhook_url.lower():
        payload: dict[str, object] = {"text": message}
        if target:
            payload["number"] = target
        return payload

    payload = {
        "text": message,
        "message": message,
        "body": message,
        "date": date_str,
        "alerts_count": len(actionable),
        "has_critical_alerts": bool(actionable),
        "alerts": actionable[:5],
        "dashboard_url": dashboard_url,
    }
    if target:
        payload["number"] = target
        payload["to"] = target
    return payload


def _send_whatsapp_webhook(
    message: str,
    date_str: str,
    actionable: list[dict[str, str]],
    dashboard_url: str,
) -> bool:
    webhook_url = os.environ.get("WHATSAPP_WEBHOOK_URL", "").strip()
    if not webhook_url:
        return False

    token = os.environ.get("WHATSAPP_WEBHOOK_TOKEN", "").strip()
    to_raw = os.environ.get("WHATSAPP_WEBHOOK_TO", "").strip()
    targets = [item.strip() for item in to_raw.split(",") if item.strip()] or [""]

    headers = {"Content-Type": "application/json"}
    if token:
        headers["apikey"] = token
        headers["Authorization"] = f"Bearer {token}"

    sent_any = False
    for target in targets:
        payload = _build_whatsapp_webhook_payload(
            webhook_url=webhook_url,
            message=message,
            date_str=date_str,
            actionable=actionable,
            dashboard_url=dashboard_url,
            target=target,
        )
        try:
            resp = requests.post(webhook_url, json=payload, headers=headers, timeout=10)
            resp.raise_for_status()
            sent_any = True
            label = target or "webhook configurado"
            print(f"[INFO] Reporte diario enviado vía WhatsApp Webhook ({label}).")
        except Exception as exc:
            print(f"[WARN] No se pudo enviar WhatsApp vía Webhook: {exc}")
    return sent_any


def _send_callmebot_whatsapp(message: str) -> bool:
    phone_raw = os.environ.get("CALLMEBOT_PHONE", "").strip()
    apikey = os.environ.get("CALLMEBOT_APIKEY", "").strip()
    if not (phone_raw and apikey):
        return False

    clean_phone = "".join(ch for ch in phone_raw if ch.isdigit() or ch == "+")
    if not clean_phone:
        return False

    try:
        resp = requests.get(
            "https://api.callmebot.com/whatsapp.php",
            params={"phone": clean_phone, "text": message, "apikey": apikey},
            timeout=15,
        )
        resp.raise_for_status()
        print("[INFO] Reporte diario enviado por CallMeBot WhatsApp.")
        return True
    except Exception as exc:
        print(f"[WARN] No se pudo enviar WhatsApp vía CallMeBot: {exc}")
        return False


def _markdown_to_html(text: str) -> str:
    escaped = html.escape(text)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"`(.+?)`", r"<code>\1</code>", escaped)
    return escaped


def format_email_report(
    alerts: list[dict[str, str]],
    brief: list[str],
    date_str: str,
    summary_df: pd.DataFrame | None = None,
    dashboard_url: str | None = None,
    chart_cid: str | None = None,
) -> tuple[str, str, str]:
    """Build (subject, plain_text, html_body) for daily executive macro email delivery."""
    resolved_url = _resolve_dashboard_url(dashboard_url)
    actionable = [a for a in alerts if a["severity"] in ("high", "medium")]

    if actionable:
        subject = f"🚨 [ALERTA] Monitor Macro UY/LatAm — {date_str} ({len(actionable)} alertas)"
    else:
        subject = f"📊 Monitor Macro UY/LatAm — Cierre {date_str}"

    plain_text = format_whatsapp_report(
        alerts=alerts,
        brief=brief,
        date_str=date_str,
        summary_df=summary_df,
        dashboard_url=resolved_url,
        max_chars=4000,
    ).replace("*", "")

    badge_colors = {
        "high": ("#fef2f2", "#fecaca", "#b91c1c"),
        "medium": ("#fffbeb", "#fde68a", "#b45309"),
        "info": ("#f0fdf4", "#bbf7d0", "#15803d"),
    }
    alert_cards = []
    for a in alerts[:6]:
        sev = a.get("severity", "info")
        bg, brd, clr = badge_colors.get(sev, badge_colors["info"])
        alert_cards.append(
            f"<div style='background:{bg};border-left:4px solid {brd};padding:10px 12px;margin-bottom:8px;border-radius:6px;'>"
            f"<div style='font-weight:700;color:{clr};font-size:13px;'>[{html.escape(sev.upper())}] {html.escape(a['title'])}</div>"
            f"<div style='color:#334155;font-size:13px;margin-top:2px;'>{html.escape(a['detail'])}</div>"
            f"<div style='color:#475569;font-size:12px;margin-top:3px;'><em>Acción:</em> {html.escape(a['action'])}</div>"
            f"</div>"
        )

    brief_html = "".join(
        f"<li style='margin-bottom:6px;line-height:1.45;'>{_markdown_to_html(item)}</li>"
        for item in brief
    )

    table_html = ""
    if summary_df is not None and not summary_df.empty:
        rows_html = []
        for _, row in summary_df.iterrows():
            activo = str(row.get("Activo", ""))
            is_idx = bool(row.get("is_index", False))
            ultimo_raw = row.get("Último", "")
            try:
                ultimo_txt = f"{float(ultimo_raw):.4f}" if is_idx else f"{float(ultimo_raw):g}"
            except (TypeError, ValueError):
                ultimo_txt = str(ultimo_raw)

            v1 = float(row.get("var_1d_num", 0.0) or 0.0)
            vy = float(row.get("var_ytd_num", 0.0) or 0.0)
            z1 = float(row.get("z_score_1d", 0.0) or 0.0)
            c1 = "#1d4ed8" if v1 > 0 else ("#b91c1c" if v1 < 0 else "#334155")
            cy = "#1d4ed8" if vy > 0 else ("#b91c1c" if vy < 0 else "#334155")
            cz = "#b45309;font-weight:700" if abs(z1) >= 2.0 else "#475569"

            rows_html.append(
                "<tr style='border-bottom:1px solid #e2e8f0;'>"
                f"<td style='padding:7px 8px;font-weight:600;color:#0f172a;'>{html.escape(activo)}</td>"
                f"<td style='padding:7px 8px;text-align:right;font-weight:600;'>{html.escape(ultimo_txt)}</td>"
                f"<td style='padding:7px 8px;text-align:right;color:{c1};font-weight:600;'>{html.escape(str(row.get('Var 1D', '-')))}</td>"
                f"<td style='padding:7px 8px;text-align:right;'>{html.escape(str(row.get('Var 5D', '-')))}</td>"
                f"<td style='padding:7px 8px;text-align:right;color:{cy};font-weight:600;'>{html.escape(str(row.get('YTD', '-')))}</td>"
                f"<td style='padding:7px 8px;text-align:right;color:{cz};'>{html.escape(str(row.get('Z-Score 1D', '-')))}</td>"
                f"<td style='padding:7px 8px;text-align:right;color:#475569;'>{html.escape(str(row.get('Rango 52S', '-')))}</td>"
                "</tr>"
            )
        table_html = (
            "<h3 style='margin:20px 0 8px;font-size:15px;color:#0f172a;'>📊 Resumen Ejecutivo de Mercado</h3>"
            "<div style='overflow-x:auto;'>"
            "<table style='width:100%;border-collapse:collapse;font-size:12.5px;'>"
            "<thead><tr style='background:#0f172a;color:#ffffff;'>"
            "<th style='padding:8px;text-align:left;'>Activo</th>"
            "<th style='padding:8px;text-align:right;'>Último</th>"
            "<th style='padding:8px;text-align:right;'>Var 1D</th>"
            "<th style='padding:8px;text-align:right;'>Var 5D</th>"
            "<th style='padding:8px;text-align:right;'>YTD</th>"
            "<th style='padding:8px;text-align:right;'>Z-Score</th>"
            "<th style='padding:8px;text-align:right;'>Rango 52S</th>"
            "</tr></thead>"
            f"<tbody>{''.join(rows_html)}</tbody>"
            "</table></div>"
        )

    chart_html = ""
    if chart_cid:
        chart_html = (
            "<h3 style='margin:20px 0 8px;font-size:15px;color:#0f172a;'>📈 Tablero Ejecutivo (4 Vistas)</h3>"
            f"<img src='cid:{html.escape(chart_cid)}' alt='Tablero Macroeconómico' "
            "style='width:100%;max-width:700px;height:auto;border:1px solid #e2e8f0;border-radius:8px;display:block;' />"
        )

    html_body = f"""<!DOCTYPE html>
<html lang="es">
<body style="margin:0;padding:16px;background:#f8fafc;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#0f172a;">
  <div style="max-width:740px;margin:0 auto;background:#ffffff;border:1px solid #e2e8f0;border-radius:12px;overflow:hidden;">
    <div style="background:#0f172a;color:#ffffff;padding:18px 20px;">
      <div style="font-size:18px;font-weight:700;">🌎 Monitor Macroeconómico V2 — Uruguay / LatAm</div>
      <div style="font-size:13px;color:#cbd5e1;margin-top:4px;">Cierre al {html.escape(date_str)} • Datos Yahoo Finance + BCU (UI y BRL/UYU)</div>
      <div style="margin-top:12px;">
        <a href="{html.escape(resolved_url)}" style="display:inline-block;background:#2563eb;color:#ffffff;text-decoration:none;font-weight:600;font-size:13px;padding:8px 14px;border-radius:6px;">Abrir Tablero Interactivo y Simulador →</a>
      </div>
    </div>
    <div style="padding:18px 20px;">
      <h3 style="margin:0 0 10px;font-size:15px;color:#0f172a;">🚨 Radar de Alertas del Día</h3>
      {''.join(alert_cards)}
      <h3 style="margin:18px 0 8px;font-size:15px;color:#0f172a;">📝 Morning Brief Ejecutivo</h3>
      <ul style="margin:0;padding-left:18px;font-size:13.5px;color:#1e293b;">{brief_html}</ul>
      {table_html}
      {chart_html}
      <p style="margin:20px 0 0;font-size:11.5px;color:#64748b;border-top:1px solid #e2e8f0;padding-top:10px;">
        Envío automático diario (Lun–Vie). Datos oficiales BCU vía datosUruguay.com (CC-BY-4.0).
      </p>
    </div>
  </div>
</body>
</html>"""
    return subject, plain_text, html_body


def _send_email_report(
    alerts: list[dict[str, str]],
    brief: list[str],
    date_str: str,
    summary_df: pd.DataFrame | None = None,
    dashboard_url: str | None = None,
    chart_path: str | None = None,
) -> bool:
    email_from = os.environ.get("EMAIL_FROM", "").strip()
    email_password = os.environ.get("EMAIL_PASSWORD", "").strip()
    if not (email_from and email_password):
        return False

    to_raw = os.environ.get("EMAIL_TO", "").strip() or email_from
    recipients = [item.strip() for item in to_raw.split(",") if item.strip()]
    if not recipients:
        return False

    smtp_host = os.environ.get("EMAIL_SMTP_HOST", "").strip() or "smtp.gmail.com"
    port_raw = os.environ.get("EMAIL_SMTP_PORT", "").strip() or "465"
    try:
        smtp_port = int(port_raw)
    except ValueError:
        smtp_port = 465

    if smtp_host.lower() == "smtp.gmail.com" and " " in email_password and len(email_password.replace(" ", "")) == 16:
        email_password = email_password.replace(" ", "")

    has_chart = bool(chart_path and os.path.isfile(chart_path))
    raw_cid = make_msgid(domain="tablero.local") if has_chart else None
    clean_cid = raw_cid.strip("<>") if raw_cid else None

    subject, plain_text, html_body = format_email_report(
        alerts=alerts,
        brief=brief,
        date_str=date_str,
        summary_df=summary_df,
        dashboard_url=dashboard_url,
        chart_cid=clean_cid,
    )

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = email_from
    msg["To"] = ", ".join(recipients)
    msg.set_content(plain_text)
    msg.add_alternative(html_body, subtype="html")

    if has_chart and raw_cid and chart_path:
        with open(chart_path, "rb") as img_file:
            img_bytes = img_file.read()
        html_part = msg.get_payload()[1]
        html_part.add_related(
            img_bytes,
            maintype="image",
            subtype="png",
            cid=raw_cid,
            filename=os.path.basename(chart_path),
        )

    context = ssl.create_default_context()
    try:
        if smtp_port == 465:
            with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context, timeout=15) as server:
                server.login(email_from, email_password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
                server.ehlo()
                server.starttls(context=context)
                server.ehlo()
                server.login(email_from, email_password)
                server.send_message(msg)
        print(f"[INFO] Reporte diario enviado por Email a {len(recipients)} destinatario(s).")
        return True
    except Exception as exc:
        print(f"[WARN] No se pudo enviar Email: {exc}")
        return False


def send_optional_alerts(
    alerts: list[dict[str, str]],
    brief: list[str],
    date_str: str,
    summary_df: pd.DataFrame | None = None,
    dashboard_url: str | None = None,
    chart_path: str | None = None,
) -> bool:
    """Send daily Email / WhatsApp reports and actionable Slack / Telegram alerts."""
    actionable = [a for a in alerts if a["severity"] in ("high", "medium")]
    resolved_url = _resolve_dashboard_url(dashboard_url)
    sent = False

    # 1) Email (Gmail / SMTP): daily executive report with table, chart & alerts
    if _send_email_report(
        alerts=alerts,
        brief=brief,
        date_str=date_str,
        summary_df=summary_df,
        dashboard_url=resolved_url,
        chart_path=chart_path,
    ):
        sent = True

    # 2) Slack & Telegram: actionable alerts only (HIGH / MEDIUM)
    if actionable:
        lines = [f"📊 Monitor Macro UY/LatAm — {date_str}", ""]
        for a in actionable[:5]:
            icon = "🔴" if a["severity"] == "high" else "🟠"
            lines.append(f"{icon} {a['title']} — {a['detail']}")
        if brief:
            lines.append("")
            lines.append(_strip_markdown(brief[0]))
        alert_msg = "\n".join(lines)

        slack_url = os.environ.get("SLACK_WEBHOOK_URL", "").strip()
        if slack_url:
            try:
                resp = requests.post(slack_url, json={"text": alert_msg}, timeout=10)
                resp.raise_for_status()
                sent = True
            except Exception as exc:
                print(f"[WARN] No se pudo enviar alerta a Slack: {exc}")

        tg_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        tg_chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
        if tg_token and tg_chat:
            try:
                resp = requests.post(
                    f"https://api.telegram.org/bot{tg_token}/sendMessage",
                    json={"chat_id": tg_chat, "text": alert_msg},
                    timeout=10,
                )
                resp.raise_for_status()
                sent = True
            except Exception as exc:
                print(f"[WARN] No se pudo enviar alerta a Telegram: {exc}")

    # 3) WhatsApp (CallMeBot / Twilio / External Webhook): daily weekday brief + alerts
    has_callmebot = bool(
        os.environ.get("CALLMEBOT_PHONE", "").strip()
        and os.environ.get("CALLMEBOT_APIKEY", "").strip()
    )
    has_twilio = bool(
        os.environ.get("TWILIO_ACCOUNT_SID", "").strip()
        and os.environ.get("TWILIO_AUTH_TOKEN", "").strip()
        and os.environ.get("TWILIO_WHATSAPP_TO", "").strip()
    )
    has_wa_webhook = bool(os.environ.get("WHATSAPP_WEBHOOK_URL", "").strip())

    if has_callmebot or has_twilio or has_wa_webhook:
        wa_msg = format_whatsapp_report(
            alerts=alerts,
            brief=brief,
            date_str=date_str,
            summary_df=summary_df,
            dashboard_url=resolved_url,
        )
        if has_callmebot:
            cmb_msg = (
                wa_msg
                if len(wa_msg) <= 1150
                else format_whatsapp_report(
                    alerts=alerts,
                    brief=brief,
                    date_str=date_str,
                    summary_df=summary_df,
                    dashboard_url=resolved_url,
                    max_chars=1150,
                )
            )
            if _send_callmebot_whatsapp(cmb_msg):
                sent = True
        if has_twilio and _send_twilio_whatsapp(wa_msg):
            sent = True
        if has_wa_webhook and _send_whatsapp_webhook(wa_msg, date_str, actionable, resolved_url):
            sent = True

    return sent