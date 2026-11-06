"""Command line: `python -m groww_ai <command>`.

Commands
  check                      test your login, show profile
  portfolio                  holdings + live prices + P&L + warnings
  report                     full snapshot (portfolio + 1-year stats) -> reports/latest.md
  analyze SYM [SYM ...]      price stats for any stocks (e.g. ones you are thinking of buying)
  quote SYM [SYM ...]        live price
  order BUY|SELL SYM QTY [--price P] [--live]   dry-run unless fully unlocked
"""

from __future__ import annotations

import argparse
import json
import sys

import pandas as pd

from . import orders
from .client import connect
from .portfolio import (analyze_symbols, build_portfolio_table, fetch_holdings, fetch_ltp,
                        portfolio_warnings)
from .report import write_report


def _portfolio(groww):
    holdings = fetch_holdings(groww)
    symbols = [h["trading_symbol"] for h in holdings if h.get("trading_symbol")]
    table = build_portfolio_table(holdings, fetch_ltp(groww, symbols))
    return table, portfolio_warnings(table)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="groww_ai", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    sub.add_parser("portfolio")
    sub.add_parser("report")
    a = sub.add_parser("analyze"); a.add_argument("symbols", nargs="+")
    q = sub.add_parser("quote"); q.add_argument("symbols", nargs="+")
    o = sub.add_parser("order")
    o.add_argument("side", choices=["BUY", "SELL", "buy", "sell"])
    o.add_argument("symbol"); o.add_argument("qty", type=int)
    o.add_argument("--price", type=float, help="limit price; omit for market order")
    o.add_argument("--live", action="store_true", help="actually send (also needs .env switch)")
    args = p.parse_args(argv)

    groww = connect()
    pd.set_option("display.width", 200)

    if args.cmd == "check":
        print(json.dumps(groww.get_user_profile(), indent=2))
    elif args.cmd == "portfolio":
        table, warns = _portfolio(groww)
        print(table.round(2).to_string(index=False))
        print("\nWarnings:\n- " + "\n- ".join(warns or ["None"]))
    elif args.cmd == "report":
        table, warns = _portfolio(groww)
        stats = analyze_symbols(groww, table["symbol"].tolist())
        try:
            margin = groww.get_available_margin_details()
        except Exception:
            margin = None
        path = write_report(table, warns, stats, margin=margin)
        print(f"Report written: {path}\n(also copied to reports/latest.md)")
    elif args.cmd == "analyze":
        print(json.dumps(analyze_symbols(groww, [s.upper() for s in args.symbols]), indent=2, default=str))
    elif args.cmd == "quote":
        print(json.dumps(fetch_ltp(groww, [s.upper() for s in args.symbols]), indent=2))
    elif args.cmd == "order":
        order = orders.build_order(args.symbol, args.side, args.qty, args.price)
        est = args.price or fetch_ltp(groww, [order["trading_symbol"]]).get(order["trading_symbol"])
        if est is None:
            print("Could not get a price for that symbol."); return 1
        try:
            print(json.dumps(orders.submit(groww, order, est, live=args.live), indent=2, default=str))
        except orders.OrderBlocked as e:
            print(f"BLOCKED: {e}"); return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
