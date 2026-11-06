# Groww-With-AI

Use **Claude** as a research assistant for your **Groww** stock portfolio.
Python code pulls your real data with Groww's official API; Claude reads it,
researches the stocks, and explains suggestions in plain words — with sources.

```
Groww account ──(official growwapi SDK)──> this code ──> reports/latest.md ──> Claude
                                                                          (reads, researches, suggests)
```

**Example:** you type in Claude Code: *"Run the report and tell me if my portfolio is too risky."*
Claude runs `python -m groww_ai report`, reads that 60% of your money is in one stock
(source: Groww `get_holdings_for_user` + `get_ltp`), checks recent news on it, and
explains the risk and options — but never buys or sells on its own.

## What it can do

| Command | What it does | Groww SDK method used |
|---|---|---|
| `python -m groww_ai check` | Test login, show your profile | `get_user_profile` |
| `python -m groww_ai portfolio` | Holdings, live price, profit/loss, weight %, warnings | `get_holdings_for_user`, `get_ltp` |
| `python -m groww_ai report` | Full snapshot + 1-year stats → `reports/latest.md` | above + `get_historical_candles`, `get_available_margin_details` |
| `python -m groww_ai analyze TCS INFY` | Returns (1M/3M/1Y), volatility, max fall, RSI, 50/200-day averages | `get_historical_candles` |
| `python -m groww_ai quote NIFTYBEES` | Live price | `get_ltp` |
| `python -m groww_ai order BUY NIFTYBEES 10 --price 270` | **Dry run** — shows what would be sent | `place_order` (only when unlocked) |

Formulas for every stat are written in `groww_ai/analysis.py`, so you can show how a number was made.

## Setup (on your own computer)

1. Install **Python 3.11 or 3.12** from python.org.
2. Get the code and make a virtual environment (Groww's SDK needs this on some systems):
   ```bash
   git clone https://github.com/yatharth-jha-yx/groww-with-ai.git
   cd groww-with-ai
   python -m venv .venv
   .venv\Scripts\activate        # Windows  (Mac/Linux: source .venv/bin/activate)
   pip install -r requirements.txt
   ```
3. On **groww.in/trade-api/api-keys** click **Generate API key** (choose the TOTP type if offered).
4. Copy `.env.example` to `.env` and paste your key there. **Never paste keys into a chat.**
5. Copy `investor_profile.example.md` to `investor_profile.md` and fill in your goals and risk level.
6. Test: `python -m groww_ai check`
7. Open the folder in **Claude Code** and ask things like:
   - "Run the report and review my portfolio against my profile."
   - "Research my 3 biggest holdings — latest results and news, with sources."
   - "I have Rs. 5,000 a month. Suggest how to split it, and why."
   - "Compare NIFTYBEES and JUNIORBEES for me."

Claude follows the rules in `CLAUDE.md` (simple words, always cite sources, never trade by itself).

## Safety

- Read-only by default. An order is sent **only** if you pass `--live`, set
  `GROWW_ALLOW_LIVE_ORDERS=true` in `.env`, the order is under `GROWW_MAX_ORDER_VALUE`
  (default Rs. 10,000), **and** you type the confirmation phrase yourself.
- `.env`, `reports/` and `investor_profile.md` are git-ignored — your keys and money data stay on your PC.

## Things to know

- **Mutual funds are not in this API** — it covers stocks, ETFs and F&O. Tell Claude your MFs manually (profile file).
- **API keys reset daily at 6 AM** (Groww API-key page). The TOTP option logs in fresh automatically.
- **Static IP for orders:** SEBI rules require a registered static IP to place orders via API from 31 March 2026
  (Groww API-key page banner). Reading data doesn't need it.
- **Cost:** check Groww's API page for whether the Trade API needs a subscription on your account.
- This is research help, **not SEBI-registered investment advice.**

## Run tests (no Groww account needed)

```bash
pip install pytest
python -m pytest -q
```
