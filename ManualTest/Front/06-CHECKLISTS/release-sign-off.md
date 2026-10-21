# Release Sign-Off Checklist

**Version**: 1.0.0  
**Last Updated**: 2026-02-17

---

## Purpose

Final sign-off before releasing a frontend build. Ensures critical paths are validated and no regressions are introduced.

---

## Pre-Release Checklist

### Environment

- [ ] Backend running and healthy
- [ ] Frontend built and served (or dev server)
- [ ] Test users created (`ensure_e2e_user_roles`, `ensure_e2e_subscription`)
- [ ] VITE_PROXY_TARGET correct for API

### Smoke

- [ ] [smoke-test.md](smoke-test.md) passed

### Auth & Visitor

- [ ] [JOURNEY-AUTH-001](../03-USER-JOURNEYS/auth/JOURNEY-AUTH-001.md) — Registration (when enabled)
- [ ] [JOURNEY-AUTH-002](../03-USER-JOURNEYS/auth/JOURNEY-AUTH-002.md) — Login
- [ ] [JOURNEY-AUTH-003](../03-USER-JOURNEYS/auth/JOURNEY-AUTH-003.md) — Password reset (when enabled)
- [ ] [JOURNEY-AUTH-004](../03-USER-JOURNEYS/auth/JOURNEY-AUTH-004.md) — Public resources

### Core Personas (Minimum)

- [ ] [Data Product Owner](../04-PERSONAS/data-product-owner.md) — Key journeys (DPO-001, 002, 005, 015, 016)
- [ ] [Data Consumer](../04-PERSONAS/data-consumer.md) — Key journeys (DC-001, 002, 003, 015)
- [ ] [Data Engineer](../04-PERSONAS/data-engineer.md) — Key journeys (DE-001, 003, 006)
- [ ] [Compliance Officer](../04-PERSONAS/compliance-officer.md) — Key journeys (CPO-001, 002, 003)
- [ ] [Tenant Admin](../04-PERSONAS/tenant-admin.md) — Key journeys (TA-001, 002, 008)
- [ ] [Platform Admin](../04-PERSONAS/platform-admin.md) — Key journeys (PA-001, 003)

### Cross-Cutting

- [ ] [alternate-flows.md](alternate-flows.md) — 404, 403, session

---

## Sign-Off

| Role | Name | Date | Approved |
|------|------|------|----------|
| QA Lead | | | ☐ |
| Release Manager | | | ☐ |

---

## Notes

- For full manual coverage, run [01-TEST-EXECUTION-SCRIPT.md](../01-TEST-EXECUTION-SCRIPT.md) end-to-end.
- Capability-gated journeys may be skipped if the capability is not enabled; document in Notes.
