"""Placing orders — locked down on purpose.

An order only goes to Groww when ALL of these are true:
  1. You passed --live on the command line
  2. GROWW_ALLOW_LIVE_ORDERS=true in your .env
  3. Order value <= GROWW_MAX_ORDER_VALUE (default Rs. 10,000)
  4. You type the exact confirmation phrase in the terminal yourself
Otherwise it is a DRY RUN: it prints what it *would* send and stops.

Note (from the Groww API-key page): SEBI rules require a registered static IP
for placing orders via API from 31 March 2026. Reading data does not need it.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv


class OrderBlocked(RuntimeError):
    pass


def build_order(symbol: str, side: str, qty: int, price: float | None, exchange: str = "NSE") -> dict:
    side = side.upper()
    if side not in {"BUY", "SELL"}:
        raise ValueError("side must be BUY or SELL")
    if qty <= 0:
        raise ValueError("qty must be positive")
    return {
        "trading_symbol": symbol.upper(),
        "quantity": int(qty),
        "price": float(price) if price else 0.0,
        "validity": "DAY",
        "exchange": exchange,
        "segment": "CASH",
        "product": "CNC",  # delivery (long-term holding), not intraday
        "order_type": "LIMIT" if price else "MARKET",
        "transaction_type": side,
    }


def check_limits(order: dict, est_price: float) -> float:
    load_dotenv()
    max_value = float(os.getenv("GROWW_MAX_ORDER_VALUE", "10000"))
    value = order["quantity"] * est_price
    if value > max_value:
        raise OrderBlocked(f"Order value Rs.{value:,.0f} is above your cap Rs.{max_value:,.0f} "
                           "(GROWW_MAX_ORDER_VALUE in .env).")
    return value


def submit(groww, order: dict, est_price: float, live: bool, confirm=input) -> dict:
    value = check_limits(order, est_price)
    summary = (f"{order['transaction_type']} {order['quantity']} x {order['trading_symbol']} "
               f"({order['order_type']}, ~Rs.{value:,.0f})")
    allowed = os.getenv("GROWW_ALLOW_LIVE_ORDERS", "false").strip().lower() == "true"
    if not (live and allowed):
        return {"status": "DRY_RUN", "would_send": order, "summary": summary,
                "why": "Needs --live AND GROWW_ALLOW_LIVE_ORDERS=true in .env"}
    phrase = f"YES {order['transaction_type']} {order['trading_symbol']}"
    answer = confirm(f"About to place REAL order: {summary}\nType '{phrase}' to confirm: ")
    if answer.strip() != phrase:
        return {"status": "CANCELLED", "summary": summary}
    return groww.place_order(**order)
