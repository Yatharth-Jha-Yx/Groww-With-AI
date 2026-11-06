"""Read-only data fetching: holdings, live prices, price history.

Groww SDK methods used (all read-only, from growwapi/groww/client.py):
  get_holdings_for_user()      -> your demat holdings
  get_ltp(symbols, segment)    -> last traded price, up to 50 symbols per call
  get_historical_candles(...)  -> daily OHLC candles
  get_user_profile()           -> your account profile
  get_available_margin_details() -> cash available to trade
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta

import pandas as pd

from .analysis import candles_to_frame, summarize

SEGMENT_CASH = "CASH"
LTP_BATCH = 50          # Groww accepts up to 50 symbols per LTP call
CANDLE_CHUNK_DAYS = 180  # ask for history in 180-day pieces to stay within API limits
PAUSE_SECONDS = 0.15     # small pause between calls to respect rate limits


def fetch_holdings(groww) -> list[dict]:
    data = groww.get_holdings_for_user()
    return data.get("holdings", []) if isinstance(data, dict) else []


def fetch_ltp(groww, symbols: list[str], exchange: str = "NSE") -> dict[str, float]:
    """Return {"RELIANCE": 2950.5, ...}."""
    prices: dict[str, float] = {}
    for i in range(0, len(symbols), LTP_BATCH):
        batch = [f"{exchange}_{s}" for s in symbols[i:i + LTP_BATCH]]
        data = groww.get_ltp(exchange_trading_symbols=tuple(batch), segment=SEGMENT_CASH)
        for key, value in (data or {}).items():
            price = value.get("ltp") if isinstance(value, dict) else value
            if price is not None:
                prices[key.split("_", 1)[1]] = float(price)
        time.sleep(PAUSE_SECONDS)
    return prices


def fetch_daily_history(groww, symbol: str, days: int = 400, exchange: str = "NSE") -> pd.DataFrame:
    """Daily candles for the last `days` calendar days."""
    end = datetime.now()
    start = end - timedelta(days=days)
    candles: list = []
    chunk_start = start
    while chunk_start < end:
        chunk_end = min(chunk_start + timedelta(days=CANDLE_CHUNK_DAYS), end)
        data = groww.get_historical_candles(
            exchange=exchange,
            segment=SEGMENT_CASH,
            groww_symbol=f"{exchange}-{symbol}",
            start_time=chunk_start.strftime("%Y-%m-%d %H:%M:%S"),
            end_time=chunk_end.strftime("%Y-%m-%d %H:%M:%S"),
            candle_interval="1day",
        )
        candles.extend((data or {}).get("candles", []))
        chunk_start = chunk_end
        time.sleep(PAUSE_SECONDS)
    return candles_to_frame(candles)


def build_portfolio_table(holdings: list[dict], prices: dict[str, float]) -> pd.DataFrame:
    """One row per stock with invested value, current value, profit/loss and weight."""
    rows = []
    for h in holdings:
        sym = h.get("trading_symbol")
        qty = float(h.get("quantity") or 0)
        avg = float(h.get("average_price") or 0)
        ltp = prices.get(sym)
        invested = qty * avg
        current = qty * ltp if ltp is not None else None
        rows.append({
            "symbol": sym,
            "isin": h.get("isin"),
            "qty": qty,
            "avg_price": avg,
            "ltp": ltp,
            "invested": invested,
            "current_value": current,
            "pnl": (current - invested) if current is not None else None,
            "pnl_pct": ((ltp / avg - 1) * 100) if (ltp is not None and avg) else None,
        })
    df = pd.DataFrame(rows, columns=["symbol", "isin", "qty", "avg_price", "ltp", "invested",
                                     "current_value", "pnl", "pnl_pct"])
    total = df["current_value"].sum(skipna=True)
    df["weight_pct"] = (df["current_value"] / total * 100) if total else None
    return df.sort_values("current_value", ascending=False, na_position="last").reset_index(drop=True)


def portfolio_warnings(df: pd.DataFrame, max_single_weight: float = 20.0) -> list[str]:
    """Simple, explainable red flags. Thresholds are common rules of thumb, not law."""
    notes = []
    if df.empty:
        return ["No holdings found."]
    for _, r in df.iterrows():
        if r["weight_pct"] is not None and pd.notna(r["weight_pct"]) and r["weight_pct"] > max_single_weight:
            notes.append(f"{r['symbol']} is {r['weight_pct']:.1f}% of the portfolio "
                         f"(more than {max_single_weight:.0f}% in one stock = concentration risk).")
        if pd.notna(r["pnl_pct"]) and r["pnl_pct"] < -25:
            notes.append(f"{r['symbol']} is down {r['pnl_pct']:.1f}% from your buy price — "
                         "worth re-checking why you bought it.")
    if len(df) < 5:
        notes.append(f"Only {len(df)} stocks — a small number of stocks means each one moves your total a lot.")
    missing = df[df["ltp"].isna()]["symbol"].tolist()
    if missing:
        notes.append(f"No live price for: {', '.join(map(str, missing))} (may be BSE-only or suspended).")
    return notes


def analyze_symbols(groww, symbols: list[str], days: int = 400) -> dict[str, dict]:
    out = {}
    for s in symbols:
        try:
            out[s] = summarize(fetch_daily_history(groww, s, days=days))
        except Exception as e:  # keep going if one stock fails
            out[s] = {"error": str(e)}
    return out
