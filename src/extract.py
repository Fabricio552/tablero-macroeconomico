import yfinance as yf
import pandas as pd

TICKERS = {
    "USD/UYU": "UYU=X",
    "USD/BRL": "BRL=X",
    "USD/ARS": "ARS=X",
    "US 10Y Yield": "^TNX",
    "WTI Oil": "CL=F",
    "Gold": "GC=F",
    "DXY": "DX-Y.NYB"
}

def fetch_macro_data(period: str = "1y") -> pd.DataFrame:
    raw_data = yf.download(
        list(TICKERS.values()),
        period=period,
        interval="1d",
        progress=False
    )["Close"]
    inv_tickers = {v: k for k, v in TICKERS.items()}
    df = raw_data.rename(columns=inv_tickers).ffill().dropna()
    return df