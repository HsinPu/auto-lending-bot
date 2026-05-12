# Pre-Live Safety Checklist

Use this checklist immediately before any guarded live lending test. Do not enable live mode until every item passes.

## 1. Account And API Key

- API key has no withdrawal permission.
- API key is dedicated to this bot or this small beta test.
- Bitfinex account funding wallet contains only the amount you are willing to test.
- You can log in to Bitfinex and manually inspect or cancel funding offers if needed.

## 2. Read-Only Smoke Test Passed

Run the smoke checklist first:

```powershell
docker compose run --rm --env-file .env auto-lending-bot auto-lending-bot smoke-exchange
```

Confirm:

- authentication succeeds
- balances can be read
- lendbook data can be read
- best daily rate is plausible
- no live offer is created

## 3. Dry-Run Passed

Run at least one single-loop dry-run:

```powershell
docker compose run --rm --env-file .env auto-lending-bot auto-lending-bot run
docker compose run --rm --env-file .env auto-lending-bot auto-lending-bot status
```

Confirm in `status` and the SQLite records:

- mode is `模擬模式`
- latest run is successful
- generated simulated offers match the intended currency
- generated amounts are small and expected
- generated daily rates and durations are acceptable
- there is no failed offer warning

## 4. Safety Limits Are Set

Set explicit live limits before changing `BOT_DRY_RUN`:

```env
MAX_TOTAL_LEND_AMOUNT=1
MAX_SINGLE_OFFER_AMOUNT=0.1
```

Use smaller values for the first test. These limits are required by safety guards.

## 5. Live Flags Are Explicit

Only after the previous sections pass, set all live flags together:

```env
EXCHANGE=bitfinex
BOT_DRY_RUN=false
ALLOW_LIVE_TRADING=true
BITFINEX_ENABLE_LIVE_OFFERS=true
BOT_MAX_LOOPS=1
```

Keep `BOT_MAX_LOOPS=1` for the first live test. Do not start continuous live mode for the first run.

## 6. First Live Run

Run one live cycle:

```powershell
docker compose run --rm --env-file .env auto-lending-bot auto-lending-bot run
```

Immediately check:

- command output includes the live lending warning
- Bitfinex shows only the expected small offer
- local records show live mode
- latest run is successful or the failed warning explains what happened
- local offer row has `created` plus an exchange offer id, or `failed` plus an error message

## 7. Stop Conditions

Stop and return to dry-run if any of these happen:

- generated amount is larger than expected
- generated rate is implausible
- local offer records show failed offers
- Bitfinex shows an unexpected offer
- authentication or permission errors appear
- you need to change strategy settings

After stopping, set:

```env
BOT_DRY_RUN=true
ALLOW_LIVE_TRADING=false
BITFINEX_ENABLE_LIVE_OFFERS=false
```

Then repeat smoke test and dry-run before trying live again.
