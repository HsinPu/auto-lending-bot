# Bitfinex Dry-Run Workflow

Use this workflow after `docs/bitfinex-smoke-checklist.md` passes. Dry-run mode reads Bitfinex data and records simulated offers locally, but it must not place real lending offers.

## 1. Start From Safe Env

```powershell
Copy-Item .env.bitfinex.example .env
```

Fill in only the API credentials first:

```env
EXCHANGE_API_KEY=your-key
EXCHANGE_API_SECRET=your-secret
```

Keep these safety settings:

```env
EXCHANGE=bitfinex
BOT_DRY_RUN=true
ALLOW_LIVE_TRADING=false
BITFINEX_ENABLE_LIVE_OFFERS=false
BOT_MAX_LOOPS=1
STRATEGY_DEBUG=true
```

## 2. Run Read-Only Smoke Test

```powershell
docker compose run --rm --env-file .env auto-lending-bot auto-lending-bot smoke-exchange
```

Continue only after balances, loan orders, and best daily rate look plausible.

## 3. Run One Dry-Run Cycle

```powershell
docker compose run --rm --env-file .env auto-lending-bot auto-lending-bot run
```

Local Python equivalent:

```powershell
uv run auto-lending-bot run
```

With `STRATEGY_DEBUG=true`, inspect the log for each currency:

- balance amount
- observed best daily rate
- configured min and max daily rates
- skip reason when no offer is generated
- generated offer count

## 4. Review Local State

```powershell
docker compose run --rm --env-file .env auto-lending-bot auto-lending-bot status
```

Confirm the `status` output and SQLite records show:

- mode is `模擬模式`
- latest run completed successfully
- simulated loan offers match the expected currency, amount, rate, and duration
- no failed offer warning appears

Optionally sync recent lending history for `SMOKE_TEST_CURRENCY`:

```powershell
docker compose run --rm --env-file .env auto-lending-bot auto-lending-bot sync-history
```

## 5. Iterate Strategy Settings

Tune global or per-currency settings in `.env`:

```env
MIN_DAILY_RATE=0.00005
MAX_DAILY_RATE=0.05
BTC_MIN_DAILY_RATE=0.00008
BTC_MAX_PERCENT_TO_LEND=80
BTC_MAX_AMOUNT_TO_LEND=0.1
BTC_FRR_AS_MIN=true
BTC_FRR_DELTA=0.00001
```

`FRR_AS_MIN=true` is the default Bitfinex calibration. After the smoke test succeeds, verify the fetched flash return rate in a dry-run cycle; the bot uses `max(MIN_DAILY_RATE, FRR + FRR_DELTA)` as the effective minimum daily rate.

Run another single dry-run cycle after each change. Keep `BOT_MAX_LOOPS=1` while calibrating.

## 6. Optional Continuous Dry-Run

Only after one-cycle dry-runs look correct:

```env
BOT_MAX_LOOPS=0
BOT_SLEEP_SECONDS=60
```

Then run:

```powershell
docker compose run --rm --env-file .env auto-lending-bot auto-lending-bot run
```

Stop the process before changing strategy or safety settings.

Do not proceed to live mode until the pre-live checklist passes.
