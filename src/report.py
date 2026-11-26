import html
import json
import os
import re
from datetime import datetime, timezone
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import seaborn as sns

try:
    from analyze import (
        compute_correlations,
        compute_summary_metrics,
        detect_alerts,
        format_markdown_summary,
        generate_morning_brief,
        save_history_snapshot,
        send_optional_alerts,
    )
    from extract import (
        ASSET_METADATA,
        COMMODITY_ASSETS,
        FX_ASSETS,
        fetch_macro_bundle,
    )
except ImportError:
    from src.analyze import (
        compute_correlations,
        compute_summary_metrics,
        detect_alerts,
        format_markdown_summary,
        generate_morning_brief,
        save_history_snapshot,
        send_optional_alerts,
    )
    from src.extract import (
        ASSET_METADATA,
        COMMODITY_ASSETS,
        FX_ASSETS,
        fetch_macro_bundle,
    )

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_IMG = os.path.join(BASE_DIR, "output", "macro_dashboard.png")
OUTPUT_HTML = os.path.join(BASE_DIR, "docs", "index.html")
HISTORY_CSV = os.path.join(BASE_DIR, "data", "macro_history.csv")
README_PATH = os.path.join(BASE_DIR, "README.md")

FX_STYLES = {
    "USD/UYU": {"color": "#1d4ed8", "ls": "-", "dash": "solid", "lw": 2.3, "label": "USD/UYU"},
    "USD/BRL": {"color": "#d97706", "ls": "-", "dash": "solid", "lw": 1.9, "label": "USD/BRL"},
    "BRL/UYU": {"color": "#0891b2", "ls": "-", "dash": "solid", "lw": 2.0, "label": "BRL/UYU (UYU/Real)"},
    "USD/ARS": {"color": "#4d7c0f", "ls": "-", "dash": "solid", "lw": 1.8, "label": "USD/ARS (Oficial)"},
    "UI (BCU)": {"color": "#64748b", "ls": ":", "dash": "dot", "lw": 2.0, "label": "UI BCU (Inflación)"},
    "DXY": {"color": "#db2777", "ls": "-", "dash": "solid", "lw": 2.5, "label": "DXY (Global)"},
}

DRIVER_STYLES = {
    "WTI Oil": {"color": "#dc2626", "ls": "-", "dash": "solid", "lw": 2.1, "label": "WTI Oil (% acum.)"},
    "Gold": {"color": "#ca8a04", "ls": "-", "dash": "solid", "lw": 2.1, "label": "Gold (% acum.)"},
    "US 10Y Yield": {"color": "#7c3aed", "ls": "-", "dash": "solid", "lw": 2.2, "label": "US 10Y Yield (%)"},
}


def _place_end_labels(ax, x_pos, entries: list[tuple[float, str, str]]) -> None:
    """Place direct right-side labels without vertical overlap."""
    if not entries:
        return
    ymin, ymax = ax.get_ylim()
    span = max(ymax - ymin, 1e-6)
    min_sep = min(span * 0.085, span / (len(entries) + 1.5))

    sorted_entries = sorted(entries, key=lambda item: item[0])
    placed_y: list[float] = []
    for raw_y, _, _ in sorted_entries:
        y = raw_y
        if placed_y and (y - placed_y[-1]) < min_sep:
            y = placed_y[-1] + min_sep
        placed_y.append(y)

    if placed_y[-1] > ymax - span * 0.04:
        shift = placed_y[-1] - (ymax - span * 0.04)
        placed_y = [y - shift for y in placed_y]

    for (_, label, color), y_lbl in zip(sorted_entries, placed_y):
        ax.annotate(
            label,
            xy=(x_pos, y_lbl),
            xytext=(6, 0),
            textcoords="offset points",
            va="center",
            ha="left",
            fontsize=8.2,
            fontweight="bold",
            color=color,
        )


def _markdown_inline_to_html(text: str) -> str:
    """Safely convert simple **bold** and `code` markers into HTML."""
    escaped = html.escape(text)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"`(.+?)`", r"<code>\1</code>", escaped)
    return escaped


