# auto-lending-bot

Python lending bot with safe mock execution, Bitfinex-first read-only/dry-run workflows, guarded live lending, SQLite records, and Docker runtime.

## Requirements

- Python 3.11+
- uv for local development
- Docker Desktop for container runs

## Setup

```powershell
uv sync
Copy-Item .env.example .env
```

## Core Commands

```powershell
uv run auto-lending-bot init-db
uv run auto-lending-bot smoke-exchange
uv run auto-lending-bot run
uv run auto-lending-bot status
uv run auto-lending-bot serve-api
uv run auto-lending-bot sync-history
uv run auto-lending-bot sync-open-offers
uv run auto-lending-bot cleanup
```

## Test And Lint

```powershell
uv run pytest
uv run ruff check .
```

Frontend checks:

```powershell
cd web
npm install
npm run build
```

If `uv` is not installed yet:

```powershell
python -m pytest
```

## Docker

Build and run once in safe mock dry-run mode:

```powershell
docker compose up --build
```

Run the read-only API and React frontend together:

```powershell
docker compose up --build api web
```

Then open `http://localhost:5173`. The frontend proxies `/api` requests to the API service.

Run CLI commands in the container:

```powershell
docker compose run --rm auto-lending-bot auto-lending-bot status
docker compose run --rm auto-lending-bot auto-lending-bot serve-api --host 0.0.0.0
docker compose run --rm --env-file .env auto-lending-bot auto-lending-bot smoke-exchange
docker compose run --rm --env-file .env auto-lending-bot auto-lending-bot sync-history
docker compose run --rm --env-file .env auto-lending-bot auto-lending-bot sync-open-offers
```

The compose setup mounts the local `data/` folder into the container.

## Current Modes

- `EXCHANGE=mock`: default safe mode; no external API calls and no real lending.
- `EXCHANGE=bitfinex`: primary real-exchange path; supports read-only calls, dry-run strategy execution, and guarded live offer creation.
- `BOT_DRY_RUN=true`: default; records simulated offers locally only.
- `BOT_DRY_RUN=false`: live mode; requires explicit safety limits and exchange-specific live flags.

Use exchange API keys without withdrawal permissions.

## Bitfinex Read-Only Smoke Test

Use this before any dry-run or live test:

```env
EXCHANGE=bitfinex
EXCHANGE_API_KEY=your-key
EXCHANGE_API_SECRET=your-secret
BOT_DRY_RUN=true
SMOKE_TEST_CURRENCY=BTC
```

```powershell
docker compose run --rm --env-file .env auto-lending-bot auto-lending-bot smoke-exchange
```

Check that the command reports lending balance count, loan order count, and a plausible best daily rate.

See `docs/bitfinex-smoke-checklist.md` for the full pre-dry-run checklist.

## Bitfinex Dry Run

After smoke test succeeds, run the strategy without placing real offers:

```env
EXCHANGE=bitfinex
BOT_DRY_RUN=true
STRATEGY_DEBUG=true
BOT_MAX_LOOPS=1
```

```powershell
docker compose run --rm --env-file .env auto-lending-bot auto-lending-bot run
docker compose run --rm --env-file .env auto-lending-bot auto-lending-bot status
```

`STRATEGY_DEBUG=true` prints balance, observed best daily rate, configured min/max rates, skip reason, and generated offer count.

See `docs/bitfinex-dry-run-workflow.md` for the full dry-run calibration workflow.

## Guarded Live Lending

Live Bitfinex lending is intended for small beta tests only. It requires all of:

```env
EXCHANGE=bitfinex
BOT_DRY_RUN=false
ALLOW_LIVE_TRADING=true
BITFINEX_ENABLE_LIVE_OFFERS=true
MAX_TOTAL_LEND_AMOUNT=1
MAX_SINGLE_OFFER_AMOUNT=0.1
```

The bot records an `intent` row before creating an offer, updates it to `created` with the exchange offer id on success, and marks it `failed` with an error message on failure.

