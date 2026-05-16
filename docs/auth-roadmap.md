# Auth Roadmap

The current dashboard uses a temporary backend/admin authorization code for protected remote operations. This is intentionally smaller than a login system and should remain isolated until multi-user or multi-profile operation is needed.

## Current Boundary

- Local backend requests can write settings and trigger protected actions without `ADMIN_AUTH_TOKEN`.
- Remote dashboard/API requests must send `Authorization: Bearer <ADMIN_AUTH_TOKEN>` for managed setting writes, settings imports/resets, dry-run reset, and live run/cancel/transfer actions.
- The authorization code does not replace live safety checks. Live actions still require dry-run to be disabled, live flags to be enabled, limits to be configured, and explicit live confirmation.
- There are no users, sessions, roles, or profile ownership checks today.

## Target Model

Add authentication only after there is a concrete need for multiple operators, hosted remote access, or multiple bot profiles.

The target model should include:

- Login with server-side session or short-lived access token plus refresh/session rotation.
- Roles: `admin`, `operator`, and `viewer`.
- Profile ownership or profile access grants before any profile-scoped settings, runs, offers, or history can be read or changed.
- Sensitive action re-authentication or explicit confirmation for live run, live transfer, cancel open offers, credential changes, and safety-limit changes.
- Audit log entries that include actor, profile, action, source IP, timestamp, and changed keys without storing secret values.

## Role Shape

- `admin`: manage users, profile access, credentials, safety settings, and all bot actions.
- `operator`: view assigned profiles, adjust non-secret strategy settings, and start/stop dry-run or approved live operations.
- `viewer`: read assigned profile dashboards, runs, offers, and history without writing settings or triggering actions.

## Migration Path

1. Keep protected-route checks centralized behind the backend/admin helper boundary.
2. Add user/session storage and password or external identity provider support.
3. Add an auth dependency that resolves the current actor and allowed profile IDs.
4. Replace the temporary `ADMIN_AUTH_TOKEN` check with role/profile checks at the same protected-route boundary.
5. Add profile ownership checks before exposing non-default profiles in API responses.
6. Add sensitive-action re-authentication for live operations and credential/safety updates.
7. Deprecate `ADMIN_AUTH_TOKEN` after hosted login/session auth covers all protected remote operations.

## Non-Goals For Now

- Do not add login UI before backend data is profile-scoped where needed.
- Do not add multi-account exchange credentials without profile access checks.
- Do not let any auth path bypass `safety.py` live guards.
