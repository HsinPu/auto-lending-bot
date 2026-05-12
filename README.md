# auto-lending-bot

Python starter project for an auto lending bot.

## Requirements

- Python 3.11+
- uv

## Setup

```powershell
uv sync
```

Optional local configuration:

```powershell
Copy-Item .env.example .env
```

## Run

```powershell
uv run auto-lending-bot init-db
uv run auto-lending-bot run
uv run auto-lending-bot status
uv run auto-lending-bot cleanup
uv run auto-lending-bot dashboard
```

Phase one uses a mock exchange by default and runs in dry-run mode. It records bot runs,
generated loan offers, and captured mock market rates into SQLite.

## Test And Lint

```powershell
uv run pytest
uv run ruff check .
```

## Project Structure

```text
src/auto_lending_bot/
├─ bot/                 # Bot runner and orchestration
├─ main.py              # Application entry point
├─ config.py            # Environment-based settings
├─ logging.py           # Logging setup
├─ domain/              # Core business rules and models
├─ integrations/        # External service clients
├─ market/              # Market data recording
├─ notifications/       # Notification adapters
├─ persistence/         # SQLite and repository code
└─ utils/               # Shared utilities
```

## Phase One Scope

- Mock exchange only
- Dry-run enabled by default
- Simple lending strategy based on minimum daily rate, minimum loan size, and split count
- SQLite tables for bot runs, loan offers, and market rates
- No real exchange API calls yet

## Safety

- `EXCHANGE=mock` is the only runnable exchange in the current phase.
- `BOT_DRY_RUN=true` is the default.
- `BOT_DRY_RUN=false` requires `ALLOW_LIVE_TRADING=true`.
- Live trading support is not implemented yet.

## Strategy Settings

Global strategy settings can be configured through environment variables:

- `MIN_DAILY_RATE`
- `MAX_DAILY_RATE`
- `MIN_LOAN_SIZE`
- `MAX_PERCENT_TO_LEND`
- `MAX_AMOUNT_TO_LEND`
- `HIDE_COINS`
- `SPREAD_LEND`

Per-currency overrides use the currency symbol as a prefix, for example:

```env
BTC_MIN_DAILY_RATE=0.00008
BTC_MAX_PERCENT_TO_LEND=80
BTC_MAX_AMOUNT_TO_LEND=0.1
BTC_HIDE_COINS=true
```

## Exchange Adapter Roadmap

The project currently includes only a mock runnable exchange. Phase four adds adapter
building blocks for future real exchanges:

- exchange error types
- HTTP client protocol
- retry wrapper for rate-limit responses
- Poloniex signing skeleton

Phase five adds read-only Poloniex calls for balances, loan orders, and open loan offers.
The runner still requires `BOT_DRY_RUN=true` for `EXCHANGE=poloniex`.

```env
EXCHANGE=poloniex
EXCHANGE_API_KEY=your-key
EXCHANGE_API_SECRET=your-secret
BOT_DRY_RUN=true
```

Use API keys without withdrawal permissions.

## Live Lending Beta

Live lending is guarded by explicit settings and is intended for small tests only:

```env
EXCHANGE=poloniex
BOT_DRY_RUN=false
ALLOW_LIVE_TRADING=true
MAX_TOTAL_LEND_AMOUNT=1
MAX_SINGLE_OFFER_AMOUNT=0.1
```

When live mode is enabled, the bot records an `intent` row before creating an offer and
updates the same row to `created` with the exchange offer id after success.

## Operations

- Set `BOT_MAX_LOOPS=0` for continuous execution.
- Use `RETRY_ATTEMPTS` and `RETRY_BACKOFF_SECONDS` to control transient failure retries.
- On startup, interrupted `running` bot runs are marked as `failed`.
- Use `auto-lending-bot cleanup` to delete old market-rate rows based on
  `MARKET_RATE_RETENTION_DAYS`.
- On Windows, `scripts/dev.ps1` runs sync, tests, and lint once `uv` is installed.

## Dashboard

Generate a local read-only HTML dashboard:

```powershell
uv run auto-lending-bot dashboard
```

The output path defaults to `reports/dashboard.html` and can be changed with `REPORT_PATH`.
