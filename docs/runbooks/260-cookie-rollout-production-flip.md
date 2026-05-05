# Phase 260.B — production HttpOnly-cookie flip runbook

**Phase:** 260.B (Acceptance #2 + #3 + #5 — production cookie default-on)
**Owner:** Auth Engineering Lead + SRE on-call
**Last reviewed:** 2026-05-05

## Purpose

Closes the production half of the cookie-mode rollout: flipping
`USE_HTTPONLY_AUTH_COOKIES=true` on production via Helm, after staging
has soaked for 14 days with zero CLI/SDK regressions.

## Prerequisites — DO NOT skip

All of the following must be true. Re-check each one even if you think
you remember the answer:

- [ ] Staging has been running with `USE_HTTPONLY_AUTH_COOKIES=true`
      for ≥ 14 days. The setting defaults to ON for staging via
      [hub/settings.py:1701-1704](../../hub/settings.py#L1701-L1704),
      so confirm via:

      ```bash
      kubectl -n hub-staging exec deploy/api -- \
        python -c "from django.conf import settings; print(settings.USE_HTTPONLY_AUTH_COOKIES)"
      ```

      Expected output: `True`.

- [ ] [docs/audit-reports/260-cookie-rollout-nightly-ledger.md](../audit-reports/260-cookie-rollout-nightly-ledger.md)
      has 14 consecutive `green` rows AND the closure block has all
      three signatures (Auth Engineering Lead, SRE on-call, EM).

- [ ] Staging cookie smoke has fired green within the last 24 h:

      ```bash
      gh run list --workflow="cli-sdk-nightly-regression.yml" \
        --limit 1 --json status,conclusion,createdAt
      ```

- [ ] No auth-related P1/P2 incidents in the production incident tracker
      within the prerequisite window.

- [ ] The frontend [`refresh_token` localStorage cleanup](../../frontend/src/features/auth/services/authService.ts#L254)
      has been deployed to production for ≥ 1 release cycle. Confirm
      via the frontend deploy log AND a manual check:

      ```javascript
      // In browser devtools on production after a fresh login:
      localStorage.getItem('refresh_token')
      // Expected: null
      ```

If any prerequisite fails, **stop**. Re-establish the gate and resume
when the ledger is back to 14 clean green rows.

## Procedure

### 1. Pre-flight verification (in production, READ-ONLY)

```bash
# Confirm current production cookie mode
kubectl -n hub-production exec deploy/api -- \
  python -c "from django.conf import settings; print('cookie_mode_on=', settings.USE_HTTPONLY_AUTH_COOKIES)"

# Confirm cookie domain is set
kubectl -n hub-production exec deploy/api -- \
  python -c "from django.conf import settings; print('domain=', settings.SESSION_COOKIE_DOMAIN)"
```

Expected pre-flip:
- `cookie_mode_on=True` — already on by default in production via
  `hub/settings.py:1701-1704`. **If this is already True, the flip is
  a no-op at the env level and the runbook is purely about removing
  the legacy `helm/values.yaml` comment + verifying production
  behaviour. Skip to step 4.**
- `domain=.meshant.com`

### 2. Edit `helm/values.yaml` to make the flip explicit

Even if settings.py defaults to True, having Helm enforce the env var
explicitly is defence-in-depth: if a future env-driven override sets it
False, Helm wins. Open [helm/values.yaml](../../helm/values.yaml#L158)
and uncomment:

```yaml
# Before:
api:
  env:
    # USE_HTTPONLY_AUTH_COOKIES: "true"

# After:
api:
  env:
    USE_HTTPONLY_AUTH_COOKIES: "true"
```

Commit on a release branch:

```bash
git checkout -b release/260b-cookie-flip
git add helm/values.yaml
git commit -m "feat(260.B): production HttpOnly cookie default-on

Phase 260.B Acceptance #2/#3/#5 — flip USE_HTTPONLY_AUTH_COOKIES=true
in production helm values after 14-day staging soak. Settings.py
already defaults this to True for production; this commit makes the
override explicit so a future env-var regression cannot silently turn
it off.

Ledger: docs/audit-reports/260-cookie-rollout-nightly-ledger.md
Runbook: docs/runbooks/260-cookie-rollout-production-flip.md
"
git push origin release/260b-cookie-flip
```

### 3. Open the production deploy PR

Open the PR with the prerequisite checklist embedded:

```bash
gh pr create --title "260.B: production HttpOnly cookie flip" \
  --body "$(cat <<'EOF'
## Summary
Production cookie mode flip per Phase 260.B Acceptance #2/#3/#5.

## Prerequisites verified
- [x] 14 consecutive green nightly rows in
      docs/audit-reports/260-cookie-rollout-nightly-ledger.md
- [x] Closure block signed by Auth Lead + SRE + EM
- [x] No production auth P1/P2 in window
- [x] Frontend localStorage cleanup deployed ≥ 1 release cycle ago

## Test plan
- [ ] After deploy, verify `Set-Cookie: __Secure-refresh_token=...; HttpOnly; Secure; SameSite=Strict; Domain=.meshant.com`
      in production login response.
- [ ] Run `tests/smoke/test_cookie_mode.py` against production base URL.
- [ ] Manual browser check: `localStorage.getItem('refresh_token')` → null.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

### 4. Deploy + verify

After merge, the standard `Deploy` workflow rolls the change to
production. Verify with:

```bash
# Login and capture cookies — replace placeholders before running.
curl -s -i -X POST https://apimeshant-internal.example.com/api/v1/auth/login/ \
  -H 'Content-Type: application/json' \
  -d '{"email":"<test-admin>","password":"<password>"}' \
  | grep -i 'Set-Cookie:.*HttpOnly.*Secure.*SameSite=Strict.*Domain=\.meshant\.com'
```

A non-empty match closes Acceptance #2. Then run the cookie smoke
against production:

```bash
SMOKE_BASE_URL=https://apimeshant-internal.example.com \
SMOKE_ADMIN_EMAIL=<email> SMOKE_ADMIN_PASSWORD=<password> \
pytest tests/smoke/test_cookie_mode.py -v
```

### 5. Post-flip soak

- Monitor [auth-tenancy Grafana dashboard](../../monitoring/grafana/dashboards/auth-tenancy.json)
  for 48 h.
- Watch the `cross_tenant_denied_total`, login-success-rate, and
  refresh-token-rotation metrics. Any deviation > 2σ from the staging
  baseline triggers a rollback (step 6).

### 6. Rollback (only if needed)

```bash
# Re-comment USE_HTTPONLY_AUTH_COOKIES in helm/values.yaml,
# OR set it explicitly to "false" via a follow-up Helm value
# override (faster than a full PR cycle):
kubectl -n hub-production set env deploy/api USE_HTTPONLY_AUTH_COOKIES=false
kubectl -n hub-production rollout status deploy/api --timeout=5m
```

If a rollback fires, file a postmortem within 24 h and re-establish the
14-day staging gate before retrying.

## Sign-off

| Role | Name | Date |
|---|---|---|
| Auth Engineering Lead | _to be filled_ | _YYYY-MM-DD_ |
| SRE on-call lead | _to be filled_ | _YYYY-MM-DD_ |
| Engineering Manager | _to be filled_ | _YYYY-MM-DD_ |

Acceptance bullets close once steps 1–5 above have all completed
successfully and post-flip soak shows no regression.
