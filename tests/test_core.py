"""Offline tests using a fake Groww client (no real account needed)."""

import os

import pandas as pd
import pytest

from groww_ai import analysis, orders
from groww_ai.portfolio import (analyze_symbols, build_portfolio_table, fetch_holdings, fetch_ltp,
                                portfolio_warnings)
from groww_ai.report import write_report


class FakeGroww:
    def __init__(self):
        self.placed = []

    def get_holdings_for_user(self):
        return {"holdings": [
            {"trading_symbol": "RELIANCE", "isin": "INE002A01018", "quantity": 10, "average_price": 2500},
            {"trading_symbol": "TCS", "isin": "INE467B01029", "quantity": 2, "average_price": 4000},
        ]}

    def get_ltp(self, exchange_trading_symbols, segment):
        prices = {"NSE_RELIANCE": 2750.0, "NSE_TCS": 2800.0}
        return {s: prices[s] for s in exchange_trading_symbols if s in prices}

    def get_historical_candles(self, exchange, segment, groww_symbol, start_time, end_time, candle_interval):
        start = pd.Timestamp(start_time)
        days = pd.bdate_range(start, pd.Timestamp(end_time))
        return {"candles": [[d.strftime("%Y-%m-%dT00:00:00"), 0, 0, 0, 100 + i * 0.5, 1000]
                            for i, d in enumerate(days, start=(start - pd.Timestamp("2020-01-01")).days)]}

    def place_order(self, **kw):
        self.placed.append(kw)
        return {"groww_order_id": "X1", "order_status": "OPEN"}


def test_portfolio_table_and_warnings():
    g = FakeGroww()
    t = build_portfolio_table(fetch_holdings(g), fetch_ltp(g, ["RELIANCE", "TCS"]))
    rel = t[t.symbol == "RELIANCE"].iloc[0]
    assert rel.pnl == pytest.approx(2500)          # 10 * (2750 - 2500)
    assert rel.pnl_pct == pytest.approx(10.0)
    assert t.weight_pct.sum() == pytest.approx(100)
    w = " ".join(portfolio_warnings(t))
    assert "TCS is down -30.0%" in w and "RELIANCE is 83.1%" in w


def test_analysis_maths():
    close = pd.Series([100, 150, 90, 120], dtype=float)
    assert analysis.max_drawdown(close) == pytest.approx(-40.0)
    assert analysis.period_return(close, 3) == pytest.approx(20.0)
    up = pd.Series(range(1, 300), dtype=float)
    assert analysis.rsi(up) == 100.0
    assert analysis.summarize(pd.DataFrame({"close": up}))["trend"].startswith("uptrend")


def test_candles_parsing_epoch_and_iso():
    df = analysis.candles_to_frame([[1700000000, 1, 1, 1, 10, 5], ["2023-11-15T00:00:00", 1, 1, 1, 11, 5]])
    assert list(df.close) == [10.0, 11.0]


def test_history_dedup_and_report(tmp_path, monkeypatch):
    import groww_ai.report as rep
    monkeypatch.setattr(rep, "REPORTS_DIR", tmp_path)
    monkeypatch.setattr("groww_ai.portfolio.PAUSE_SECONDS", 0)
    g = FakeGroww()
    stats = analyze_symbols(g, ["RELIANCE"], days=400)
    assert stats["RELIANCE"]["data_points"] > 250
    t = build_portfolio_table(fetch_holdings(g), fetch_ltp(g, ["RELIANCE", "TCS"]))
    path = write_report(t, portfolio_warnings(t), stats)
    text = path.read_text()
    assert "RELIANCE" in text and "get_holdings_for_user" in text
    assert (tmp_path / "latest.md").exists()


def test_orders_are_dry_run_by_default(monkeypatch):
    monkeypatch.setenv("GROWW_ALLOW_LIVE_ORDERS", "false")
    monkeypatch.setenv("GROWW_MAX_ORDER_VALUE", "10000")
    g = FakeGroww()
    o = orders.build_order("niftybees", "buy", 10, 270)
    assert orders.submit(g, o, 270, live=True)["status"] == "DRY_RUN"
    assert g.placed == []


def test_orders_cap_and_confirmation(monkeypatch):
    monkeypatch.setenv("GROWW_ALLOW_LIVE_ORDERS", "true")
    monkeypatch.setenv("GROWW_MAX_ORDER_VALUE", "10000")
    g = FakeGroww()
    with pytest.raises(orders.OrderBlocked):
        orders.submit(g, orders.build_order("TCS", "BUY", 5, 4000), 4000, live=True)
    o = orders.build_order("NIFTYBEES", "BUY", 10, 270)
    assert orders.submit(g, o, 270, live=True, confirm=lambda _: "yes")["status"] == "CANCELLED"
    assert orders.submit(g, o, 270, live=True, confirm=lambda _: "YES BUY NIFTYBEES")["order_status"] == "OPEN"
    assert g.placed[0]["product"] == "CNC"
