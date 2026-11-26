# 🌎 Monitor Macroeconómico & Riesgo Cambiario V2 (Uruguay / LatAm)

Pipeline automatizado en Python orientado a **decisión financiera y gestión de costos empresariales** en Uruguay y la región: combina mercado internacional (`yfinance`) con datos oficiales del **Banco Central del Uruguay (UI y BRL/UYU)**, detección estadística de anomalías (`Z-Score`), alertas accionables, histórico en CSV y un **simulador interactivo de impacto en márgenes**.

*Última actualización automática: **2026-11-26 01:52 UTC***

> **📊 Versión interactiva + Simulador de Márgenes:** abrí [`docs/index.html`](./docs/index.html) (o activá **GitHub Pages → `/docs`** en este repositorio).  
> **📁 Histórico para Excel / Power BI:** [`data/macro_history.csv`](./data/macro_history.csv)

---

## 📝 Morning Brief Ejecutivo
- **Frente cambiario UY/Brasil:** `USD/UYU` cerró en **40.77** (+0.18% 1D | +4.43% YTD | pos. 52S: 100%) y el cruce bilateral **BRL/UYU** en **7.22** (-3.34% YTD), frente a un dólar global (**DXY**) en **+5.56% YTD**.
- **Costos locales vs. Dólar:** la **UI (BCU)** acumula **+4.55% YTD** vs. **+4.43% YTD** del `USD/UYU` (brecha real **-0.12 p.p.**, dólar por debajo de la UI (atraso cambiario real)).
- **Drivers globales (financiamiento y energía):** Tasa US 10Y en **4.85%** (+68.5 bps YTD) • WTI en **$83.98** (+46.26% YTD) • Oro en **$3584.0** (-17.44% YTD).
- **Alertas activas (8):** USD/UYU en máximo anual (100% del rango 52S); USD/ARS en máximo anual (100% del rango 52S); BRL/UYU en piso anual (2% del rango 52S).

## 🚨 Radar de Alertas del Día
- **[HIGH] USD/UYU en máximo anual (100% del rango 52S):** Cierre en 40.77 (+4.43% YTD). *(Revisar cobertura cambiaria, costos de reposición o ajuste de listas de precios.)*
- **[HIGH] USD/ARS en máximo anual (100% del rango 52S):** Cierre en 1592.49 (+9.71% YTD). *(Revisar cobertura cambiaria, costos de reposición o ajuste de listas de precios.)*
- **[MEDIUM] BRL/UYU en piso anual (2% del rango 52S):** Cierre en 7.22 (-3.34% YTD). *(Evaluar oportunidad de compra o fijación de precios en niveles bajos.)*
- **[MEDIUM] Movimiento diario atípico en BRL/UYU (-1.94%):** Desvío de -1.7σ respecto a su volatilidad de últimos 20 días hábiles. *(Validar si responde a shock global (DXY/US 10Y) o evento puntual antes de fijar precio.)*
- **[MEDIUM] Presión semanal acumulada en BRL/UYU (-5.02% en 5D):** Volatilidad 20D actual: 13.4%. *(Monitorear impacto en capital de trabajo y márgenes de la semana.)*

---

## 📊 Resumen de Mercado
| Activo       | Unidad        |    Último | Var 1D   | Var 5D    | YTD       | 1A        | Vol 20D   | Z-Score 1D   | Rango 52S                |
|:-------------|:--------------|----------:|:---------|:----------|:----------|:----------|:----------|:-------------|:-------------------------|
| USD/UYU      | UYU           |   40.77   | +0.18%   | +0.31%    | +4.43%    | +2.77%    | 2.1%      | +0.8σ        | 37.45 – 40.77 (100%)     |
| USD/BRL      | BRL           |    5.9    | -0.41%   | +2.20%    | +7.81%    | +9.75%    | 11.6%     | -1.2σ        | 4.91 – 5.95 (96%)        |
| BRL/UYU      | UYU/BRL       |    7.22   | -1.94%   | -5.02%    | -3.34%    | -6.32%    | 13.4%     | -1.7σ        | 7.19 – 8.38 (2%)         |
| USD/ARS      | ARS (Oficial) | 1592.49   | +0.79%   | +2.59%    | +9.71%    | +10.02%   | 4.8%      | +2.4σ        | 1354.73 – 1592.49 (100%) |
| UI (BCU)     | UYU/UI        |    6.7159 | +0.02%   | +0.14%    | +4.55%    | +4.80%    | 0.2%      | n/a          | 6.41 – 6.72 (100%)       |
| DXY          | Índice        |  103.75   | -0.06%   | -0.11%    | +5.56%    | +4.17%    | 5.8%      | -0.4σ        | 96.22 – 104.32 (93%)     |
| WTI Oil      | USD/bbl       |   83.98   | +2.35%   | +0.86%    | +46.26%   | +43.19%   | 51.2%     | +1.0σ        | 55.27 – 112.95 (50%)     |
| Gold         | USD/oz        | 3584      | +0.62%   | -4.22%    | -17.44%   | -13.95%   | 34.7%     | +0.6σ        | 3515.40 – 5318.40 (4%)   |
| US 10Y Yield | % anual       |    4.85   | -5.6 bps | -21.8 bps | +68.5 bps | +85.0 bps | 6.1 bps/d | -0.8σ        | 3.96 – 5.31 (66%)        |

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
        │              (+ alertas opcionales vía Slack / Telegram en CI)
        ▲
GitHub Actions (.github/workflows/update_macro.yml — Lun–Vie 21:30 UTC)
```

## 📐 Criterios Metodológicos
- **Tasas vs. Precios:** `US 10Y Yield` (`^TNX`) reporta variaciones en **puntos básicos (`bps`)**; monedas, índices y commodities reportan variaciones porcentuales (`%`).
- **Competitividad Bilateral & Costos Locales:** incorpora `BRL/UYU` (pesos uruguayos por 1 real) y la **Unidad Indexada (`UI BCU`)** para medir brecha real entre dólar e inflación local indexada.
- **Volatilidad y Anomalías (`Z-Score 1D`):** mide la desviación estándar anualizada de 20 días hábiles y marca movimientos diarios atípicos (`|Z| ≥ 2.0σ`) o rupturas de **Rango 52S**.
- **Correlaciones (60 días hábiles):** calculadas sobre cambios diarios observados de activos de mercado (`pct_change()` en precios, `diff()` en tasas), excluyendo `UI (BCU)` por ser una interpolación diaria de inflación pasada.
- **Fuentes y Atribución:** **market**: Yahoo Finance (yfinance) | **usd_uyu**: BCU oficial (vía datosUruguay.com) | **brl_uyu**: BCU oficial (vía datosUruguay.com) | **ui_bcu**: BCU oficial (vía datosUruguay.com). Datos oficiales del BCU consumidos vía [datosUruguay.com](https://datosuruguay.com) bajo licencia CC-BY-4.0; `USD/ARS` (`ARS=X`) refleja tipo de cambio oficial mayorista.

## 🔔 Alertas Opcionales (Slack / Telegram) y Ejecución Local

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate | Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt
pytest
python src/report.py
```

Para activar notificaciones automáticas en GitHub Actions cuando haya alertas `HIGH`/`MEDIUM`, configurá en **Settings → Secrets and variables → Actions** cualquiera de estas variables opcionales:
- `SLACK_WEBHOOK_URL`
- `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID`

---
*Desarrollado con Python (`yfinance`, `pandas`, `requests`, `matplotlib`, `seaborn`, `plotly`, `pytest`) y automatizado con GitHub Actions.*
