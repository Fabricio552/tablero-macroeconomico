# 🌎 Monitor Macroeconómico & Riesgo Cambiario V2 (Uruguay / LatAm)

Pipeline automatizado en Python orientado a **decisión financiera y gestión de costos empresariales** en Uruguay y la región: combina mercado internacional (`yfinance`) con datos oficiales del **Banco Central del Uruguay (UI y BRL/UYU)**, detección estadística de anomalías (`Z-Score`), alertas accionables, histórico en CSV y un **simulador interactivo de impacto en márgenes**.

*Última actualización automática: **2026-11-27 03:42 UTC***

> **📊 Versión interactiva + Simulador de Márgenes:** abrí [`docs/index.html`](./docs/index.html) (o activá **GitHub Pages → `/docs`** en este repositorio).  
> **📁 Histórico para Excel / Power BI:** [`data/macro_history.csv`](./data/macro_history.csv)

---

## 📝 Morning Brief Ejecutivo
- **Frente cambiario UY/Brasil:** `USD/UYU` cerró en **40.7** (+0.00% 1D | +4.24% YTD | pos. 52S: 98%) y el cruce bilateral **BRL/UYU** en **7.36** (-1.42% YTD), frente a un dólar global (**DXY**) en **+5.49% YTD**.
- **Costos locales vs. Dólar:** la **UI (BCU)** acumula **+4.59% YTD** vs. **+4.24% YTD** del `USD/UYU` (brecha real **-0.35 p.p.**, dólar por debajo de la UI (atraso cambiario real)).
- **Drivers globales (financiamiento y energía):** Tasa US 10Y en **4.85%** (+68.5 bps YTD) • WTI en **$85.78** (+49.39% YTD) • Oro en **$3655.9** (-15.78% YTD).
- **Alertas activas (3):** Movimiento diario atípico en USD/BRL (-2.93%); USD/ARS en máximo anual (99% del rango 52S); Presión semanal acumulada en USD/BRL (-4.76% en 5D).

## 🚨 Radar de Alertas del Día
- **[HIGH] Movimiento diario atípico en USD/BRL (-2.93%):** Desvío de -4.0σ respecto a su volatilidad de últimos 20 días hábiles. *(Validar si responde a shock global (DXY/US 10Y) o evento puntual antes de fijar precio.)*
- **[HIGH] USD/ARS en máximo anual (99% del rango 52S):** Cierre en 1601.0 (+10.30% YTD). *(Revisar cobertura cambiaria, costos de reposición o ajuste de listas de precios.)*
- **[MEDIUM] Presión semanal acumulada en USD/BRL (-4.76% en 5D):** Volatilidad 20D actual: 17.8%. *(Monitorear impacto en capital de trabajo y márgenes de la semana.)*

---

## 📊 Resumen de Mercado
| Activo       | Unidad        |    Último | Var 1D   | Var 5D   | YTD       | 1A        | Vol 20D   | Z-Score 1D   | Rango 52S               |
|:-------------|:--------------|----------:|:---------|:---------|:----------|:----------|:----------|:-------------|:------------------------|
| USD/UYU      | UYU           |   40.7    | +0.00%   | +0.16%   | +4.24%    | +3.11%    | 2.2%      | -0.4σ        | 37.45 – 40.77 (98%)     |
| USD/BRL      | BRL           |    5.65   | -2.93%   | -4.76%   | +3.20%    | +6.01%    | 17.8%     | -4.0σ        | 4.91 – 5.95 (72%)       |
| BRL/UYU      | UYU/BRL       |    7.36   | +0.00%   | -1.47%   | -1.42%    | -3.79%    | 16.1%     | +0.5σ        | 7.19 – 8.38 (14%)       |
| USD/ARS      | ARS (Oficial) | 1601      | -0.12%   | +2.32%   | +10.30%   | +10.21%   | 5.0%      | -1.0σ        | 1354.73 – 1603.00 (99%) |
| UI (BCU)     | UYU/UI        |    6.7185 | +0.02%   | +0.14%   | +4.59%    | +4.83%    | 0.2%      | n/a          | 6.41 – 6.72 (100%)      |
| DXY          | Índice        |  103.68   | +0.00%   | -0.13%   | +5.49%    | +4.09%    | 5.8%      | -0.2σ        | 96.22 – 104.32 (92%)    |
| WTI Oil      | USD/bbl       |   85.78   | +0.00%   | +2.14%   | +49.39%   | +46.26%   | 51.3%     | +0.2σ        | 55.27 – 112.95 (53%)    |
| Gold         | USD/oz        | 3655.9    | +0.00%   | +4.00%   | -15.78%   | -12.23%   | 35.8%     | +0.2σ        | 3515.40 – 5318.40 (8%)  |
| US 10Y Yield | % anual       |    4.85   | +0.0 bps | -6.4 bps | +68.5 bps | +85.0 bps | 5.9 bps/d | +0.1σ        | 3.96 – 5.31 (66%)       |

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
        │              (+ notificaciones automáticas Email / WhatsApp / Slack / Telegram en CI)
        ▲
