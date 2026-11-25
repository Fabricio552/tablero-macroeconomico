# 🌎 Tablero Macroeconómico Regional (Uruguay / LatAm)

Pipeline automatizado en Python que monitorea diariamente las principales variables cambiarias regionales, tasas de referencia de EE. UU. y commodities relevantes para Uruguay y LatAm.

*Última actualización automática: **2026-11-25 04:25 UTC***

> **📊 Versión interactiva:** abrí [`docs/index.html`](./docs/index.html) en tu navegador (o activá **GitHub Pages → `/docs`** en este repositorio para ver el tablero online con zoom, tooltips, filtros `1M / 3M / 6M / YTD / 1A` y selector de horizonte).

---

## 📊 Resumen de Mercado
| Activo       | Unidad        |   Último | Var 1D   | Var 5D    | YTD       | 1A        | Rango 52S                |
|:-------------|:--------------|---------:|:---------|:----------|:----------|:----------|:-------------------------|
| USD/UYU      | UYU           |    40.72 | +3.78%   | +3.47%    | +5.35%    | +3.70%    | 36.92 – 40.72 (100%)     |
| USD/BRL      | BRL           |     5.9  | -0.43%   | +2.18%    | +7.79%    | +9.58%    | 4.91 – 5.95 (96%)        |
| USD/ARS      | ARS (Oficial) |  1592    | +0.76%   | +2.56%    | +9.68%    | +11.77%   | 1354.73 – 1592.00 (100%) |
| US 10Y Yield | % anual       |     4.9  | +0.0 bps | -16.2 bps | +74.1 bps | +90.2 bps | 3.96 – 5.31 (70%)        |
| WTI Oil      | USD/bbl       |    80.78 | +0.00%   | -2.98%    | +40.68%   | +39.40%   | 55.27 – 112.95 (44%)     |
| Gold         | USD/oz        |  3548.9  | +0.00%   | -5.16%    | -18.25%   | -14.28%   | 3515.40 – 5318.40 (2%)   |
| DXY          | Índice        |   103.98 | +0.00%   | +0.11%    | +5.80%    | +4.33%    | 96.22 – 104.32 (96%)     |

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
