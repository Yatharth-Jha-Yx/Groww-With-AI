"""Pure maths on price history. No network calls, so it is easy to test.

Every number here is a standard textbook formula — the docstring of each
function says what it is, so you can explain where a number came from.
"""

from __future__ import annotations

import math

import pandas as pd

TRADING_DAYS_PER_YEAR = 252  # usual convention for Indian & US markets


def candles_to_frame(candles: list) -> pd.DataFrame:
    """Turn Groww's candle list into a table.

    Groww returns each candle as [time, open, high, low, close, volume, (oi)].
    Time can be epoch seconds, epoch milliseconds, or an ISO string.
    """
    rows = []
    for c in candles or []:
        ts = c[0]
        if isinstance(ts, (int, float)):
            ts = pd.to_datetime(ts, unit="ms" if ts > 1e11 else "s")
        else:
            ts = pd.to_datetime(ts)
        rows.append({"time": ts, "open": c[1], "high": c[2], "low": c[3], "close": c[4],
                     "volume": c[5] if len(c) > 5 else None})
    df = pd.DataFrame(rows, columns=["time", "open", "high", "low", "close", "volume"])
    if not df.empty:
        df = df.drop_duplicates("time").sort_values("time").reset_index(drop=True)
        df["close"] = df["close"].astype(float)
    return df


def period_return(close: pd.Series, days: int) -> float | None:
    """% change over the last `days` trading days: (today / then - 1) * 100."""
    if len(close) <= days:
        return None
    return (close.iloc[-1] / close.iloc[-1 - days] - 1) * 100


def annual_volatility(close: pd.Series) -> float | None:
    """How much the price jumps around, yearly %.

    = standard deviation of daily % returns * sqrt(252) * 100.
    Rough guide: <20% calm (large caps), 20-35% normal, >35% very jumpy.
    """
    r = close.pct_change().dropna()
    if len(r) < 20:
        return None
    return float(r.std() * math.sqrt(TRADING_DAYS_PER_YEAR) * 100)


def max_drawdown(close: pd.Series) -> float | None:
    """Worst fall from a previous peak, in % (a negative number).

    Example: price goes 100 -> 150 -> 90, drawdown = 90/150 - 1 = -40%.
    """
    if close.empty:
        return None
    peak = close.cummax()
    return float(((close / peak) - 1).min() * 100)


def rsi(close: pd.Series, period: int = 14) -> float | None:
    """Relative Strength Index (J. Welles Wilder, 1978), 0-100.

    Above 70 is usually called "overbought", below 30 "oversold".
    """
    if len(close) <= period:
        return None
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    last_loss = loss.iloc[-1]
    if last_loss == 0:
        return 100.0
    rs = gain.iloc[-1] / last_loss
    return float(100 - 100 / (1 + rs))


def moving_average(close: pd.Series, days: int) -> float | None:
    """Simple average of the last `days` closing prices (e.g. 50-DMA, 200-DMA)."""
    if len(close) < days:
        return None
    return float(close.iloc[-days:].mean())


def summarize(df: pd.DataFrame) -> dict:
    """All the stats for one stock in one dict."""
    close = df["close"] if not df.empty else pd.Series(dtype=float)
    last = float(close.iloc[-1]) if len(close) else None
    dma50, dma200 = moving_average(close, 50), moving_average(close, 200)
    trend = None
    if last and dma50 and dma200:
        if last > dma50 > dma200:
            trend = "uptrend (price > 50-DMA > 200-DMA)"
        elif last < dma50 < dma200:
            trend = "downtrend (price < 50-DMA < 200-DMA)"
        else:
            trend = "mixed / sideways"
    return {
        "last_close": last,
        "return_1m_pct": period_return(close, 21),
        "return_3m_pct": period_return(close, 63),
        "return_6m_pct": period_return(close, 126),
        "return_1y_pct": period_return(close, 252),
        "volatility_pct": annual_volatility(close),
        "max_drawdown_pct": max_drawdown(close),
        "rsi_14": rsi(close),
        "dma_50": dma50,
        "dma_200": dma200,
        "trend": trend,
        "high_52w": float(close.iloc[-252:].max()) if len(close) else None,
        "low_52w": float(close.iloc[-252:].min()) if len(close) else None,
        "data_points": int(len(close)),
    }
