"""Write a snapshot report (Markdown + JSON) that Claude reads to give advice."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd

REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"


def _fmt(v, nd=1, pct=False):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    s = f"{v:,.{nd}f}"
    return s + "%" if pct else s


def write_report(table: pd.DataFrame, warnings: list[str], stats: dict[str, dict],
                 profile: dict | None = None, margin: dict | None = None) -> Path:
    REPORTS_DIR.mkdir(exist_ok=True)
    now = datetime.now()
    stamp = now.strftime("%Y-%m-%d_%H%M")
    invested = table["invested"].sum()
    current = table["current_value"].sum(skipna=True)

    lines = [
        f"# Portfolio snapshot — {now:%d %b %Y, %I:%M %p}",
        "",
        "**Source:** Groww Trade API via official `growwapi` SDK — "
        "`get_holdings_for_user`, `get_ltp`, `get_historical_candles` (daily candles). "
        "Stats computed locally in `groww_ai/analysis.py`.",
        "",
        "## Totals",
        f"- Invested: Rs.{invested:,.0f}",
        f"- Current value: Rs.{current:,.0f}",
        f"- Profit/Loss: Rs.{current - invested:,.0f} "
        f"({_fmt((current / invested - 1) * 100 if invested else None, pct=True)})",
        f"- Number of stocks: {len(table)}",
    ]
    if margin:
        lines.append(f"- Cash/margin info (raw from Groww): `{json.dumps(margin)[:300]}`")
    lines += ["", "## Holdings", "",
              "| Stock | Qty | Avg buy | Live price | Value | P&L % | Weight |",
              "|---|---:|---:|---:|---:|---:|---:|"]
    for _, r in table.iterrows():
        lines.append(f"| {r['symbol']} | {_fmt(r['qty'], 0)} | {_fmt(r['avg_price'], 2)} | "
                     f"{_fmt(r['ltp'], 2)} | {_fmt(r['current_value'], 0)} | "
                     f"{_fmt(r['pnl_pct'], pct=True)} | {_fmt(r['weight_pct'], pct=True)} |")
    lines += ["", "## Warnings (rule-of-thumb checks)", ""]
    lines += [f"- {w}" for w in warnings] or ["- None"]
    if stats:
        lines += ["", "## Price behaviour (from ~1 year of daily candles)", "",
                  "| Stock | 1M | 3M | 1Y | Volatility | Max fall | RSI-14 | Trend |",
                  "|---|---:|---:|---:|---:|---:|---:|---|"]
        for sym, s in stats.items():
            if "error" in s:
                lines.append(f"| {sym} | error: {s['error'][:60]} | | | | | | |")
                continue
            lines.append(f"| {sym} | {_fmt(s['return_1m_pct'], pct=True)} | {_fmt(s['return_3m_pct'], pct=True)} | "
                         f"{_fmt(s['return_1y_pct'], pct=True)} | {_fmt(s['volatility_pct'], pct=True)} | "
                         f"{_fmt(s['max_drawdown_pct'], pct=True)} | {_fmt(s['rsi_14'])} | {s['trend'] or '—'} |")
    lines += ["", "_Past performance does not predict future returns. Not investment advice._", ""]

    md_path = REPORTS_DIR / f"snapshot_{stamp}.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    payload = {"generated_at": now.isoformat(), "profile": profile,
               "holdings": json.loads(table.to_json(orient="records")),
               "warnings": warnings, "stats": stats}
    (REPORTS_DIR / f"snapshot_{stamp}.json").write_text(json.dumps(payload, indent=2, default=str))
    (REPORTS_DIR / "latest.md").write_text("\n".join(lines), encoding="utf-8")
    return md_path
