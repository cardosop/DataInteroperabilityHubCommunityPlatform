<!--
Phase 228 X (228.X.10) — required PR template.
Reviewers reject any PR with empty checklist sections; the bot
posts a comment listing which sections are blank.
-->

## Summary

<!-- 1-3 sentences. The "why", not the "what". -->

## Linked spec / ADR

<!-- spec / ADR links — REQUIRED. If none exists, link the issue.
     E.g. `openspec/changes/preprod01/specs/lineage-snapshots/spec.md`
     or `docs/adr/lineage/ADR-LIN-002.md`. -->

- spec:
- ADR:

## Test plan

<!-- Per 228.X.10: every PR carries a tested-or-tested-by-CI plan.
     Tick what applies. -->

- [ ] Backend unit tests added/updated (`hub/apps/<app>/tests/test_*.py`).
- [ ] Backend integration tests added/updated (real DB, no internal mocks).
- [ ] Frontend unit tests added/updated (`*.test.tsx`).
- [ ] Frontend E2E covered (`frontend/e2e/features/*.spec.ts`).
- [ ] OpenAPI surface verified (`python manage.py spectacular`) when adding/changing endpoints.
- [ ] No-test rationale documented below (when the change is doc-only / config-only).

## Rollback plan

<!-- 1-2 sentences. How does the on-call revert this if the dashboard
     trips? Reference the runbook + the rollback command. -->

## Feature flag

<!-- Tick one. -->

- [ ] No new flag (refactor / fix / docs).
- [ ] Behind capability flag (name): __________________________
- [ ] Phased rollout (Helm overlay + per-tenant allow-list).
- [ ] Default-OFF in prod + ON in test (per Phase 228 capability convention).

## Observability evidence

<!-- New behaviour must surface a metric or audit row. Tick what applies. -->

- [ ] Prometheus metric added (name): _________________________
- [ ] Audit-action constant added/used (name): _______________
- [ ] Grafana dashboard panel updated.
- [ ] Runbook added/updated (path): __________________________
- [ ] No new observability needed (rationale): _______________

## Security considerations

<!-- Tick what applies. -->

- [ ] No security-sensitive surface area touched.
- [ ] PII handled — redaction / encryption verified.
- [ ] Cross-tenant authorization checked.
- [ ] GDPR cascade verified (delete-cascades into archive + S3 if relevant).
- [ ] Data residency rules honored (REQ-LIN-X-004).

## Notes for reviewers

<!-- Anything tricky / non-obvious / context. -->

🤖 Generated with [Claude Code](https://claude.com/claude-code)
