# 🌎 Monitor Macroeconómico & Riesgo Cambiario V2 (Uruguay / LatAm)

Pipeline automatizado en Python orientado a **decisión financiera y gestión de costos empresariales** en Uruguay y la región: combina mercado internacional (`yfinance`) con datos oficiales del **Banco Central del Uruguay (UI y BRL/UYU)**, detección estadística de anomalías (`Z-Score`), alertas accionables, histórico en CSV y un **simulador interactivo de impacto en márgenes**.

*Última actualización automática: **2026-11-26 21:33 UTC***

> **📊 Versión interactiva + Simulador de Márgenes:** abrí [`docs/index.html`](./docs/index.html) (o activá **GitHub Pages → `/docs`** en este repositorio).  
> **📁 Histórico para Excel / Power BI:** [`data/macro_history.csv`](./data/macro_history.csv)

---

## 📝 Morning Brief Ejecutivo
- **Frente cambiario UY/Brasil:** `USD/UYU` cerró en **40.7** (-0.18% 1D | +4.24% YTD | pos. 52S: 98%) y el cruce bilateral **BRL/UYU** en **7.36** (-1.42% YTD), frente a un dólar global (**DXY**) en **+5.59% YTD**.
- **Costos locales vs. Dólar:** la **UI (BCU)** acumula **+4.57% YTD** vs. **+4.24% YTD** del `USD/UYU` (brecha real **-0.33 p.p.**, dólar por debajo de la UI (atraso cambiario real)).
- **Drivers globales (financiamiento y energía):** Tasa US 10Y en **4.85%** (+68.5 bps YTD) • WTI en **$84.91** (+47.88% YTD) • Oro en **$3593.4** (-17.22% YTD).
- **Alertas activas (7):** Movimiento diario atípico en USD/BRL (-4.28%); Movimiento diario atípico en BRL/UYU (+1.98%); USD/ARS en máximo anual (100% del rango 52S).

## 🚨 Radar de Alertas del Día
- **[HIGH] Movimiento diario atípico en USD/BRL (-4.28%):** Desvío de -6.5σ respecto a su volatilidad de últimos 20 días hábiles. *(Validar si responde a shock global (DXY/US 10Y) o evento puntual antes de fijar precio.)*
- **[HIGH] Movimiento diario atípico en BRL/UYU (+1.98%):** Desvío de +3.1σ respecto a su volatilidad de últimos 20 días hábiles. *(Validar si responde a shock global (DXY/US 10Y) o evento puntual antes de fijar precio.)*
- **[HIGH] USD/ARS en máximo anual (100% del rango 52S):** Cierre en 1601.0 (+10.30% YTD). *(Revisar cobertura cambiaria, costos de reposición o ajuste de listas de precios.)*
- **[MEDIUM] Presión semanal acumulada en USD/BRL (-3.92% en 5D):** Volatilidad 20D actual: 20.5%. *(Monitorear impacto en capital de trabajo y márgenes de la semana.)*
- **[MEDIUM] Presión semanal acumulada en BRL/UYU (-3.04% en 5D):** Volatilidad 20D actual: 16.2%. *(Monitorear impacto en capital de trabajo y márgenes de la semana.)*

---

## 📊 Resumen de Mercado
| Activo       | Unidad        |    Último | Var 1D   | Var 5D    | YTD       | 1A        | Vol 20D   | Z-Score 1D   | Rango 52S                |
|:-------------|:--------------|----------:|:---------|:----------|:----------|:----------|:----------|:-------------|:-------------------------|
| USD/UYU      | UYU           |   40.7    | -0.18%   | +0.22%    | +4.24%    | +2.58%    | 2.2%      | -2.0σ        | 37.45 – 40.77 (98%)      |
| USD/BRL      | BRL           |    5.65   | -4.28%   | -3.92%    | +3.20%    | +5.05%    | 20.5%     | -6.5σ        | 4.91 – 5.95 (72%)        |
| BRL/UYU      | UYU/BRL       |    7.36   | +1.98%   | -3.04%    | -1.42%    | -4.47%    | 16.2%     | +3.1σ        | 7.19 – 8.38 (14%)        |
| USD/ARS      | ARS (Oficial) | 1601      | +0.53%   | +2.69%    | +10.30%   | +10.61%   | 5.0%      | +1.2σ        | 1354.73 – 1601.00 (100%) |
| UI (BCU)     | UYU/UI        |    6.7172 | +0.02%   | +0.14%    | +4.57%    | +4.82%    | 0.2%      | n/a          | 6.41 – 6.72 (100%)       |
| DXY          | Índice        |  103.78   | +0.10%   | -0.12%    | +5.59%    | +4.19%    | 5.8%      | +0.1σ        | 96.22 – 104.32 (93%)     |
| WTI Oil      | USD/bbl       |   84.91   | +1.47%   | +2.04%    | +47.88%   | +44.77%   | 51.6%     | +0.8σ        | 55.27 – 112.95 (51%)     |
| Gold         | USD/oz        | 3593.4    | +1.63%   | -2.50%    | -17.22%   | -13.73%   | 35.4%     | +1.1σ        | 3515.40 – 5318.40 (4%)   |
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
