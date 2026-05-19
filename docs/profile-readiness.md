# Profile Readiness Notes

This project currently runs as a single bot profile. There is no user account system and no multi-profile runtime yet. These notes document the current global coupling points so future changes can avoid making a later profile migration harder.

## Current Single-Profile Assumptions

- `Settings` in `src/auto_lending_bot/config.py` represents one global runtime configuration.
- `load_effective_settings()` reads global environment values and global SQLite overrides from `app_settings`.
- `AppSettingRepository` stores settings by key only; settings are not scoped by profile.
- `create_exchange_client(settings)` builds one exchange client from the active settings and default-profile API credentials.
- `BotRunner` receives one `Settings` object, one exchange client, and global repositories.
- API controllers operate on the default profile and read default-profile scoped runtime rows.
- CLI commands in `src/auto_lending_bot/cli.py` create exchange clients, repositories, and runners for the single active settings set.
- Background loop state in the API is process-global and represents one running bot loop and one market-analysis collection loop.
- Runtime tables such as `bot_runs`, `bot_run_decisions`, `bot_run_steps`, `loan_offers`, `active_loans`, `open_loan_offers`, `lending_history`, `market_rates`, `market_analysis_rates`, and `notification_state` include `profile_id`, but only the default profile is accepted today.
- Dashboard API responses describe the active bot, not a selected profile.

## Current Profile-Ready Boundaries

- `src/auto_lending_bot/profiles.py` defines `DEFAULT_PROFILE_CONTEXT` and rejects non-default profiles for now.
- `load_effective_settings(..., profile_context=DEFAULT_PROFILE_CONTEXT)` accepts profile context but still reads global settings.
- `create_exchange_client(..., profile_context=DEFAULT_PROFILE_CONTEXT)` accepts profile context but still returns the same mock or Bitfinex client.
- `ExchangeCredentialProvider` isolates credential lookup; it currently returns `settings.api_key` and `settings.api_secret`.
- `create_repository_bundle(..., profile_context=DEFAULT_PROFILE_CONTEXT)` centralizes repository creation; repositories still use unscoped tables.
- `BotActionService` centralizes run-once, loop start/stop, and dry-run reset orchestration for the default profile.
- `DashboardReadService` centralizes read-only dashboard queries for the default profile.
- API runtime controllers are wrapped with profile context, but there is still only one process-local bot loop and one market-analysis loop.
- Continuous loop starts create `bot_jobs` rows with `profile_id` and a settings snapshot. The running job uses that snapshot until stopped, so later setting edits require a new job to take effect.
- API startup restores the newest default-profile `running` bot job from its saved snapshot. `stopping` jobs are reconciled to `stopped`, and older extra `running` jobs are marked `failed` because the current runtime can only own one loop.
- Runtime repositories write and query default-profile rows for runs, offers, snapshots, lending history, market data, and notification state. This is data-isolation groundwork only; it does not enable multi-account execution or profile selection.

## Boundaries To Keep Clean

- Keep settings loading behind `load_effective_settings()` rather than reading `app_settings` directly in feature code.
- Keep environment variables limited to bootstrap, deployment, and fallback concerns.
- Keep runner construction centralized so future profile-specific runners can share one creation path.
- Keep exchange client creation behind `create_exchange_client(settings)`.
- Keep credential lookup behind `ExchangeCredentialProvider` rather than passing profile-specific secrets directly to exchange adapters.
- Keep repository creation behind `create_repository_bundle()` when adding new runtime/API surfaces.
- Keep bot action orchestration behind `BotActionService` instead of growing route handlers.
- Keep dashboard aggregation behind `DashboardReadService` instead of adding ad hoc route-level repository queries.
- Keep data access through repository or service methods, not direct SQL in API handlers.
- Avoid adding new module-level mutable runtime state unless it clearly belongs to the single active bot process.
- Keep new API response fields additive so a future `profile` object can be introduced without breaking current clients.

## Environment Boundary

Environment variables are still supported as safe bootstrap and fallback values, but they should not be the primary home for account/profile behavior. New account-specific behavior should prefer dashboard-managed DB settings.

Keep these in env because the app needs them before it can safely read profile settings:

- `DATABASE_URL`: tells the app which database contains settings and runtime data.
- `SETTINGS_ENCRYPTION_KEY`: decrypts secret settings; do not store this in the same SQLite database.
- `ADMIN_AUTH_TOKEN`: temporary backend/admin authorization code for non-local settings and protected live action endpoints.
- Deployment/runtime process settings such as `LOG_LEVEL`, bind host/port, and container-specific values.

Prefer dashboard/DB profile settings for values that belong to a bot account or strategy:

- Exchange selection and credentials.
- Dry-run/live safety toggles and live amount limits.
- Currency selection, output currency, market analysis behavior, and strategy parameters.
- Notification settings that should differ per profile.

The intended operating model is `.env` for bootstrap, dashboard-managed settings for bot/account behavior, and `.env` fallback only when the database has no override.

## Backend Admin Mode

The current dashboard is a backend/admin UI for one trusted operator. It is not a login, session, role, or multi-user account system.

Current authorization behavior:

- Local backend requests can write settings and trigger protected actions without `ADMIN_AUTH_TOKEN`.
- Remote backend requests must send `Authorization: Bearer <ADMIN_AUTH_TOKEN>` for managed setting writes, settings imports/resets, dry-run reset, and live run/cancel/transfer actions.
- Live actions still require the normal safety flags, amount limits, and explicit live confirmation; the backend/admin token does not bypass safety checks.

Keep this boundary isolated so a later login/session system can replace the temporary token check without rewriting every route.

## Settings Scope Contract

Settings are scoped to the single default profile today. The categories below are the contract for keeping those defaults ready for a later multi-profile migration.

The dashboard-managed setting schema exposes this as `scope` metadata from `src/auto_lending_bot/settings_registry.py`:

- `global`: process/deployment level settings.
- `profile`: per-profile strategy, exchange choice, market selection, and notification behavior.
- `profile_secret`: per-profile encrypted secrets such as exchange or notification credentials.
- `profile_safety`: per-profile live trading/transfer guard settings that may also need global ceilings later.

### Global Runtime Settings

These should usually stay process/global because they describe deployment behavior, retention, display, or API operation rather than a lending profile.

- `DATABASE_URL`
- `LOG_LEVEL`
- `DISPLAY_TIMEZONE`
- `ADMIN_AUTH_TOKEN`
- `SETTINGS_ENCRYPTION_KEY`
- `HTTP_TIMEOUT_SECONDS`
- `MARKET_RATE_RETENTION_DAYS`
- `MARKET_ANALYSIS_RETENTION_DAYS`
- `NOTIFICATION_WEBHOOK_URL`, unless notifications become per profile later.

### Profile Strategy Settings

These should become profile-scoped if multiple bot profiles are added because they affect lending decisions.

- Base strategy: `MIN_DAILY_RATE`, `MAX_DAILY_RATE`, `MAX_AMOUNT_TO_LEND`, `MAX_PERCENT_TO_LEND`, `MIN_OFFER_AMOUNT`, `SPREAD_LEND`
- Offer splitting and fill preference: `MAX_OFFER_AMOUNT`, `MIN_OFFER_REMAINDER`, `MIN_OFFER_VALUE_USD`, `LENDING_RISK_LEVEL`
- Duration logic: `DEFAULT_PERIOD_DAYS`, `XDAY_THRESHOLD`, `XDAYS`, `XDAY_SPREAD`
- Market logic: `GAP_MODE`, `GAP_BOTTOM`, `GAP_TOP`, `MACD_FAST`, `MACD_SLOW`, `MACD_SIGNAL`
- FRR logic: `FRR_AS_MIN`, `FRR_DELTA`
- Rate optimization: `RATE_OPTIMIZATION_MODE`, `RATE_OPTIMIZATION_MIN_PROBABILITY`, `RATE_OPTIMIZATION_SAMPLE_SIZE`
- Per-currency overrides such as `USD_MIN_DAILY_RATE` and other `<CURRENCY>_...` strategy keys.

### Profile Exchange Settings

These should become profile-scoped because they define which exchange account/profile a bot uses.

- `EXCHANGE`
- `BITFINEX_API_KEY`
- `BITFINEX_API_SECRET`
- `SMOKE_TEST_CURRENCY`
- `MARKET_ANALYSIS_CURRENCIES`
- `OUTPUT_CURRENCY`

### Profile Safety Settings

These likely need to be profile-scoped, but some may also require global deployment-level ceilings before live multi-profile operation.

- `BOT_DRY_RUN`
- `ALLOW_LIVE_TRADING`
- `BITFINEX_ENABLE_LIVE_OFFERS`
- `MAX_TOTAL_LEND_AMOUNT`
- `MAX_SINGLE_OFFER_AMOUNT`
- `ALLOW_ABOVE_MARKET_OFFERS`
- `ALLOW_BALANCE_TRANSFERS`
- `BITFINEX_ENABLE_LIVE_TRANSFERS`
- `MAX_TOTAL_TRANSFER_AMOUNT`
- `MAX_SINGLE_TRANSFER_AMOUNT`

### Runtime Scheduling Settings

These are currently global. If multiple profiles run concurrently later, decide whether each profile gets its own loop cadence or whether one scheduler owns all profiles.

- `BOT_MAX_LOOPS`
- `BOT_SLEEP_SECONDS`
- `BOT_INACTIVE_SLEEP_SECONDS`
- `RETRY_ATTEMPTS`
- `RETRY_BACKOFF_SECONDS`
- `MARKET_ANALYSIS_INTERVAL_SECONDS`
- `MARKET_ANALYSIS_LEVELS`
- `MARKET_ANALYSIS_MAX_AGE_SECONDS`

## Future Migration Shape

If profile support is needed later, the likely migration path is:

1. Add a default bot profile concept in code while keeping current behavior unchanged. This is currently represented by `DEFAULT_PROFILE_CONTEXT`.
2. Pass a profile context through settings loading, runner creation, and API actions.
3. Add a `bot_profiles` table and seed a default profile.
4. Scope settings, runs, offers, loans, history, and market-analysis rows by profile.
5. Scope job execution by profile using `bot_jobs.profile_id` and one active job per runnable profile.
6. Replace the single-loop restore path with a profile-aware scheduler that can restore one safe running job per runnable profile after process restart.
7. Add profile-aware API routes while keeping existing routes mapped to the default profile.
8. Add frontend profile selection after backend data isolation exists.

Do not add login or user-account behavior as part of these readiness steps.
