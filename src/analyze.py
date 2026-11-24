import pandas as pd
from datetime import datetime

def compute_summary_metrics(df: pd.DataFrame) -> pd.DataFrame:
    current_year = datetime.now().year
    ytd_df = df[df.index.year == current_year]
    summary = []
    for col in df.columns:
        latest = df[col].iloc[-1]
        prev_1d = df[col].iloc[-2]
        prev_5d = df[col].iloc[-6] if len(df) >= 6 else df[col].iloc[0]
        start_ytd = ytd_df[col].iloc[0] if not ytd_df.empty else df[col].iloc[0]
        summary.append({
            "Activo": col,
            "Último": round(latest, 2),
            "Var 1D (%)": round(((latest / prev_1d) - 1) * 100, 2),
            "Var 5D (%)": round(((latest / prev_5d) - 1) * 100, 2),
            "YTD (%)": round(((latest / start_ytd) - 1) * 100, 2)
        })
    return pd.DataFrame(summary)

def compute_correlations(df: pd.DataFrame, window: int = 60) -> pd.DataFrame:
    returns = df.pct_change().dropna().tail(window)
    return returns.corr().round(2)