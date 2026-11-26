# 🌎 Monitor Macroeconómico & Riesgo Cambiario V2 (Uruguay / LatAm)

Pipeline automatizado en Python orientado a **decisión financiera y gestión de costos empresariales** en Uruguay y la región: combina mercado internacional (`yfinance`) con datos oficiales del **Banco Central del Uruguay (UI y BRL/UYU)**, detección estadística de anomalías (`Z-Score`), alertas accionables, histórico en CSV y un **simulador interactivo de impacto en márgenes**.

*Última actualización automática: **2026-11-26 19:12 UTC***

> **📊 Versión interactiva + Simulador de Márgenes:** abrí [`docs/index.html`](./docs/index.html) (o activá **GitHub Pages → `/docs`** en este repositorio).  
> **📁 Histórico para Excel / Power BI:** [`data/macro_history.csv`](./data/macro_history.csv)

---

## 📝 Morning Brief Ejecutivo
- **Frente cambiario UY/Brasil:** `USD/UYU` cerró en **40.77** (+0.00% 1D | +4.43% YTD | pos. 52S: 100%) y el cruce bilateral **BRL/UYU** en **7.22** (-3.34% YTD), frente a un dólar global (**DXY**) en **+5.59% YTD**.
- **Costos locales vs. Dólar:** la **UI (BCU)** acumula **+4.57% YTD** vs. **+4.43% YTD** del `USD/UYU` (brecha real **-0.14 p.p.**, dólar por debajo de la UI (atraso cambiario real)).
- **Drivers globales (financiamiento y energía):** Tasa US 10Y en **4.85%** (+68.5 bps YTD) • WTI en **$84.97** (+47.98% YTD) • Oro en **$3594.9** (-17.19% YTD).
- **Alertas activas (7):** USD/UYU en máximo anual (100% del rango 52S); Movimiento diario atípico en USD/BRL (-2.80%); USD/ARS en máximo anual (100% del rango 52S).

## 🚨 Radar de Alertas del Día
- **[HIGH] USD/UYU en máximo anual (100% del rango 52S):** Cierre en 40.77 (+4.43% YTD). *(Revisar cobertura cambiaria, costos de reposición o ajuste de listas de precios.)*
- **[HIGH] Movimiento diario atípico en USD/BRL (-2.80%):** Desvío de -4.5σ respecto a su volatilidad de últimos 20 días hábiles. *(Validar si responde a shock global (DXY/US 10Y) o evento puntual antes de fijar precio.)*
- **[HIGH] USD/ARS en máximo anual (100% del rango 52S):** Cierre en 1601.0 (+10.30% YTD). *(Revisar cobertura cambiaria, costos de reposición o ajuste de listas de precios.)*
- **[MEDIUM] BRL/UYU en piso anual (2% del rango 52S):** Cierre en 7.22 (-3.34% YTD). *(Evaluar oportunidad de compra o fijación de precios en niveles bajos.)*
- **[MEDIUM] Presión semanal acumulada en BRL/UYU (-4.93% en 5D):** Volatilidad 20D actual: 13.5%. *(Monitorear impacto en capital de trabajo y márgenes de la semana.)*

---

## 📊 Resumen de Mercado
| Activo       | Unidad        |    Último | Var 1D   | Var 5D    | YTD       | 1A        | Vol 20D   | Z-Score 1D   | Rango 52S                |
|:-------------|:--------------|----------:|:---------|:----------|:----------|:----------|:----------|:-------------|:-------------------------|
| USD/UYU      | UYU           |   40.77   | +0.00%   | +0.41%    | +4.43%    | +2.77%    | 2.1%      | -0.6σ        | 37.45 – 40.77 (100%)     |
| USD/BRL      | BRL           |    5.74   | -2.80%   | -2.43%    | +4.79%    | +6.68%    | 16.4%     | -4.5σ        | 4.91 – 5.95 (80%)        |
| BRL/UYU      | UYU/BRL       |    7.22   | +0.00%   | -4.93%    | -3.34%    | -6.32%    | 13.5%     | +0.7σ        | 7.19 – 8.38 (2%)         |
| USD/ARS      | ARS (Oficial) | 1601      | +0.53%   | +2.69%    | +10.30%   | +10.61%   | 5.0%      | +1.2σ        | 1354.73 – 1601.00 (100%) |
| UI (BCU)     | UYU/UI        |    6.7172 | +0.02%   | +0.14%    | +4.57%    | +4.82%    | 0.2%      | n/a          | 6.41 – 6.72 (100%)       |
| DXY          | Índice        |  103.77   | +0.10%   | -0.12%    | +5.59%    | +4.19%    | 5.8%      | +0.1σ        | 96.22 – 104.32 (93%)     |
| WTI Oil      | USD/bbl       |   84.97   | +1.54%   | +2.12%    | +47.98%   | +44.88%   | 51.6%     | +0.8σ        | 55.27 – 112.95 (51%)     |
| Gold         | USD/oz        | 3594.9    | +1.67%   | -2.46%    | -17.19%   | -13.69%   | 35.4%     | +1.1σ        | 3515.40 – 5318.40 (4%)   |
| US 10Y Yield | % anual       |    4.85   | +0.0 bps | -20.4 bps | +68.5 bps | +85.0 bps | 6.0 bps/d | +0.2σ        | 3.96 – 5.31 (66%)        |

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
- **Fuentes y Atribución:** **market**: Yahoo Finance (yfinance) | **usd_uyu**: BCU oficial (vía datosUruguay.com) | **brl_uyu**: BCU oficial (vía datosUruguay.com) | **ui_bcu**: BCU oficial (vía datosUruguay.com). Datos oficiales del BCU consumidos vía [datosUruguay.com](https://datosuruguay.com) bajo licencia CC-BY-4.0; `USD/ARS` (`ARS=X`) refleja tipo de cambio oficial mayorista.

## 🔔 Notificaciones Automáticas (WhatsApp, Slack y Telegram)

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate | Linux/Mac: source .venv/bin/activate
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
