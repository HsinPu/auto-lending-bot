# Profile Readiness Notes

This project currently runs as a single bot profile. There is no user account system and no multi-profile runtime yet. These notes document the current global coupling points so future changes can avoid making a later profile migration harder.

## Current Single-Profile Assumptions

- `Settings` in `src/auto_lending_bot/config.py` represents one global runtime configuration.
- `load_effective_settings()` reads global environment values and global SQLite overrides from `app_settings`.
- `AppSettingRepository` stores settings by key only; settings are not scoped by profile.
- `create_exchange_client(settings)` builds one exchange client from the active settings and API credentials.
- `BotRunner` receives one `Settings` object, one exchange client, and global repositories.
- API controllers in `src/auto_lending_bot/api/routes.py` create repositories directly from `settings.database_url` and operate on all rows.
- CLI commands in `src/auto_lending_bot/cli.py` create exchange clients, repositories, and runners for the single active settings set.
- Background loop state in the API is process-global and represents one running bot loop and one market-analysis collection loop.
- SQLite tables such as `bot_runs`, `bot_run_decisions`, `bot_run_steps`, `loan_offers`, `active_loans`, `open_loan_offers`, `lending_history`, `market_rates`, and `market_analysis_rates` do not include profile scope.
- Dashboard API responses describe the active bot, not a selected profile.

## Boundaries To Keep Clean

- Keep settings loading behind `load_effective_settings()` rather than reading `app_settings` directly in feature code.
- Keep runner construction centralized so future profile-specific runners can share one creation path.
- Keep exchange client creation behind `create_exchange_client(settings)`.
- Keep data access through repository or service methods, not direct SQL in API handlers.
- Avoid adding new module-level mutable runtime state unless it clearly belongs to the single active bot process.
- Keep new API response fields additive so a future `profile` object can be introduced without breaking current clients.

## Future Migration Shape

If profile support is needed later, the likely migration path is:

1. Add a default bot profile concept in code while keeping current behavior unchanged.
2. Pass a profile context through settings loading, runner creation, and API actions.
3. Add a `bot_profiles` table and seed a default profile.
4. Scope settings, runs, offers, loans, history, and market-analysis rows by profile.
5. Add profile-aware API routes while keeping existing routes mapped to the default profile.
6. Add frontend profile selection after backend data isolation exists.

Do not add login or user-account behavior as part of these readiness steps.
