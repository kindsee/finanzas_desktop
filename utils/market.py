# utils/market.py
import yfinance as yf
from decimal import Decimal

def fetch_price_yfinance(ticker: str) -> float:
    """
    Devuelve precio actual (float) para ticker.
    yfinance acepta tickers con sufijos (eg 'SAN.MC' o 'BBVA.MC', 'AAPL').
    """
    try:
        t = yf.Ticker(ticker)
        # preferimos last close / regularMarketPrice
        info = t.history(period="1d", interval="1d")
        if not info.empty:
            # price close del último registro
            last = info['Close'].iloc[-1]
            return float(last)
        # fallback a info["regularMarketPrice"]
        info2 = t.info
        price = info2.get("regularMarketPrice") or info2.get("currentPrice")
        if price is not None:
            return float(price)
    except Exception:
        pass
    raise RuntimeError(f"No se pudo obtener precio para {ticker}")