See `docs/pre-live-safety-checklist.md` before any live Bitfinex test.

## Read-Only API

Start the local API for the frontend:

```powershell
uv run auto-lending-bot serve-api --host 127.0.0.1 --port 8000
```

Current API endpoints:

- `GET /api/status`
- `GET /api/runs`
- `GET /api/offers`
- `GET /api/open-offers`
- `GET /api/active-loans`
- `GET /api/lending-history`
- `GET /api/earnings`
- `GET /api/converted-earnings`
- `GET /api/market-rates`
- `GET /api/market-analysis-rates`
- `GET /api/settings`
- `POST /api/actions/smoke-exchange`
- `POST /api/actions/sync-history`
- `POST /api/actions/sync-open-offers`
- `POST /api/actions/transfer-preview`
- `POST /api/actions/cancel-open-offers`
- `POST /api/actions/cleanup`
- `POST /api/actions/run-once`
- `POST /api/actions/record-market-analysis`

## Strategy Settings

Global settings:

- `MIN_DAILY_RATE`
- `MAX_DAILY_RATE`
- `MIN_LOAN_SIZE`
- `OUTPUT_CURRENCY`
- `TRANSFERABLE_CURRENCIES`
- `MARKET_ANALYSIS_METHOD`
- `MARKET_ANALYSIS_CURRENCIES`
- `MARKET_ANALYSIS_MIN_SAMPLES`
- `MARKET_ANALYSIS_MAX_AGE_SECONDS`
- `MARKET_ANALYSIS_PERCENTILE`
- `MARKET_ANALYSIS_MACD_SHORT_SAMPLES`
- `MARKET_ANALYSIS_MACD_LONG_SAMPLES`
- `MARKET_ANALYSIS_MACD_SHORT_SECONDS`
- `MARKET_ANALYSIS_MACD_LONG_SECONDS`
- `MARKET_ANALYSIS_MULTIPLIER`
- `MAX_PERCENT_TO_LEND`
- `MAX_TO_LEND`
- `MAX_TO_LEND_RATE`
- `MAX_AMOUNT_TO_LEND`
- `MAX_ACTIVE_AMOUNT`
- `HIDE_COINS`
- `SPREAD_LEND`
- `GAP_MODE`
- `GAP_BOTTOM`
- `GAP_TOP`
- `XDAY_THRESHOLD`
- `XDAYS`
- `XDAY_SPREAD`
- `END_DATE`
- `FRR_AS_MIN`
- `FRR_DELTA`
- `STRATEGY_DEBUG`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `NOTIFY_PREFIX`
- `NOTIFY_CAUGHT_EXCEPTION`
- `NOTIFY_SUMMARY_MINUTES`
- `NOTIFY_XDAY_THRESHOLD`

Telegram notifications are disabled unless both Telegram settings are present. When enabled,
the bot sends run summaries, live offer creation confirmations, newly detected filled-loan
messages, and periodic lending summaries when `NOTIFY_SUMMARY_MINUTES` is greater than
`0`. Set `NOTIFY_PREFIX` to prepend a label to Telegram messages,
`NOTIFY_CAUGHT_EXCEPTION=true` to send caught runtime errors, and `NOTIFY_XDAY_THRESHOLD=true`
to notify when an offer is created for more than 2 days.

Per-currency overrides use the currency symbol as a prefix:

```env
BTC_MIN_DAILY_RATE=0.00008
BTC_MIN_LOAN_SIZE=0.02
BTC_MAX_PERCENT_TO_LEND=80
BTC_MAX_TO_LEND=0.1
BTC_MAX_TO_LEND_RATE=0.00008
BTC_MAX_AMOUNT_TO_LEND=0.1
BTC_MAX_ACTIVE_AMOUNT=0.5
BTC_HIDE_COINS=true
BTC_GAP_MODE=raw_btc
BTC_GAP_BOTTOM=20
BTC_GAP_TOP=100
BTC_XDAY_THRESHOLD=0.001
BTC_XDAYS=30
BTC_XDAY_SPREAD=2
BTC_END_DATE=2027-01-15
BTC_FRR_AS_MIN=true
BTC_FRR_DELTA=0.00001
```

