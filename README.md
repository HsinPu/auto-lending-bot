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

Current read-only endpoints:

- `GET /api/status`
- `GET /api/runs`
- `GET /api/offers`
- `GET /api/open-offers`
- `GET /api/active-loans`
- `GET /api/lending-history`
- `GET /api/earnings`
- `GET /api/market-rates`
- `GET /api/settings`

## Strategy Settings

Global settings:

- `MIN_DAILY_RATE`
- `MAX_DAILY_RATE`
- `MIN_LOAN_SIZE`
- `MAX_PERCENT_TO_LEND`
- `MAX_TO_LEND`
- `MAX_TO_LEND_RATE`
- `MAX_AMOUNT_TO_LEND`
- `HIDE_COINS`
- `SPREAD_LEND`
- `GAP_MODE`
- `GAP_BOTTOM`
- `GAP_TOP`
- `XDAY_THRESHOLD`
- `XDAYS`
- `XDAY_SPREAD`
- `FRR_AS_MIN`
- `FRR_DELTA`
- `STRATEGY_DEBUG`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Per-currency overrides use the currency symbol as a prefix:

```env
BTC_MIN_DAILY_RATE=0.00008
BTC_MAX_PERCENT_TO_LEND=80
BTC_MAX_TO_LEND=0.1
BTC_MAX_TO_LEND_RATE=0.00008
BTC_MAX_AMOUNT_TO_LEND=0.1
BTC_HIDE_COINS=true
BTC_GAP_MODE=raw
BTC_GAP_BOTTOM=20
BTC_GAP_TOP=100
BTC_XDAY_THRESHOLD=0.001
BTC_XDAYS=30
BTC_XDAY_SPREAD=2
BTC_FRR_AS_MIN=true
BTC_FRR_DELTA=0.00001
```

`FRR_AS_MIN=true` is Bitfinex-only strategy calibration. When enabled, the bot reads Bitfinex FRR and uses `max(MIN_DAILY_RATE, FRR + FRR_DELTA)` as the effective minimum daily rate for that currency.

`MAX_TO_LEND` and `MAX_PERCENT_TO_LEND` restrict lendable balance when the best market rate is at or below `MAX_TO_LEND_RATE`. Keep `MAX_TO_LEND_RATE=0` to apply the limit whenever there is a positive market rate. `MAX_AMOUNT_TO_LEND` is retained as an alias for existing env files.

## Operations

- Set `BOT_MAX_LOOPS=0` for continuous execution.
- Use `RETRY_ATTEMPTS` and `RETRY_BACKOFF_SECONDS` for transient failure retries.
- Authentication failures are not retried; fix the key/secret or permissions before restarting.
- On startup, interrupted `running` bot runs are marked as `failed`.
- Use `auto-lending-bot cleanup` to delete old market-rate rows based on `MARKET_RATE_RETENTION_DAYS`.
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
