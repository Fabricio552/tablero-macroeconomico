import os
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


def send_optional_alerts(alerts: list[dict[str, str]], brief: list[str], date_str: str) -> bool:
    """Send actionable alerts via Slack Webhook or Telegram Bot when secrets are configured."""
    actionable = [a for a in alerts if a["severity"] in ("high", "medium")]
    if not actionable:
        return False

    lines = [f"📊 Monitor Macro UY/LatAm — {date_str}", ""]
    for a in actionable[:5]:
        icon = "🔴" if a["severity"] == "high" else "🟠"
        lines.append(f"{icon} {a['title']} — {a['detail']}")
    if brief:
        lines.append("")
        lines.append(brief[0].replace("**", "").replace("`", ""))
    message = "\n".join(lines)

    sent = False
    slack_url = os.environ.get("SLACK_WEBHOOK_URL", "").strip()
    if slack_url:
        try:
            resp = requests.post(slack_url, json={"text": message}, timeout=10)
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
                json={"chat_id": tg_chat, "text": message},
                timeout=10,
            )
            resp.raise_for_status()
            sent = True
        except Exception as exc:
            print(f"[WARN] No se pudo enviar alerta a Telegram: {exc}")

    return sent