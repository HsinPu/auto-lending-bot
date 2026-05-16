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
- `GET /api/settings/schema`
- `GET /api/settings/effective`
- `GET /api/settings/values`
- `PUT /api/settings/values`
- `POST /api/settings/reset`
- `GET /api/settings/export`
- `POST /api/settings/import`
- `GET /api/settings/audit-log`
- `POST /api/actions/smoke-exchange`
- `POST /api/actions/sync-history`
- `POST /api/actions/sync-open-offers`
- `POST /api/actions/transfer-preview`
- `POST /api/actions/transfer-funds`
- `POST /api/actions/cancel-open-offers`
- `POST /api/actions/cleanup`
- `POST /api/actions/run-once`
- `POST /api/actions/record-market-analysis`

## Run Once Order Flow

`POST /api/actions/run-once` follows the same business flow as the dashboard's run-once
modal. In dry-run mode the bot records local offer rows only; in live mode the Bitfinex
offer is submitted only after the live confirmation and amount guards pass.

| Order | Step | What happens |
|---:|---|---|
| 1 | Create run | Start a `bot_runs` row for this execution. |
| 2 | Read previous active loans | Read the local active-loan snapshot used for fill detection. |
| 3 | Read exchange active loans | Read currently filled lending loans from the exchange. |
| 4 | Replace active loans | Refresh the local active-loan snapshot. |
| 5 | Detect new active loans | Compare previous and current active loans for fill notifications. |
| 6 | Read lending balances | Read available Funding/Lending wallet balances. |
| 7 | Check open-offer rebalance setting | Record whether open-offer sync should run. |
| 8 | Sync open offers | Read open offers when rebalance is enabled, otherwise record `skipped`. |
| 9 | Replace open offers | Refresh the local open-offer snapshot when available. |
| 10 | Check cancel setting | Record whether old offers may be canceled. |
| 11 | Evaluate open-offer cancel | Decide per open offer whether it should be kept or canceled. |
| 12 | Cancel open offer | Cancel a specific old offer when live canceling is enabled. |
| 13 | Load market orders | For each available currency, read the current lending order book. |
| 14 | Record market orders | Store the market-rate snapshot in SQLite. |
| 15 | Load strategy config | Load per-currency strategy settings and overrides. |
| 16 | Load FRR rate | Read FRR when `FRR_AS_MIN=true`, otherwise record `skipped`. |
| 17 | Load market-analysis rate | Read the suggested minimum daily rate from local analysis data. |
| 18 | Calculate active amount | Calculate the currently active lending amount for the currency. |
| 19 | Load BTC price | Read BTC conversion price when the strategy needs it, otherwise record `skipped`. |
| 20 | Calculate decisions | Decide whether each currency should create offers, including amount, rate, and duration. |
| 21 | Record decisions | Store the per-run decision snapshot for dashboard review. |
| 22 | Prepare offers | Convert decisions into the offers that should be recorded or submitted. |
| 23A | Record dry-run offer | In dry-run mode, write one local `status=dry_run` row per offer; no exchange order is sent. |
| 23B | Validate live offer | In live mode, check single-offer and run-total lending limits before each offer. |
| 24B | Record live intent | Write one local `status=intent` row before each exchange request. |
| 25B | Submit live offer | Submit each lending offer to Bitfinex. |
| 26B | Update offer result | Mark the local offer `created` with the exchange ID, or `failed` with the error. |
| 27 | X-day notification | Record whether a long-duration offer notification was sent or skipped. |
| 28 | Finish run | Mark the run `completed` or `failed` with a summary message. |
| 29 | Run summary notification | Record the run-summary notification action. |
| 30 | Periodic summary notification | Send or skip the periodic lending summary based on settings. |
| 31 | Error notification | On failures, send or skip the error notification based on settings. |

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
- `ALLOW_ABOVE_MARKET_OFFERS`
- `SPREAD_LEND`
- `MAX_OFFER_AMOUNT`
- `MIN_OFFER_REMAINDER`
- `GAP_MODE`
- `GAP_BOTTOM`
- `GAP_TOP`
- `XDAY_THRESHOLD`
- `XDAYS`
- `XDAY_SPREAD`
- `END_DATE`
- `FRR_AS_MIN`
- `FRR_DELTA`
- `RATE_OPTIMIZATION_MODE`
- `RATE_OPTIMIZATION_MIN_PROBABILITY`
- `RATE_OPTIMIZATION_SAMPLE_SIZE`
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
BTC_SPREAD_LEND=0
BTC_MAX_OFFER_AMOUNT=500
BTC_MIN_OFFER_REMAINDER=100
BTC_MAX_PERCENT_TO_LEND=80
BTC_MAX_TO_LEND=0.1
BTC_MAX_TO_LEND_RATE=0.00008
BTC_MAX_AMOUNT_TO_LEND=0.1
BTC_MAX_ACTIVE_AMOUNT=0.5
BTC_ALLOW_ABOVE_MARKET_OFFERS=true
BTC_HIDE_COINS=true
BTC_GAP_MODE=raw_btc
BTC_GAP_BOTTOM=20
BTC_GAP_TOP=100
BTC_XDAY_THRESHOLD=0.0005479452054794521
BTC_XDAYS=120
BTC_XDAY_SPREAD=0
BTC_END_DATE=2027-01-15
BTC_FRR_AS_MIN=true
BTC_FRR_DELTA=0.00001
BTC_RATE_OPTIMIZATION_MODE=fill_probability
BTC_RATE_OPTIMIZATION_MIN_PROBABILITY=0.10
BTC_RATE_OPTIMIZATION_SAMPLE_SIZE=50
```

`FRR_AS_MIN=true` is the default Bitfinex strategy calibration. When enabled, the bot reads Bitfinex FRR and uses `max(MIN_DAILY_RATE, FRR + FRR_DELTA)` as the effective minimum daily rate for that currency.

`ALLOW_ABOVE_MARKET_OFFERS=true` is enabled by default. When the best market rate is below the effective minimum rate, the bot may still create offers at the effective minimum rate instead of skipping the currency. Set it to `false` to keep the older behavior where below-minimum markets are hidden when `HIDE_COINS=true`.

`MAX_OFFER_AMOUNT=500` is enabled by default and makes the strategy split lendable balance by maximum offer size instead of a fixed number of offers. `MIN_OFFER_REMAINDER=100` keeps the final remainder unoffered when it is less than or equal to that amount. Set `MAX_OFFER_AMOUNT=` to disable amount-based splitting and fall back to `SPREAD_LEND`.

`MAX_TO_LEND` and `MAX_PERCENT_TO_LEND` restrict lendable balance when the best market rate is at or below `MAX_TO_LEND_RATE`. Keep `MAX_TO_LEND_RATE=0` to apply the limit whenever there is a positive market rate. `MAX_AMOUNT_TO_LEND` is retained as an alias for existing env files.

`END_DATE=YYYY-MM-DD` caps offer duration so new loans finish before the date. When two or fewer days remain, the strategy stops creating new lending offers.

By default, `XDAY_THRESHOLD=0.0005479452054794521`, `XDAYS=120`, and `XDAY_SPREAD=0`, so offers stay at 2 days unless the selected offer rate reaches roughly 20% annualized. At or above that threshold, the bot uses 120 days.

`GAP_MODE=raw_btc` treats `GAP_BOTTOM` and `GAP_TOP` as BTC-denominated lendbook depth, matching Mika's `RawBTC` behavior when a BTC conversion price is available.

`RATE_OPTIMIZATION_MODE=fill_probability` compares candidate offer rates against recent top-level market analysis samples. It estimates how often each candidate would have been fillable, scores candidates by `daily rate * fill probability`, and uses the best-scoring rates. The defaults use `RATE_OPTIMIZATION_SAMPLE_SIZE=50` and `RATE_OPTIMIZATION_MIN_PROBABILITY=0.10` so the strategy reacts faster when market lending rates rise. When there are no usable samples, the bot falls back to the configured `GAP_MODE` behavior.

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

Live transfers require `BOT_DRY_RUN=false`, `ALLOW_LIVE_TRADING=true`,
`ALLOW_BALANCE_TRANSFERS=true`, `BITFINEX_ENABLE_LIVE_TRANSFERS=true`,
`MAX_TOTAL_TRANSFER_AMOUNT`, `MAX_SINGLE_TRANSFER_AMOUNT`, and an explicit API/CLI live
confirmation.

Managed settings writes and live actions require `ADMIN_AUTH_TOKEN` via
`Authorization: Bearer <token>`.

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