def generate_chart(
    df: pd.DataFrame,
    summary_df: pd.DataFrame,
    corr_matrix: pd.DataFrame,
    output_path: str = OUTPUT_IMG,
) -> None:
    """Generate a 4-panel executive static dashboard for GitHub README and LinkedIn."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.style.use("seaborn-v0_8-whitegrid")
    fig, axes = plt.subplots(
        2,
        2,
        figsize=(16.5, 10.8),
        gridspec_kw={"hspace": 0.36, "wspace": 0.25},
    )
    ax_fx, ax_drv = axes[0, 0], axes[0, 1]
    ax_bar, ax_corr = axes[1, 0], axes[1, 1]

    last_date = df.index.max()
    date_span = last_date - df.index.min()

    # 1) Panel FX, BRL/UYU, UI (BCU) vs DXY (% acumulado 1A)
    fx_panel_cols = [c for c in [*FX_ASSETS, "UI (BCU)"] if c in df.columns]
    fx_pct = (df[fx_panel_cols] / df[fx_panel_cols].iloc[0] - 1.0) * 100.0
    end_labels_fx = []
    for col in fx_panel_cols:
        st = FX_STYLES[col]
        ax_fx.plot(
            fx_pct.index,
            fx_pct[col],
            color=st["color"],
            linestyle=st["ls"],
            linewidth=st["lw"],
            label=st["label"],
        )
        end_val = float(fx_pct[col].iloc[-1])
        end_labels_fx.append((end_val, f"{col} {end_val:+.1f}%", st["color"]))

    ax_fx.axhline(0, color="#9ca3af", linestyle=":", linewidth=1.1)
    ax_fx.set_title("1. Presión Cambiaria, BRL/UYU y UI BCU (% Acum. 1A)", fontweight="bold", fontsize=11.5, pad=10)
    ax_fx.set_ylabel("Variación acumulada (%)")
    ax_fx.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
    ax_fx.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))
    ax_fx.set_xlim(df.index.min(), last_date + pd.Timedelta(days=max(int(date_span.days * 0.25), 26)))
    last_num = mdates.date2num(last_date)
    ax_fx.set_xticks([t for t in ax_fx.get_xticks() if mdates.date2num(df.index.min()) <= t <= last_num])
    ax_fx.legend(loc="upper left", ncol=2, frameon=True, facecolor="white", framealpha=0.92, fontsize=8.0)
    _place_end_labels(ax_fx, last_date, end_labels_fx)

    # 2) Panel Drivers Globales: Commodities (% acum) + US 10Y Yield (%)
    comm_cols = [c for c in COMMODITY_ASSETS if c in df.columns]
    comm_pct = (df[comm_cols] / df[comm_cols].iloc[0] - 1.0) * 100.0
    lines_drv = []
    for col in comm_cols:
        st = DRIVER_STYLES[col]
        (line,) = ax_drv.plot(
            comm_pct.index,
            comm_pct[col],
            color=st["color"],
            linestyle=st["ls"],
            linewidth=st["lw"],
            label=f"{col} ({float(comm_pct[col].iloc[-1]):+.1f}%)",
        )
        lines_drv.append(line)

    ax_drv.axhline(0, color="#9ca3af", linestyle=":", linewidth=1.1)
    ax_drv.set_title("2. Drivers Globales: Commodities (% Acum.) y Tasa US 10Y (%)", fontweight="bold", fontsize=11.5, pad=10)
    ax_drv.set_ylabel("Commodities (% acum. 1A)")
    ax_drv.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
    ax_drv.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))

    if "US 10Y Yield" in df.columns:
        ax_rate = ax_drv.twinx()
        st_rate = DRIVER_STYLES["US 10Y Yield"]
        rate_series = df["US 10Y Yield"]
        rate_latest = float(rate_series.iloc[-1])
        rate_bps_1y = (rate_latest - float(rate_series.iloc[0])) * 100.0
        (rate_line,) = ax_rate.plot(
            rate_series.index,
            rate_series,
            color=st_rate["color"],
            linestyle="--",
            linewidth=st_rate["lw"],
            label=f"US 10Y: {rate_latest:.2f}% ({rate_bps_1y:+.0f} bps 1A)",
        )
        lines_drv.append(rate_line)
        ax_rate.set_ylabel("Tasa US 10Y (%)", color=st_rate["color"])
        ax_rate.tick_params(axis="y", colors=st_rate["color"])
        ax_rate.grid(False)

    labels_drv = [l.get_label() for l in lines_drv]
    ax_drv.legend(lines_drv, labels_drv, loc="upper left", frameon=True, facecolor="white", framealpha=0.92, fontsize=8.5)

    # 3) Panel Desempeño YTD (%) y posición en rango 52S
    price_rows = summary_df[~summary_df["is_rate"]].sort_values("var_ytd_num", ascending=True)
    y_vals = price_rows["var_ytd_num"].to_numpy()
    colors_bar = [
        "#64748b" if bool(is_idx) else ("#2563eb" if v >= 0 else "#dc2626")
        for v, is_idx in zip(y_vals, price_rows["is_index"])
    ]
    bars = ax_bar.barh(price_rows["Activo"], y_vals, color=colors_bar, height=0.62, alpha=0.9)
    ax_bar.axvline(0, color="#4b5563", linewidth=1.1)

    max_abs = max(float(np.abs(y_vals).max()) if len(y_vals) else 10.0, 5.0)
    ax_bar.set_xlim(-max_abs * 1.48, max_abs * 1.58)
    ax_bar.xaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
    ax_bar.set_title("3. Desempeño YTD (%) y Posición en Rango 52S", fontweight="bold", fontsize=11.5, pad=10)
    ax_bar.set_xlabel("Variación Año Corrido (%)")

    for bar, (_, row) in zip(bars, price_rows.iterrows()):
        val = float(row["var_ytd_num"])
        pos = float(row["pos_52w_pct"])
        offset = max_abs * 0.04
        x_txt = val + offset if val >= 0 else val - offset
        ha = "left" if val >= 0 else "right"
        suffix = " [Índice]" if bool(row["is_index"]) else f" [52S: {pos:.0f}%]"
        ax_bar.text(
            x_txt,
            bar.get_y() + bar.get_height() / 2.0,
            f"{val:+.1f}%{suffix}",
            va="center",
            ha=ha,
            fontsize=8.2,
            fontweight="bold",
            color="#1f2937",
        )

    rate_rows = summary_df[summary_df["is_rate"]]
    if not rate_rows.empty:
        r0 = rate_rows.iloc[0]
        ax_bar.text(
            0.98,
            0.04,
            f"US 10Y Yield: {r0['Último']:.2f}%  |  YTD: {r0['YTD']}  |  52S: {r0['pos_52w_pct']:.0f}%",
            transform=ax_bar.transAxes,
            ha="right",
            fontsize=8.3,
            fontweight="bold",
            color="#5b21b6",
            bbox=dict(boxstyle="round,pad=0.35", facecolor="#f5f3ff", edgecolor="#c4b5fd"),
        )

    # 4) Panel Heatmap triangular inferior de correlaciones
    corr_sub = corr_matrix.iloc[1:, :-1] if len(corr_matrix) > 1 else corr_matrix
    mask = np.triu(np.ones_like(corr_sub, dtype=bool), k=1) if len(corr_matrix) > 1 else None
    sns.heatmap(
        corr_sub,
        mask=mask,
        annot=True,
        fmt=".2f",
        cmap="RdBu_r",
        vmin=-1,
        vmax=1,
        center=0,
        square=True,
        linewidths=0.8,
        cbar_kws={"shrink": 0.8, "label": "Correlación (r)"},
        ax=ax_corr,
    )
    ax_corr.set_title("4. Correlación de Cambios Diarios (Últimos 60 Días Hábiles)", fontweight="bold", fontsize=11.5, pad=10)
    ax_corr.set_xlabel("")
    ax_corr.set_ylabel("")
    ax_corr.tick_params(axis="x", rotation=30)
    ax_corr.tick_params(axis="y", rotation=0)

    fig.suptitle(
        "Monitor Macro & Riesgo Cambiario V2 — Uruguay / LatAm & Drivers Globales",
        fontsize=15,
        fontweight="bold",
        y=0.97,
        color="#111827",
    )
    fig.text(
        0.5,
        0.935,
        f"Cierre al {last_date.strftime('%Y-%m-%d')}  •  Precios en % | Tasa US 10Y en bps | Datos locales BCU",
        ha="center",
        fontsize=10,
        color="#4b5563",
    )
    fig.text(
        0.5,
        0.014,
        "Fuentes: Yahoo Finance (yfinance) & BCU vía datosUruguay.com (CC-BY-4.0) • USD/ARS oficial (ARS=X) • UI excluida de correlaciones diarias",
        ha="center",
        fontsize=8.3,
        color="#6b7280",
    )

    plt.savefig(output_path, dpi=250, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def _padded_range(values: np.ndarray, pad_frac: float = 0.14, min_pad: float = 1.5) -> list[float]:
    """Compute [min, max] with padding so tick labels never collide at axis corners."""
    vmin = float(np.nanmin(values))
    vmax = float(np.nanmax(values))
    span = max(vmax - vmin, 1e-6)
    pad = max(span * pad_frac, min_pad)
    return [vmin - pad, vmax + pad]


def _build_html_table(summary_df: pd.DataFrame) -> str:
    """Render a clean responsive executive HTML table."""
    disp = format_markdown_summary(summary_df)
    headers = "".join(
        f'<th class="{"num" if i >= 2 else "txt"}">{html.escape(str(col))}</th>'
        for i, col in enumerate(disp.columns)
    )
    rows_html = []
    for _, row in disp.iterrows():
        cells = []
        for i, col in enumerate(disp.columns):
            val = str(row[col])
            esc = html.escape(val)
            if i < 2:
                cls = "txt fw" if i == 0 else "txt muted"
            elif col in ("Var 1D", "Var 5D", "YTD", "1A"):
                cls = "num pos" if val.startswith("+") else ("num neg" if val.startswith("-") else "num")
            elif col == "Z-Score 1D":
                is_anom = val not in ("n/a",) and abs(float(val.replace("σ", ""))) >= 2.0
                cls = "num anom" if is_anom else "num"
            else:
                cls = "num"
            cells.append(f'<td class="{cls}">{esc}</td>')
        rows_html.append(f"<tr>{''.join(cells)}</tr>")

    return (
        '<div class="table-wrap">'
        "<table>"
        f"<thead><tr>{headers}</tr></thead>"
        f"<tbody>{''.join(rows_html)}</tbody>"
        "</table>"
        "</div>"
    )


def _build_brief_and_alerts_html(brief: list[str], alerts: list[dict[str, str]]) -> str:
    """Render Morning Brief bullets and actionable alert cards."""
    brief_items = "".join(f"<li>{_markdown_inline_to_html(b)}</li>" for b in brief)

    alert_cards = []
    for a in alerts[:5]:
        sev = a.get("severity", "info")
        sev_label = {"high": "ALTA", "medium": "MEDIA", "info": "INFO"}.get(sev, "INFO")
        alert_cards.append(
            f'<div class="alert-item sev-{html.escape(sev)}">'
            f'<div class="alert-top"><span class="badge">{sev_label}</span>'
            f'<strong>{html.escape(a["title"])}</strong></div>'
            f'<div class="alert-detail">{html.escape(a["detail"])}</div>'
            f'<div class="alert-action">Acción sugerida: {html.escape(a["action"])}</div>'
            "</div>"
        )

    return f"""
    <section class="exec-grid">
      <div class="card">
        <h2>📝 Morning Brief Ejecutivo</h2>
        <ul class="brief-list">{brief_items}</ul>
      </div>
      <div class="card">
        <h2>🚨 Radar de Alertas y Desvíos</h2>
        <div class="alert-list">{''.join(alert_cards)}</div>
      </div>
    </section>
    """


def _build_simulator_payload(summary_df: pd.DataFrame) -> dict:
    """Build market return lookup for the client-side business margin simulator."""
    by_name = summary_df.set_index("Activo")

    def _get(asset: str) -> dict[str, float]:
        if asset not in by_name.index:
            return {"5d": 0.0, "ytd": 0.0, "1y": 0.0}
        row = by_name.loc[asset]
        return {
            "5d": float(row["var_5d_num"]),
            "ytd": float(row["var_ytd_num"]),
            "1y": float(row["var_1y_num"]),
        }

    return {
        "usd_uyu": _get("USD/UYU"),
        "brl_uyu": _get("BRL/UYU"),
        "ui_bcu": _get("UI (BCU)"),
    }


def generate_interactive_dashboard(
    df: pd.DataFrame,
    summary_df: pd.DataFrame,
    corr_matrix: pd.DataFrame,
    alerts: list[dict[str, str]],
    brief: list[str],
    sources: dict[str, str],
    output_path: str = OUTPUT_HTML,
) -> None:
    """Generate V2 self-contained interactive Plotly + business simulator HTML dashboard."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    last_date_str = df.index.max().strftime("%Y-%m-%d")

    range_buttons = [
        dict(count=1, label="1M", step="month", stepmode="backward"),
        dict(count=3, label="3M", step="month", stepmode="backward"),
        dict(count=6, label="6M", step="month", stepmode="backward"),
        dict(count=1, label="YTD", step="year", stepmode="todate"),
        dict(step="all", label="1A"),
    ]
    plot_config = {"responsive": True, "displaylogo": False}

    # --- 1) FX + BRL/UYU + UI vs DXY ---
    fig_fx = go.Figure()
    fx_cols = [c for c in [*FX_ASSETS, "UI (BCU)"] if c in df.columns]
    fx_pct = (df[fx_cols] / df[fx_cols].iloc[0] - 1.0) * 100.0
    for col in fx_cols:
        st = FX_STYLES[col]
        unit = ASSET_METADATA[col]["unit"]
        custom = np.column_stack([df[col].to_numpy(), np.full(len(df), unit)])
        fig_fx.add_trace(
            go.Scatter(
                x=df.index,
                y=fx_pct[col].round(2),
                mode="lines",
                name=st["label"],
                line=dict(color=st["color"], width=st["lw"], dash=st["dash"]),
                customdata=custom,
                hovertemplate=(
                    f"<b>{st['label']}</b>: %{{y:+.2f}}%<br>"
                    "Valor: %{customdata[0]:.3f} %{customdata[1]}<extra></extra>"
                ),
            )
        )
    fig_fx.add_hline(y=0, line_dash="dot", line_color="#9ca3af", line_width=1.1)
    fig_fx.update_layout(
        title=dict(
            text="<b>1. Presión Cambiaria, BRL/UYU y UI BCU (% Acum. 1A)</b>",
            x=0.01,
            y=0.96,
            yanchor="top",
            font=dict(size=14),
        ),
        template="plotly_white",
        height=465,
        margin=dict(t=130, l=72, r=24, b=54),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.14, xanchor="left", x=0.0),
        xaxis=dict(
            rangeselector=dict(buttons=range_buttons, bgcolor="#f1f5f9", activecolor="#1d4ed8", y=1.02),
            ticklabelstandoff=6,
            automargin=True,
        ),
        yaxis=dict(
            title="Var. acumulada (%)",
            ticksuffix="%",
            range=_padded_range(fx_pct.to_numpy(), pad_frac=0.14, min_pad=1.5),
            ticklabelstandoff=8,
            automargin=True,
        ),
    )

    # --- 2) Drivers Globales ---
    fig_drv = make_subplots(specs=[[{"secondary_y": True}]])
    comm_cols = [c for c in COMMODITY_ASSETS if c in df.columns]
    comm_pct = (df[comm_cols] / df[comm_cols].iloc[0] - 1.0) * 100.0
    for col in comm_cols:
        st = DRIVER_STYLES[col]
        unit = ASSET_METADATA[col]["unit"]
        custom = np.column_stack([df[col].to_numpy(), np.full(len(df), unit)])
        fig_drv.add_trace(
            go.Scatter(
                x=df.index,
                y=comm_pct[col].round(2),
                mode="lines",
                name=col,
                line=dict(color=st["color"], width=st["lw"]),
                customdata=custom,
                hovertemplate=(
                    f"<b>{col}</b>: %{{y:+.2f}}%<br>"
                    "Precio: %{customdata[0]:.2f} %{customdata[1]}<extra></extra>"
                ),
            ),
            secondary_y=False,
        )
    if "US 10Y Yield" in df.columns:
        st_r = DRIVER_STYLES["US 10Y Yield"]
        fig_drv.add_trace(
            go.Scatter(
                x=df.index,
                y=df["US 10Y Yield"].round(3),
                mode="lines",
                name="US 10Y Yield (%)",
                line=dict(color=st_r["color"], width=st_r["lw"], dash="dash"),
                hovertemplate="<b>US 10Y Yield</b>: %{y:.2f}%<extra></extra>",
            ),
            secondary_y=True,
        )
        fig_drv.update_yaxes(
            title_text="Tasa US 10Y (%)",
            ticksuffix="%",
            tickformat=".2f",
            range=_padded_range(df["US 10Y Yield"].to_numpy(), pad_frac=0.12, min_pad=0.1),
            ticklabelstandoff=6,
            secondary_y=True,
        )

    fig_drv.add_hline(y=0, line_dash="dot", line_color="#9ca3af", line_width=1.1, secondary_y=False)
    fig_drv.update_layout(
        title=dict(
            text="<b>2. Drivers Globales: Commodities (% Acum.) y Tasa US 10Y (%)</b>",
            x=0.01,
            y=0.96,
            yanchor="top",
            font=dict(size=14),
        ),
        template="plotly_white",
        height=465,
        margin=dict(t=130, l=72, r=72, b=54),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.14, xanchor="left", x=0.0),
        xaxis=dict(
            rangeselector=dict(buttons=range_buttons, bgcolor="#f1f5f9", activecolor="#1d4ed8", y=1.02),
            ticklabelstandoff=6,
            automargin=True,
        ),
    )
    fig_drv.update_yaxes(
        title_text="Commodities (%)",
        ticksuffix="%",
        range=_padded_range(comm_pct.to_numpy(), pad_frac=0.14, min_pad=3.0),
        ticklabelstandoff=8,
        automargin=True,
        secondary_y=False,
    )

    # --- 3) Ranking Interactivo por Horizonte + Anomalía Z-Score ---
    fig_bar = go.Figure()
    price_summary = summary_df[~summary_df["is_rate"]].copy()
    horizons = [
        ("YTD (%)", "var_ytd_num", "%"),
        ("5 Días (%)", "var_5d_num", "%"),
        ("1 Día (%)", "var_1d_num", "%"),
        ("1 Año (%)", "var_1y_num", "%"),
        ("Posición 52S (%)", "pos_52w_pct", "%"),
        ("Z-Score 1D (σ)", "z_score_1d", "σ"),
    ]
    horizon_ranges: list[list[float]] = []
    for idx, (label, col_key, suffix) in enumerate(horizons):
        subset = price_summary[~price_summary["is_index"]].copy() if col_key == "z_score_1d" else price_summary
        ordered = subset.sort_values(col_key, ascending=True)
        vals = ordered[col_key].to_numpy(dtype=float)

        if col_key == "pos_52w_pct":
            colors = ["#0ea5e9" for _ in vals]
            text_vals = [f"{v:.0f}% (52S)" for v in vals]
            x_range = [0.0, 122.0]
        elif col_key == "z_score_1d":
            colors = ["#b91c1c" if abs(v) >= 2.0 else "#475569" for v in vals]
            text_vals = [f"{v:+.2f}σ" for v in vals]
            vmin = min(-2.5, float(vals.min()))
            vmax = max(2.5, float(vals.max()))
            span = max(vmax - vmin, 4.0)
            x_range = [vmin - span * 0.25, vmax + span * 0.25]
        else:
            colors = [
                "#64748b" if bool(is_idx) else ("#2563eb" if v >= 0 else "#dc2626")
                for v, is_idx in zip(vals, ordered["is_index"])
            ]
            text_vals = [f"{v:+.2f}{suffix}" for v in vals]
            vmin = min(0.0, float(vals.min()))
            vmax = max(0.0, float(vals.max()))
            span = max(vmax - vmin, 5.0)
            pad_left = span * 0.34 if vmin < 0 else span * 0.08
            pad_right = span * 0.30 if vmax > 0 else span * 0.08
            x_range = [vmin - pad_left, vmax + pad_right]

        horizon_ranges.append(x_range)
        fig_bar.add_trace(
            go.Bar(
                x=vals,
                y=ordered["Activo"],
                orientation="h",
                name=label,
                visible=(idx == 0),
                showlegend=False,
                marker_color=colors,
                text=text_vals,
                textposition="outside",
                cliponaxis=False,
                customdata=np.column_stack([ordered["Último"], ordered["Rango 52S"]]),
                hovertemplate=(
                    "<b>%{y}</b><br>"
                    f"{label}: <b>%{{x:+.2f}}{suffix}</b><br>"
                    "Último: %{customdata[0]:.3f}<br>"
                    "Rango 52S: %{customdata[1]}<extra></extra>"
                ),
            )
        )

    fig_bar.add_vline(x=0, line_color="#4b5563", line_width=1.1)
    horizon_buttons = [
        dict(
            label=label,
            method="update",
            args=[
                {"visible": [i == idx for i in range(len(horizons))]},
                {
                    "xaxis.range": horizon_ranges[idx],
                    "xaxis.ticksuffix": horizons[idx][2],
                },
            ],
        )
        for idx, (label, _, _) in enumerate(horizons)
    ]

    rate_rows = summary_df[summary_df["is_rate"]]
    rate_note = ""
    if not rate_rows.empty:
        r0 = rate_rows.iloc[0]
        rate_note = f"US 10Y Yield (bps): {r0['Último']:.2f}% | 1D: {r0['Var 1D']} | YTD: {r0['YTD']} | Z: {r0['Z-Score 1D']}"

    fig_bar.update_layout(
        title=dict(
            text=f"<b>3. Ranking de Desempeño y Anomalías</b><br><sup>{rate_note}</sup>",
            x=0.01,
            font=dict(size=14),
        ),
        updatemenus=[
            dict(
                type="buttons",
                direction="right",
                active=0,
                x=0.0,
                y=1.15,
                xanchor="left",
                yanchor="top",
                bgcolor="#f1f5f9",
                bordercolor="#cbd5e1",
                buttons=horizon_buttons,
            )
        ],
        template="plotly_white",
        height=465,
        margin=dict(t=115, l=100, r=28, b=48),
        xaxis=dict(range=horizon_ranges[0], ticksuffix="%", ticklabelstandoff=6),
        yaxis=dict(ticklabelstandoff=8, automargin=True),
    )

    # --- 4) Heatmap de Correlación ---
    fig_corr = go.Figure(
        data=go.Heatmap(
            z=corr_matrix.values,
            x=list(corr_matrix.columns),
            y=list(corr_matrix.index),
            zmin=-1,
            zmax=1,
            colorscale="RdBu",
            reversescale=True,
            text=corr_matrix.values,
            texttemplate="%{text:.2f}",
            hovertemplate="%{y} vs %{x}<br>Correlación (60 días hábiles): <b>%{z:.2f}</b><extra></extra>",
            colorbar=dict(title="r", thickness=14, len=0.88),
        )
    )
    fig_corr.update_layout(
        title=dict(
            text="<b>4. Correlación de Cambios Diarios (Últimos 60 Días Hábiles)</b><br><sup>Precios: retorno % | US 10Y: cambio diario (p.p.) | UI BCU excluida</sup>",
            x=0.01,
            y=0.96,
            yanchor="top",
            font=dict(size=14),
        ),
        template="plotly_white",
        height=465,
        margin=dict(t=88, l=102, r=75, b=82),
        xaxis=dict(tickangle=-30, ticklabelstandoff=6, automargin=True),
        yaxis=dict(autorange="reversed", ticklabelstandoff=8, automargin=True),
    )

    html_brief_alerts = _build_brief_and_alerts_html(brief, alerts)
    html_table = _build_html_table(summary_df)
    div_fx = fig_fx.to_html(full_html=False, include_plotlyjs="cdn", config=plot_config)
    div_drv = fig_drv.to_html(full_html=False, include_plotlyjs=False, config=plot_config)
    div_bar = fig_bar.to_html(full_html=False, include_plotlyjs=False, config=plot_config)
    div_corr = fig_corr.to_html(full_html=False, include_plotlyjs=False, config=plot_config)

    sim_payload_json = json.dumps(_build_simulator_payload(summary_df))
    csv_export_text = df.to_csv(float_format="%.4f")
    csv_payload_json = json.dumps(csv_export_text)
    source_summary = " • ".join(f"{k}: {v}" for k, v in sources.items())

    html_doc = f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Monitor Macro & Riesgo Cambiario V2 — Uruguay / LatAm</title>
  <style>
    :root {{
      --bg: #f8fafc;
      --card: #ffffff;
      --border: #e2e8f0;
      --ink: #0f172a;
      --muted: #475569;
      --pos: #1d4ed8;
      --pos-bg: #eff6ff;
      --neg: #b91c1c;
      --neg-bg: #fef2f2;
      --warn: #b45309;
      --warn-bg: #fffbeb;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      padding: 24px;
      font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
      background: var(--bg);
      color: var(--ink);
      line-height: 1.45;
    }}
    main {{ max-width: 1460px; margin: 0 auto; display: flex; flex-direction: column; gap: 18px; }}
    header {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 18px 22px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 12px;
    }}
    header h1 {{ margin: 0 0 4px; font-size: 1.35rem; }}
    header p {{ margin: 0; color: var(--muted); font-size: 0.9rem; }}
    .btn-primary {{
      background: #0f172a;
      color: #ffffff;
      border: none;
      border-radius: 8px;
      padding: 9px 14px;
      font-size: 0.88rem;
      font-weight: 600;
      cursor: pointer;
    }}
    .btn-primary:hover {{ background: #1e293b; }}
    .card {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 16px 18px;
      box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
      overflow: hidden;
    }}
    .card h2 {{ margin: 0 0 12px; font-size: 1.02rem; color: var(--ink); }}
    .exec-grid, .grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 18px;
    }}
    .brief-list {{ margin: 0; padding-left: 18px; display: flex; flex-direction: column; gap: 8px; font-size: 0.92rem; }}
    .brief-list code {{ background: #f1f5f9; padding: 1px 5px; border-radius: 4px; font-size: 0.85em; }}
    .alert-list {{ display: flex; flex-direction: column; gap: 8px; }}
    .alert-item {{ border-radius: 8px; padding: 9px 12px; border-left: 4px solid; font-size: 0.88rem; }}
    .sev-high {{ background: var(--neg-bg); border-color: var(--neg); }}
    .sev-medium {{ background: var(--warn-bg); border-color: var(--warn); }}
    .sev-info {{ background: var(--pos-bg); border-color: var(--pos); }}
    .alert-top {{ display: flex; align-items: center; gap: 8px; margin-bottom: 2px; }}
    .badge {{
      font-size: 0.72rem;
      font-weight: 700;
      padding: 2px 6px;
      border-radius: 4px;
      background: rgba(15, 23, 42, 0.08);
    }}
    .alert-detail {{ color: var(--muted); }}
    .alert-action {{ margin-top: 2px; font-weight: 500; }}
    .sim-toolbar {{ display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 14px; }}
    .sim-btn {{
      background: #f1f5f9;
      color: var(--ink);
      border: 1px solid #cbd5e1;
      border-radius: 6px;
      padding: 6px 11px;
      font-size: 0.85rem;
      font-weight: 600;
      cursor: pointer;
    }}
    .sim-btn.active {{ background: #1d4ed8; color: #ffffff; border-color: #1d4ed8; }}
    .sim-body {{
      display: grid;
      grid-template-columns: 1fr 1fr 1fr;
      gap: 16px;
      align-items: start;
    }}
    .sim-group {{ background: #f8fafc; border: 1px solid var(--border); border-radius: 8px; padding: 12px; }}
    .sim-group h3 {{ margin: 0 0 10px; font-size: 0.9rem; }}
    .sim-row {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; gap: 8px; font-size: 0.86rem; }}
    .sim-row input[type="number"] {{ width: 72px; padding: 4px 6px; border: 1px solid #cbd5e1; border-radius: 6px; text-align: right; }}
    .sim-note {{ font-size: 0.78rem; color: var(--muted); margin-top: 4px; }}
    .kpi-grid {{ display: grid; grid-template-columns: 1fr; gap: 8px; }}
    .kpi {{ border-radius: 8px; padding: 10px 12px; border: 1px solid var(--border); background: #ffffff; }}
    .kpi-lbl {{ font-size: 0.78rem; color: var(--muted); }}
    .kpi-val {{ font-size: 1.25rem; font-weight: 700; margin-top: 2px; }}
    .table-wrap {{ overflow-x: auto; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.88rem; font-variant-numeric: tabular-nums; }}
    th {{
      background: #0f172a;
      color: #ffffff;
      font-weight: 600;
      padding: 9px 10px;
      white-space: nowrap;
    }}
    td {{ padding: 8px 10px; border-bottom: 1px solid var(--border); white-space: nowrap; }}
    tbody tr:nth-child(even) {{ background: #f8fafc; }}
    th.txt, td.txt {{ text-align: left; }}
    th.num, td.num {{ text-align: right; }}
    td.fw {{ font-weight: 600; }}
    td.muted {{ color: var(--muted); }}
    td.pos {{ color: var(--pos); background: var(--pos-bg); font-weight: 600; }}
    td.neg {{ color: var(--neg); background: var(--neg-bg); font-weight: 600; }}
    td.anom {{ color: var(--warn); background: var(--warn-bg); font-weight: 700; }}
    footer {{ text-align: center; color: var(--muted); font-size: 0.82rem; padding: 6px 0; }}
    @media (max-width: 1024px) {{
      body {{ padding: 14px; }}
      .exec-grid, .grid, .sim-body {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <h1>🌎 Monitor Macro &amp; Riesgo Cambiario V2 — Uruguay / LatAm</h1>
        <p>Cierre al <strong>{html.escape(last_date_str)}</strong> • Alertas estadísticas, cruce BRL/UYU, UI BCU y simulador de impacto en márgenes</p>
      </div>
      <button type="button" class="btn-primary" id="download-csv-btn">📥 Descargar Histórico CSV</button>
    </header>

    {html_brief_alerts}

    <section class="card">
      <h2>🧮 Simulador de Impacto Cambiario en Costos y Márgenes</h2>
      <div class="sim-toolbar">
        <span style="font-size:0.86rem;font-weight:600;color:#475569;">Perfil empresa:</span>
        <button type="button" class="sim-btn active" data-preset="importadora">Importadora UY</button>
        <button type="button" class="sim-btn" data-preset="exportadora">Exportadora UY</button>
        <button type="button" class="sim-btn" data-preset="brasil">Competencia Brasil</button>
        <span style="font-size:0.86rem;font-weight:600;color:#475569;margin-left:12px;">Horizonte:</span>
        <select id="sim-horizon" style="padding:5px 8px;border:1px solid #cbd5e1;border-radius:6px;font-size:0.86rem;">
          <option value="5d">Últimos 5 días</option>
          <option value="ytd" selected>Año corrido (YTD)</option>
          <option value="1y">Último año (1A)</option>
        </select>
      </div>
      <div class="sim-body">
        <div class="sim-group">
          <h3>Estructura de Costos (% total)</h3>
          <div class="sim-row"><label for="c-usd">Costos en USD (%)</label><input id="c-usd" type="number" min="0" max="100" value="75" /></div>
          <div class="sim-row"><label for="c-brl">Costos en BRL (%)</label><input id="c-brl" type="number" min="0" max="100" value="0" /></div>
          <div class="sim-row"><label for="c-ui">Costos locales en UYU/UI (%)</label><input id="c-ui" type="number" min="0" max="100" value="25" /></div>
          <div class="sim-note" id="c-sum-note">Suma: 100% (ajustado a pesos uruguayos vía USD/UYU, BRL/UYU y UI BCU)</div>
        </div>
        <div class="sim-group">
          <h3>Estructura de Ingresos (% total)</h3>
          <div class="sim-row"><label for="r-usd">Ingresos en USD (%)</label><input id="r-usd" type="number" min="0" max="100" value="0" /></div>
          <div class="sim-row"><label for="r-brl">Ingresos en BRL (%)</label><input id="r-brl" type="number" min="0" max="100" value="0" /></div>
          <div class="sim-row"><label for="r-uyu">Ingresos en UYU fijos (%)</label><input id="r-uyu" type="number" min="0" max="100" value="100" /></div>
          <div class="sim-note" id="r-sum-note">Suma: 100% (mide variación en UYU nominal sin reajuste de precios)</div>
        </div>
        <div class="kpi-grid">
          <div class="kpi"><div class="kpi-lbl">Variación estimada de Costos (en UYU)</div><div class="kpi-val" id="kpi-cost">--</div></div>
          <div class="kpi"><div class="kpi-lbl">Variación estimada de Ingresos (en UYU)</div><div class="kpi-val" id="kpi-rev">--</div></div>
          <div class="kpi"><div class="kpi-lbl">Efecto neto estimado sobre Margen</div><div class="kpi-val" id="kpi-margin">--</div><div class="sim-note" id="kpi-msg"></div></div>
        </div>
      </div>
    </section>

    <section class="card">
      <h2>📊 Resumen Ejecutivo de Mercado (Volatilidad 20D, Z-Score y Rango 52S)</h2>
      {html_table}
    </section>

    <section class="grid">
      <div class="card">{div_fx}</div>
      <div class="card">{div_drv}</div>
      <div class="card">{div_bar}</div>
      <div class="card">{div_corr}</div>
    </section>

    <footer>
      Fuentes: {html.escape(source_summary)} • Atribución BCU/UI: Datos de <a href="https://datosuruguay.com" target="_blank" rel="noopener">datosUruguay.com</a> (CC-BY-4.0) • Uso informativo y de análisis.
    </footer>
  </main>

  <script>
    const SIM_DATA = {sim_payload_json};
    const CSV_TEXT = {csv_payload_json};
    const PRESETS = {{
      importadora: {{ cUsd: 75, cBrl: 0, cUi: 25, rUsd: 0, rBrl: 0, rUyu: 100 }},
      exportadora: {{ cUsd: 35, cBrl: 0, cUi: 65, rUsd: 90, rBrl: 0, rUyu: 10 }},
      brasil:      {{ cUsd: 20, cBrl: 45, cUi: 35, rUsd: 0, rBrl: 0, rUyu: 100 }},
    }};

    function val(id) {{ return Math.max(0, Number(document.getElementById(id).value) || 0); }}

    function recalcSim() {{
      const h = document.getElementById("sim-horizon").value;
      const cUsd = val("c-usd"), cBrl = val("c-brl"), cUi = val("c-ui");
      const rUsd = val("r-usd"), rBrl = val("r-brl"), rUyu = val("r-uyu");
      const cSum = cUsd + cBrl + cUi || 1;
      const rSum = rUsd + rBrl + rUyu || 1;

      document.getElementById("c-sum-note").textContent = "Suma ingresada: " + (cUsd + cBrl + cUi).toFixed(0) + "% (normalizado al 100%)";
      document.getElementById("r-sum-note").textContent = "Suma ingresada: " + (rUsd + rBrl + rUyu).toFixed(0) + "% (normalizado al 100%)";

      const dUsd = SIM_DATA.usd_uyu[h] || 0;
      const dBrl = SIM_DATA.brl_uyu[h] || 0;
      const dUi  = SIM_DATA.ui_bcu[h] || 0;

      const costPct = (cUsd / cSum) * dUsd + (cBrl / cSum) * dBrl + (cUi / cSum) * dUi;
      const revPct  = (rUsd / rSum) * dUsd + (rBrl / rSum) * dBrl + (rUyu / rSum) * 0;
      const netEffect = (((1 + revPct / 100) / (1 + costPct / 100)) - 1) * 100;

      const kpiCost = document.getElementById("kpi-cost");
      const kpiRev = document.getElementById("kpi-rev");
      const kpiMargin = document.getElementById("kpi-margin");
      const kpiMsg = document.getElementById("kpi-msg");

      kpiCost.textContent = (costPct >= 0 ? "+" : "") + costPct.toFixed(2) + "%";
      kpiCost.style.color = costPct > 0 ? "#b91c1c" : "#1d4ed8";
      kpiRev.textContent = (revPct >= 0 ? "+" : "") + revPct.toFixed(2) + "%";
      kpiRev.style.color = revPct >= 0 ? "#1d4ed8" : "#b91c1c";
      kpiMargin.textContent = (netEffect >= 0 ? "+" : "") + netEffect.toFixed(2) + " p.p.";
      kpiMargin.style.color = netEffect >= 0 ? "#15803d" : "#b91c1c";

      if (netEffect < -1.0) {{
        kpiMsg.textContent = "Presión negativa sobre margen: evaluar traslado a precios o cobertura cambiaria.";
      }} else if (netEffect > 1.0) {{
        kpiMsg.textContent = "Efecto favorable en margen por evolución relativa de ingresos vs. costos.";
      }} else {{
        kpiMsg.textContent = "Impacto acotado en el horizonte seleccionado.";
      }}
    }}

    document.querySelectorAll(".sim-btn").forEach((btn) => {{
      btn.addEventListener("click", () => {{
        document.querySelectorAll(".sim-btn").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        const p = PRESETS[btn.dataset.preset];
        document.getElementById("c-usd").value = p.cUsd;
        document.getElementById("c-brl").value = p.cBrl;
        document.getElementById("c-ui").value = p.cUi;
        document.getElementById("r-usd").value = p.rUsd;
        document.getElementById("r-brl").value = p.rBrl;
        document.getElementById("r-uyu").value = p.rUyu;
        recalcSim();
      }});
    }});

    ["c-usd", "c-brl", "c-ui", "r-usd", "r-brl", "r-uyu", "sim-horizon"].forEach((id) => {{
      document.getElementById(id).addEventListener("input", recalcSim);
      document.getElementById(id).addEventListener("change", recalcSim);
    }});

    document.getElementById("download-csv-btn").addEventListener("click", () => {{
      const blob = new Blob([CSV_TEXT], {{ type: "text/csv;charset=utf-8;" }});
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "macro_history_{html.escape(last_date_str)}.csv";
      a.click();
      URL.revokeObjectURL(url);
    }});

    recalcSim();
  </script>
</body>
</html>
"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_doc)


def update_readme(
    summary_df: pd.DataFrame,
    alerts: list[dict[str, str]],
    brief: list[str],
    sources: dict[str, str],
    readme_path: str = README_PATH,
) -> None:
    """Write V2 executive README.md with Morning Brief, alerts, table, charts, and documentation."""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    markdown_table = format_markdown_summary(summary_df).to_markdown(index=False)
    brief_md = "\n".join(f"- {b}" for b in brief)
    alerts_md = "\n".join(
        f"- **[{a['severity'].upper()}] {a['title']}:** {a['detail']} *({a['action']})*"
        for a in alerts[:5]
    )
    sources_md = " | ".join(f"**{k}**: {v}" for k, v in sources.items())

    content = f"""# 🌎 Monitor Macroeconómico & Riesgo Cambiario V2 (Uruguay / LatAm)

Pipeline automatizado en Python orientado a **decisión financiera y gestión de costos empresariales** en Uruguay y la región: combina mercado internacional (`yfinance`) con datos oficiales del **Banco Central del Uruguay (UI y BRL/UYU)**, detección estadística de anomalías (`Z-Score`), alertas accionables, histórico en CSV y un **simulador interactivo de impacto en márgenes**.

*Última actualización automática: **{timestamp}***

> **📊 Versión interactiva + Simulador de Márgenes:** abrí [`docs/index.html`](./docs/index.html) (o activá **GitHub Pages → `/docs`** en este repositorio).  
> **📁 Histórico para Excel / Power BI:** [`data/macro_history.csv`](./data/macro_history.csv)

---

## 📝 Morning Brief Ejecutivo
{brief_md}

## 🚨 Radar de Alertas del Día
{alerts_md}

---

## 📊 Resumen de Mercado
{markdown_table}

## 📈 Tablero Ejecutivo (4 Vistas)
![Dashboard Macro](./output/macro_dashboard.png)

---

## ⚙️ Arquitectura V2

```text
Yahoo Finance (yfinance) + BCU vía datosUruguay.com (UI y BRL/UYU)
        │
        ▼
  src/extract.py   ──▶ Descarga + enriquecimiento local (fallback automático)
        │
        ▼
  src/analyze.py   ──▶ % / bps, Vol 20D, Z-Score, Alertas, Brief y data/macro_history.csv
        │
        ▼
  src/report.py    ──▶ output/macro_dashboard.png + docs/index.html (Simulador) + README.md
        │              (+ notificaciones automáticas WhatsApp / Slack / Telegram en CI)
        ▲
GitHub Actions (.github/workflows/update_macro.yml — Lun–Vie 21:30 UTC)
```

## 📐 Criterios Metodológicos
- **Tasas vs. Precios:** `US 10Y Yield` (`^TNX`) reporta variaciones en **puntos básicos (`bps`)**; monedas, índices y commodities reportan variaciones porcentuales (`%`).
- **Competitividad Bilateral & Costos Locales:** incorpora `BRL/UYU` (pesos uruguayos por 1 real) y la **Unidad Indexada (`UI BCU`)** para medir brecha real entre dólar e inflación local indexada.
- **Volatilidad y Anomalías (`Z-Score 1D`):** mide la desviación estándar anualizada de 20 días hábiles y marca movimientos diarios atípicos (`|Z| ≥ 2.0σ`) o rupturas de **Rango 52S**.
- **Correlaciones (60 días hábiles):** calculadas sobre cambios diarios observados de activos de mercado (`pct_change()` en precios, `diff()` en tasas), excluyendo `UI (BCU)` por ser una interpolación diaria de inflación pasada.
- **Fuentes y Atribución:** {sources_md}. Datos oficiales del BCU consumidos vía [datosUruguay.com](https://datosuruguay.com) bajo licencia CC-BY-4.0; `USD/ARS` (`ARS=X`) refleja tipo de cambio oficial mayorista.

## 🔔 Notificaciones Automáticas (WhatsApp, Slack y Telegram)

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate | Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt
pytest
python src/report.py
```

Para activar envíos automáticos en GitHub Actions (**Settings → Secrets and variables → Actions**):

- **WhatsApp diario al cierre (Lun–Vie con cierres clave, alertas y link al tablero):**
  - *Vía Twilio WhatsApp:* `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_TO` (ej. `+59899123456`, admite múltiples separados por coma) y opcional `TWILIO_WHATSAPP_FROM` (por defecto usa Twilio Sandbox `whatsapp:+14155238886`).
  - *Vía Webhook externo (Evolution API, Make, Zapier o n8n para chats o grupos):* `WHATSAPP_WEBHOOK_URL` y opcionales `WHATSAPP_WEBHOOK_TOKEN` / `WHATSAPP_WEBHOOK_TO`.
  - *Opcional:* `DASHBOARD_URL` si querés fijar un enlace distinto al de GitHub Pages del repositorio.
- **Slack / Telegram (solo cuando saltan alertas `HIGH`/`MEDIUM`):** `SLACK_WEBHOOK_URL` o `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`.

---
*Desarrollado con Python (`yfinance`, `pandas`, `requests`, `matplotlib`, `seaborn`, `plotly`, `pytest`) y automatizado con GitHub Actions.*
"""
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(content)


if __name__ == "__main__":
    data, raw_data, data_sources = fetch_macro_bundle(period="1y")
    save_history_snapshot(data, HISTORY_CSV)
    metrics = compute_summary_metrics(data)
    corr = compute_correlations(data, window=60, raw_df=raw_data)
    active_alerts = detect_alerts(metrics)
    morning_brief = generate_morning_brief(metrics, active_alerts)
    generate_chart(data, metrics, corr)
    generate_interactive_dashboard(data, metrics, corr, active_alerts, morning_brief, data_sources)
    update_readme(metrics, active_alerts, morning_brief, data_sources)
    send_optional_alerts(
        active_alerts,
        morning_brief,
        data.index.max().strftime("%Y-%m-%d"),
        summary_df=metrics,
    )
    print("Tablero macro V2 actualizado exitosamente (estático + interactivo + histórico).")