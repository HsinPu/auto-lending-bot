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

Real read-only exchange calls are still planned for a later phase.
