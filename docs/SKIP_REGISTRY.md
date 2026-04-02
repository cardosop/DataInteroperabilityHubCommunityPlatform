# Skip Registry

**Document Version**: 1.0.0
**Last Updated**: 2026-03-26
**Status**: Active
**Policy**: Every `pytest.mark.skip` or `skipIf` must be registered here with owner, reason, and target fix date.

---

## Policy

- No bare `@pytest.mark.skip` without a reason string
- All skips must reference a category: INFRA, DEFERRED, FLAKY, EXTERNAL_DEP
- Skips are reviewed monthly; stale entries are either fixed or escalated
- PRs must not introduce new skips without updating this registry

## E2E Skips

| Test                           | Reason                                    | Category      | Owner        | Target Fix |
|--------------------------------|-------------------------------------------|---------------|-------------|------------|
| Vault integration tests        | vault binary not available in CI container | external-dep  | Infra Team  | N/A        |

## Backend Skips

| Test                                          | Reason                                          | Category      | Owner        | Target Fix |
|-----------------------------------------------|------------------------------------------------|---------------|-------------|------------|
| test_revoked_token_replay_triggers_family_revocation | Login did not return refresh cookie in test env | infra         | Auth Team   | 2026-04-15 |

## Frontend Skips

| Test                           | Reason                                    | Category      | Owner        | Target Fix |
|--------------------------------|-------------------------------------------|---------------|-------------|------------|
| (none currently)               |                                           |               |             |            |
