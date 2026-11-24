import os
from datetime import datetime, timezone
import matplotlib.pyplot as plt
import seaborn as sns
from extract import fetch_macro_data
from analyze import compute_summary_metrics, compute_correlations

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_IMG = os.path.join(BASE_DIR, "output", "macro_dashboard.png")
README_PATH = os.path.join(BASE_DIR, "README.md")

def generate_chart(df, corr_matrix):
    os.makedirs(os.path.dirname(OUTPUT_IMG), exist_ok=True)
    plt.style.use("seaborn-v0_8-whitegrid")
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5))

    currencies = ["USD/UYU", "USD/BRL", "DXY"]
    norm_df = (df[currencies] / df[currencies].iloc[0]) * 100
    for col in currencies:
        ax1.plot(norm_df.index, norm_df[col], label=col, linewidth=2)
    ax1.set_title("Evolución Cambiaria Normalizada (Base 100 - 1 Año)", fontweight="bold")
    ax1.set_ylabel("Índice (Base 100)")
    ax1.legend()

    sns.heatmap(corr_matrix, annot=True, cmap="coolwarm", center=0, ax=ax2, cbar=False)
    ax2.set_title("Correlación de Retornos Diarios (Últimos 60 días)", fontweight="bold")

    plt.tight_layout()
    plt.savefig(OUTPUT_IMG, dpi=300)
    plt.close()

def update_readme(summary_df):
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    markdown_table = summary_df.to_markdown(index=False)
    content = f"""# 🌎 Tablero Macroeconómico Regional (Uruguay / LatAm)

Pipeline automatizado en Python que monitorea diariamente las principales variables cambiarias, tasas de referencia y commodities con impacto en Uruguay y la región.

*Última actualización automática: **{timestamp}***

## 📊 Resumen de Mercado
{markdown_table}

## 📈 Tendencia Cambiaria y Correlaciones
![Dashboard Macro](./output/macro_dashboard.png)

---
*Desarrollado con Python (`yfinance`, `pandas`, `matplotlib`, `seaborn`) y automatizado mediante GitHub Actions.*
"""
    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(content)

if __name__ == "__main__":
    data = fetch_macro_data(period="1y")
    metrics = compute_summary_metrics(data)
    corr = compute_correlations(data, window=60)
    generate_chart(data, corr)
    update_readme(metrics)
    print("Tablero macro actualizado exitosamente.")