GitHub Actions (.github/workflows/update_macro.yml — Lun–Vie 21:30 UTC)
```

## 📐 Criterios Metodológicos
- **Tasas vs. Precios:** `US 10Y Yield` (`^TNX`) reporta variaciones en **puntos básicos (`bps`)**; monedas, índices y commodities reportan variaciones porcentuales (`%`).
- **Competitividad Bilateral & Costos Locales:** incorpora `BRL/UYU` (pesos uruguayos por 1 real) y la **Unidad Indexada (`UI BCU`)** para medir brecha real entre dólar e inflación local indexada.
- **Volatilidad y Anomalías (`Z-Score 1D`):** mide la desviación estándar anualizada de 20 días hábiles y marca movimientos diarios atípicos (`|Z| ≥ 2.0σ`) o rupturas de **Rango 52S**.
- **Correlaciones (60 días hábiles):** calculadas sobre cambios diarios observados de activos de mercado (`pct_change()` en precios, `diff()` en tasas), excluyendo `UI (BCU)` por ser una interpolación diaria de inflación pasada.
- **Fuentes y Atribución:** **market**: Yahoo Finance (yfinance) | **usd_uyu**: BCU oficial (vía datosUruguay.com) | **brl_uyu**: BCU oficial (vía datosUruguay.com) | **ui_bcu**: BCU oficial (vía datosUruguay.com). Datos oficiales del BCU consumidos vía [datosUruguay.com](https://datosuruguay.com) bajo licencia CC-BY-4.0; `USD/ARS` (`ARS=X`) refleja tipo de cambio oficial mayorista.

## 🔔 Notificaciones Automáticas (Email, WhatsApp, Slack y Telegram)

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate | Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt
pytest
python src/report.py
```

Para activar envíos automáticos en GitHub Actions (**Settings → Secrets and variables → Actions**):

- **Email diario ejecutivo al cierre (Lun–Vie con tabla, alertas, Morning Brief, gráfico adjunto y link al tablero — Recomendado):**
  - *Gmail (2 pasos):* `EMAIL_FROM` (tu correo Gmail) y `EMAIL_PASSWORD` (**Contraseña de aplicación** de Google de 16 caracteres).
  - *Opcionales:* `EMAIL_TO` (si se omite, se envía al mismo `EMAIL_FROM`; admite varios correos separados por coma), `EMAIL_SMTP_HOST` (por defecto `smtp.gmail.com`), `EMAIL_SMTP_PORT` (por defecto `465` SSL; admite `587` STARTTLS) y `DASHBOARD_URL`.
- **WhatsApp diario al cierre (opcional):**
  - *CallMeBot:* `CALLMEBOT_PHONE` y `CALLMEBOT_APIKEY`.
  - *Twilio WhatsApp:* `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_TO` y opcional `TWILIO_WHATSAPP_FROM`.
  - *Webhook externo (Evolution API / Make / n8n):* `WHATSAPP_WEBHOOK_URL` y opcionales `WHATSAPP_WEBHOOK_TOKEN` / `WHATSAPP_WEBHOOK_TO`.
- **Slack / Telegram (solo cuando saltan alertas `HIGH`/`MEDIUM`):** `SLACK_WEBHOOK_URL` o `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`.

---
*Desarrollado con Python (`yfinance`, `pandas`, `requests`, `matplotlib`, `seaborn`, `plotly`, `pytest`) y automatizado con GitHub Actions.*