`FRR_AS_MIN=true` is Bitfinex-only strategy calibration. When enabled, the bot reads Bitfinex FRR and uses `max(MIN_DAILY_RATE, FRR + FRR_DELTA)` as the effective minimum daily rate for that currency.

`MAX_TO_LEND` and `MAX_PERCENT_TO_LEND` restrict lendable balance when the best market rate is at or below `MAX_TO_LEND_RATE`. Keep `MAX_TO_LEND_RATE=0` to apply the limit whenever there is a positive market rate. `MAX_AMOUNT_TO_LEND` is retained as an alias for existing env files.

`END_DATE=YYYY-MM-DD` caps offer duration so new loans finish before the date. When two or fewer days remain, the strategy stops creating new lending offers.

`GAP_MODE=raw_btc` treats `GAP_BOTTOM` and `GAP_TOP` as BTC-denominated lendbook depth, matching Mika's `RawBTC` behavior when a BTC conversion price is available.

`MARKET_ANALYSIS_CURRENCIES=BTC,ETH,USDT` records market analysis snapshots for multiple
currencies when no explicit currency is provided to `record-market-analysis`. If it is
empty, the bot falls back to `SMOKE_TEST_CURRENCY`.

`MARKET_ANALYSIS_MIN_SAMPLES` and `MARKET_ANALYSIS_MAX_AGE_SECONDS` protect suggested
minimum rates from sparse or stale market-analysis data. Keep both at `0` to disable the
extra quality gate.

`GET /api/settings` includes the market-analysis suggested minimum and effective minimum
daily rate for `SMOKE_TEST_CURRENCY`, which the dashboard shows in the strategy preview.

`TRANSFERABLE_CURRENCIES=BTC,ETH` enables transfer previews from exchange balances to the
lending wallet. `ALL` targets every exchange balance, and `ACTIVE` targets currencies that
already exist in the lending wallet. Phase 66 only previews transfers; it does not move funds.

## Operations

- Set `BOT_MAX_LOOPS=0` for continuous execution.
- Set `BOT_INACTIVE_SLEEP_SECONDS` to use a longer delay when a run creates no offers.
- Set `AUTO_REBALANCE_OPEN_OFFERS=true` to sync open offers before each run. `AUTO_CANCEL_OPEN_OFFERS=true` additionally cancels them, but only when live mode is explicitly enabled.
- Keep `KEEP_STUCK_ORDERS=true` to avoid canceling tiny partially-filled offers that would fall below `MIN_LOAN_SIZE` after cancellation.
- Use `RETRY_ATTEMPTS` and `RETRY_BACKOFF_SECONDS` for transient failure retries.
- Authentication failures are not retried; fix the key/secret or permissions before restarting.
- On startup, interrupted `running` bot runs are marked as `failed`.
- Use `auto-lending-bot cleanup` to delete old market-rate rows based on `MARKET_RATE_RETENTION_DAYS`.
- Market analysis rows are cleaned by the same command based on `MARKET_ANALYSIS_RETENTION_DAYS`.
- `scripts/dev.ps1` runs `uv sync`, tests, and ruff once `uv` is installed.

## Project Structure

```text
src/auto_lending_bot/
├─ bot/                 # Runner, retry/backoff, dry-run/live offer records
├─ cli.py               # Console command implementation
├─ api/                 # Read-only HTTP API for frontend clients
├─ config.py            # Environment settings and per-currency strategy config
├─ domain/              # Models and lending strategy
├─ integrations/        # Mock, Bitfinex, HTTP helpers
├─ market/              # Market data recording
├─ notifications/       # Local notifier adapter
└─ persistence/         # SQLite schema and repositories
```

Frontend source lives in `web/` and uses Vite, React, TypeScript, and TanStack Query.
