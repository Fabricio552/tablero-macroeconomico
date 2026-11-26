# 🌎 Tablero Macroeconómico Regional (Uruguay / LatAm)

Pipeline automatizado en Python que monitorea diariamente las principales variables cambiarias regionales, tasas de referencia de EE. UU. y commodities relevantes para Uruguay y LatAm.

*Última actualización automática: **2026-11-26 03:42 UTC***

> **📊 Versión interactiva:** abrí [`docs/index.html`](./docs/index.html) en tu navegador (o activá **GitHub Pages → `/docs`** en este repositorio para ver el tablero online con zoom, tooltips, filtros `1M / 3M / 6M / YTD / 1A` y selector de horizonte).

---

## 📊 Resumen de Mercado
| Activo       | Unidad        |   Último | Var 1D   | Var 5D    | YTD       | 1A        | Rango 52S                |
|:-------------|:--------------|---------:|:---------|:----------|:----------|:----------|:-------------------------|
| USD/UYU      | UYU           |    39.24 | +0.00%   | -0.29%    | +1.52%    | +0.41%    | 36.92 – 40.21 (71%)      |
| USD/BRL      | BRL           |     5.9  | -0.41%   | +2.20%    | +7.81%    | +9.75%    | 4.91 – 5.95 (96%)        |
| USD/ARS      | ARS (Oficial) |  1592.49 | +0.79%   | +2.59%    | +9.71%    | +10.02%   | 1354.73 – 1592.49 (100%) |
| US 10Y Yield | % anual       |     4.85 | -5.6 bps | -21.8 bps | +68.5 bps | +85.0 bps | 3.96 – 5.31 (66%)        |
| WTI Oil      | USD/bbl       |    84.31 | +2.75%   | +1.26%    | +46.83%   | +43.75%   | 55.27 – 112.95 (50%)     |
| Gold         | USD/oz        |  3605    | +1.21%   | -3.66%    | -16.96%   | -13.45%   | 3515.40 – 5318.40 (5%)   |
| DXY          | Índice        |   103.81 | +0.00%   | -0.05%    | +5.63%    | +4.23%    | 96.22 – 104.32 (94%)     |

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
# Windows: .venv\Scripts\activate | Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt
pytest
python src/report.py
```

---
*Desarrollado con Python (`yfinance`, `pandas`, `matplotlib`, `seaborn`, `plotly`, `pytest`) y automatizado con GitHub Actions.*
