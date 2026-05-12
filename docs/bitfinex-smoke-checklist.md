# Bitfinex Smoke Test Checklist

Use this checklist before any Bitfinex dry-run or live lending test. The smoke command is read-only and must not create, cancel, or modify offers.

## 1. Prepare Credentials

- Create a Bitfinex API key without withdrawal permissions.
- Keep `BOT_DRY_RUN=true` and `ALLOW_LIVE_TRADING=false`.
- Start from `.env.bitfinex.example` and fill only `EXCHANGE_API_KEY` and `EXCHANGE_API_SECRET`.

```powershell
Copy-Item .env.bitfinex.example .env
```

## 2. Confirm Safe Settings

Check these values before running the command:

```env
EXCHANGE=bitfinex
BOT_DRY_RUN=true
ALLOW_LIVE_TRADING=false
BITFINEX_ENABLE_LIVE_OFFERS=false
SMOKE_TEST_CURRENCY=BTC
```

Do not set `BOT_DRY_RUN=false` for smoke tests.

## 3. Run Read-Only Smoke Test

```powershell
docker compose run --rm --env-file .env auto-lending-bot auto-lending-bot smoke-exchange
```

Local Python equivalent:

```powershell
uv run auto-lending-bot smoke-exchange
```

## 4. Expected Checks

- The command exits successfully.
- Lending balances are returned or reported as zero without an authentication error.
- Loan orders are returned for `SMOKE_TEST_CURRENCY`.
- Best daily rate is present and plausible for the selected currency.
- Open loan offer count can be read.
- No new live offer appears in Bitfinex after the command.

## 5. If It Fails

- Authentication error: verify API key, secret, and permissions.
- Empty or unexpected currency data: confirm `SMOKE_TEST_CURRENCY` is supported by Bitfinex funding.
- Network or rate-limit error: retry later; authentication errors are not retried by the bot.
- Implausible rate: keep `BOT_DRY_RUN=true`, enable `STRATEGY_DEBUG=true`, and inspect dry-run output before considering live mode.

Proceed to a Bitfinex dry-run only after this checklist passes.
