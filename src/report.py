import os
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
        format_markdown_summary,
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
        format_markdown_summary,
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
README_PATH = os.path.join(BASE_DIR, "README.md")

FX_STYLES = {
    "USD/UYU": {"color": "#1d4ed8", "ls": "-", "dash": "solid", "lw": 2.3, "label": "USD/UYU"},
    "USD/BRL": {"color": "#d97706", "ls": "-", "dash": "solid", "lw": 2.0, "label": "USD/BRL"},
    "USD/ARS": {"color": "#0f766e", "ls": "-", "dash": "solid", "lw": 1.8, "label": "USD/ARS (Oficial)"},
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
    min_sep = span * 0.085

    sorted_entries = sorted(entries, key=lambda item: item[0])
    placed_y: list[float] = []
    for raw_y, _, _ in sorted_entries:
        y = raw_y
        if placed_y and (y - placed_y[-1]) < min_sep:
            y = placed_y[-1] + min_sep
        placed_y.append(y)

    # Pull down slightly if top label exceeds axis ceiling
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
            fontsize=8.5,
            fontweight="bold",
            color=color,
        )


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
        figsize=(16, 10.5),
        gridspec_kw={"hspace": 0.36, "wspace": 0.24},
    )
    ax_fx, ax_drv = axes[0, 0], axes[0, 1]
    ax_bar, ax_corr = axes[1, 0], axes[1, 1]

    last_date = df.index.max()
    date_span = last_date - df.index.min()

    # 1) Panel FX vs DXY (% acumulado 1A)
    fx_cols = [c for c in FX_ASSETS if c in df.columns]
    fx_pct = (df[fx_cols] / df[fx_cols].iloc[0] - 1.0) * 100.0
    end_labels_fx = []
    for col in fx_cols:
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
    ax_fx.set_title("1. Presión Cambiaria vs. Dólar Global (% Acum. 1A)", fontweight="bold", fontsize=11.5, pad=10)
    ax_fx.set_ylabel("Variación acumulada (%)")
    ax_fx.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
    ax_fx.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))
    ax_fx.set_xlim(df.index.min(), last_date + pd.Timedelta(days=max(int(date_span.days * 0.23), 24)))
    last_num = mdates.date2num(last_date)
    ax_fx.set_xticks([t for t in ax_fx.get_xticks() if mdates.date2num(df.index.min()) <= t <= last_num])
    ax_fx.legend(loc="upper left", frameon=True, facecolor="white", framealpha=0.9, fontsize=8.5)
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
    ax_drv.legend(lines_drv, labels_drv, loc="upper left", frameon=True, facecolor="white", framealpha=0.9, fontsize=8.5)

    # 3) Panel Desempeño YTD (%) y posición en rango 52S
    price_rows = summary_df[~summary_df["is_rate"]].sort_values("var_ytd_num", ascending=True)
    y_vals = price_rows["var_ytd_num"].to_numpy()
    colors_bar = ["#2563eb" if v >= 0 else "#dc2626" for v in y_vals]
    bars = ax_bar.barh(price_rows["Activo"], y_vals, color=colors_bar, height=0.58, alpha=0.9)
    ax_bar.axvline(0, color="#4b5563", linewidth=1.1)

    max_abs = max(float(np.abs(y_vals).max()) if len(y_vals) else 10.0, 5.0)
    ax_bar.set_xlim(-max_abs * 1.45, max_abs * 1.55)
    ax_bar.xaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
    ax_bar.set_title("3. Desempeño YTD (%) y Posición en Rango 52S", fontweight="bold", fontsize=11.5, pad=10)
    ax_bar.set_xlabel("Variación Año Corrido (%)")

    for bar, (_, row) in zip(bars, price_rows.iterrows()):
        val = float(row["var_ytd_num"])
        pos = float(row["pos_52w_pct"])
        offset = max_abs * 0.04
        x_txt = val + offset if val >= 0 else val - offset
        ha = "left" if val >= 0 else "right"
        ax_bar.text(
            x_txt,
            bar.get_y() + bar.get_height() / 2.0,
            f"{val:+.1f}%  [52S: {pos:.0f}%]",
            va="center",
            ha=ha,
            fontsize=8.5,
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
            fontsize=8.5,
            fontweight="bold",
            color="#5b21b6",
            bbox=dict(boxstyle="round,pad=0.35", facecolor="#f5f3ff", edgecolor="#c4b5fd"),
        )

    # 4) Panel Heatmap triangular inferior de correlaciones (sin fila/columna vacías)
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
        "Tablero Macroeconómico Regional — Uruguay / LatAm & Drivers Globales",
        fontsize=15,
        fontweight="bold",
        y=0.97,
        color="#111827",
    )
    fig.text(
        0.5,
        0.935,
        f"Cierre al {last_date.strftime('%Y-%m-%d')}  •  Precios en variación % | Tasa US 10Y en puntos básicos (bps)",
        ha="center",
        fontsize=10,
        color="#4b5563",
    )
    fig.text(
        0.5,
        0.015,
        "Fuente: Yahoo Finance (yfinance) • USD/ARS refleja tipo de cambio oficial (ARS=X) • Correlación: retorno % en precios y cambio diario en tasa US 10Y",
        ha="center",
        fontsize=8.5,
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
    """Render a clean responsive executive HTML table without overlapping legends."""
    import html

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
                if val.startswith("+"):
                    cls = "num pos"
                elif val.startswith("-"):
                    cls = "num neg"
                else:
                    cls = "num"
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


def generate_interactive_dashboard(
    df: pd.DataFrame,
    summary_df: pd.DataFrame,
    corr_matrix: pd.DataFrame,
    output_path: str = OUTPUT_HTML,
) -> None:
    """Generate a self-contained interactive Plotly HTML dashboard with clean card layout."""
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

    # --- 1) FX vs DXY ---
    fig_fx = go.Figure()
    fx_cols = [c for c in FX_ASSETS if c in df.columns]
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
                    "Spot: %{customdata[0]:.2f} %{customdata[1]}<extra></extra>"
                ),
            )
        )
    fig_fx.add_hline(y=0, line_dash="dot", line_color="#9ca3af", line_width=1.1)
    fig_fx.update_layout(
        title=dict(text="<b>1. Presión Cambiaria vs. Dólar Global (% Acum. 1A)</b>", x=0.01, y=0.96, yanchor="top", font=dict(size=14)),
        template="plotly_white",
        height=455,
        margin=dict(t=122, l=72, r=24, b=54),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.15, xanchor="left", x=0.0),
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
        title=dict(text="<b>2. Drivers Globales: Commodities (% Acum.) y Tasa US 10Y (%)</b>", x=0.01, y=0.96, yanchor="top", font=dict(size=14)),
        template="plotly_white",
        height=455,
        margin=dict(t=122, l=72, r=72, b=54),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.15, xanchor="left", x=0.0),
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

    # --- 3) Ranking Interactivo por Horizonte ---
    fig_bar = go.Figure()
    price_summary = summary_df[~summary_df["is_rate"]].copy()
    horizons = [
        ("YTD (%)", "var_ytd_num", "%"),
        ("5 Días (%)", "var_5d_num", "%"),
        ("1 Día (%)", "var_1d_num", "%"),
        ("1 Año (%)", "var_1y_num", "%"),
        ("Posición 52S (%)", "pos_52w_pct", "%"),
    ]
    horizon_ranges: list[list[float]] = []
    for idx, (label, col_key, suffix) in enumerate(horizons):
        ordered = price_summary.sort_values(col_key, ascending=True)
        vals = ordered[col_key].to_numpy(dtype=float)
        if col_key == "pos_52w_pct":
            colors = ["#0ea5e9" for _ in vals]
            text_vals = [f"{v:.0f}% (52S)" for v in vals]
            x_range = [0.0, 122.0]
        else:
            colors = ["#2563eb" if v >= 0 else "#dc2626" for v in vals]
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
                    f"{label}: <b>%{{x:+.2f}}%</b><br>"
                    "Último: %{customdata[0]:.2f}<br>"
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
                {"xaxis.range": horizon_ranges[idx]},
            ],
        )
        for idx, (label, _, _) in enumerate(horizons)
    ]

    rate_rows = summary_df[summary_df["is_rate"]]
    rate_note = ""
    if not rate_rows.empty:
        r0 = rate_rows.iloc[0]
        rate_note = f"US 10Y Yield (en bps): {r0['Último']:.2f}% | 1D: {r0['Var 1D']} | YTD: {r0['YTD']} | 52S: {r0['pos_52w_pct']:.0f}%"

    fig_bar.update_layout(
        title=dict(
            text=f"<b>3. Ranking de Desempeño Interactivo</b><br><sup>{rate_note}</sup>",
            x=0.01,
            font=dict(size=14),
        ),
        updatemenus=[
            dict(
                type="buttons",
                direction="right",
                active=0,
                x=0.0,
                y=1.14,
                xanchor="left",
                yanchor="top",
                bgcolor="#f1f5f9",
                bordercolor="#cbd5e1",
                buttons=horizon_buttons,
            )
        ],
        template="plotly_white",
        height=440,
        margin=dict(t=108, l=95, r=28, b=48),
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
            text="<b>4. Correlación de Cambios Diarios (Últimos 60 Días Hábiles)</b><br><sup>Precios: retorno % | Tasa US 10Y: cambio diario (p.p.)</sup>",
            x=0.01,
            y=0.96,
            yanchor="top",
            font=dict(size=14),
        ),
        template="plotly_white",
        height=455,
        margin=dict(t=88, l=100, r=75, b=78),
        xaxis=dict(tickangle=-30, ticklabelstandoff=6, automargin=True),
        yaxis=dict(autorange="reversed", ticklabelstandoff=8, automargin=True),
    )

    html_table = _build_html_table(summary_df)
    div_fx = fig_fx.to_html(full_html=False, include_plotlyjs="cdn", config=plot_config)
    div_drv = fig_drv.to_html(full_html=False, include_plotlyjs=False, config=plot_config)
    div_bar = fig_bar.to_html(full_html=False, include_plotlyjs=False, config=plot_config)
    div_corr = fig_corr.to_html(full_html=False, include_plotlyjs=False, config=plot_config)

    html_doc = f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Tablero Macroeconómico Regional — Uruguay / LatAm</title>
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
    main {{ max-width: 1440px; margin: 0 auto; display: flex; flex-direction: column; gap: 18px; }}
    header {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 18px 22px;
    }}
    header h1 {{ margin: 0 0 4px; font-size: 1.35rem; }}
    header p {{ margin: 0; color: var(--muted); font-size: 0.92rem; }}
    .card {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 14px 16px;
      box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
      overflow: hidden;
    }}
    .card h2 {{ margin: 0 0 10px; font-size: 1rem; color: var(--ink); }}
    .table-wrap {{ overflow-x: auto; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.9rem; font-variant-numeric: tabular-nums; }}
    th {{
      background: #0f172a;
      color: #ffffff;
      font-weight: 600;
      padding: 9px 12px;
      white-space: nowrap;
    }}
    td {{ padding: 8px 12px; border-bottom: 1px solid var(--border); white-space: nowrap; }}
    tbody tr:nth-child(even) {{ background: #f8fafc; }}
    th.txt, td.txt {{ text-align: left; }}
    th.num, td.num {{ text-align: right; }}
    td.fw {{ font-weight: 600; }}
    td.muted {{ color: var(--muted); }}
    td.pos {{ color: var(--pos); background: var(--pos-bg); font-weight: 600; }}
    td.neg {{ color: var(--neg); background: var(--neg-bg); font-weight: 600; }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 18px;
    }}
    @media (max-width: 1024px) {{
      body {{ padding: 14px; }}
      .grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>🌎 Tablero Macroeconómico Interactivo — Uruguay / LatAm</h1>
      <p>Cierre al <strong>{last_date_str}</strong> • Fuente: Yahoo Finance (yfinance) • Hacé clic en la leyenda para aislar series o usá los filtros temporales</p>
    </header>
    <section class="card">
      <h2>Resumen Ejecutivo de Mercado (Precios en % • Tasa US 10Y en bps)</h2>
      {html_table}
    </section>
    <section class="grid">
      <div class="card">{div_fx}</div>
      <div class="card">{div_drv}</div>
      <div class="card">{div_bar}</div>
      <div class="card">{div_corr}</div>
    </section>
  </main>
</body>
</html>
"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_doc)


def update_readme(summary_df: pd.DataFrame, readme_path: str = README_PATH) -> None:
    """Write executive README.md with metrics table, static charts, and technical documentation."""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    markdown_table = format_markdown_summary(summary_df).to_markdown(index=False)
    content = f"""# 🌎 Tablero Macroeconómico Regional (Uruguay / LatAm)

Pipeline automatizado en Python que monitorea diariamente las principales variables cambiarias regionales, tasas de referencia de EE. UU. y commodities relevantes para Uruguay y LatAm.

*Última actualización automática: **{timestamp}***

> **📊 Versión interactiva:** abrí [`docs/index.html`](./docs/index.html) en tu navegador (o activá **GitHub Pages → `/docs`** en este repositorio para ver el tablero online con zoom, tooltips, filtros `1M / 3M / 6M / YTD / 1A` y selector de horizonte).

---

## 📊 Resumen de Mercado
{markdown_table}

## 📈 Tablero Ejecutivo (4 Vistas)
![Dashboard Macro](./output/macro_dashboard.png)

---

## ⚙️ Arquitectura del Pipeline

```text
Yahoo Finance (yfinance)
        │
        ▼
  src/extract.py   ──▶ Descarga cierres diarios (reintentos + normalización de columnas)
        │
        ▼
  src/analyze.py   ──▶ Precios en % | Tasa US 10Y en bps | YTD vs. cierre año previo | Corr 60d
        │
        ▼
  src/report.py    ──▶ Genera output/macro_dashboard.png + docs/index.html + README.md
        │
        ▲
GitHub Actions (.github/workflows/update_macro.yml — Lun–Vie 21:30 UTC)
```

## 📐 Criterios Metodológicos
- **Tasas vs. Precios:** `US 10Y Yield` (`^TNX`) reporta variaciones en **puntos básicos (`bps`)**; monedas, índices y commodities reportan variaciones porcentuales (`%`).
- **Baseline YTD:** calcula el retorno año corrido respecto al **último cierre del año calendario anterior** (si la serie inicia en el año en curso, usa el primer registro disponible).
- **Correlaciones (60 días hábiles):** se calculan sobre cambios diarios observados sin ceros artificiales por feriados cruzados entre EE. UU. y LatAm (`pct_change()` para precios y `diff()` para la tasa `US 10Y`).
- **Alcance de fuentes:** los datos provienen de Yahoo Finance (`yfinance`); en particular, `USD/ARS` (`ARS=X`) refleja el tipo de cambio oficial mayorista.

## 🚀 Ejecución Local

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate | Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt
pytest
python src/report.py
```

---
*Desarrollado con Python (`yfinance`, `pandas`, `matplotlib`, `seaborn`, `plotly`, `pytest`) y automatizado con GitHub Actions.*
"""
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(content)


if __name__ == "__main__":
    data, raw_data = fetch_macro_bundle(period="1y")
    metrics = compute_summary_metrics(data)
    corr = compute_correlations(data, window=60, raw_df=raw_data)
    generate_chart(data, metrics, corr)
    generate_interactive_dashboard(data, metrics, corr)
    update_readme(metrics)
    print("Tablero macro actualizado exitosamente (estático + interactivo).")