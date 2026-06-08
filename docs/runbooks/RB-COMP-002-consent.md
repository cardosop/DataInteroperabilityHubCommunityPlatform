# RB-COMP-002 — Consent Subsystem (283.3.1)

**Date:** 2026-05-15  
**Feature flag:** `compliance_consent_enabled` (GA)  
**Audit events:** `CONSENT_GRANTED`, `CONSENT_REVOKED`, `CONSENT_PURPOSE_CHANGED`

## 1. Overview

The consent subsystem manages user consent records with cryptographic (HMAC) proofs. When `compliance_consent_enabled` is True, tenants can:

- Define consent purposes via `/api/v1/governance/consent-purposes/`
- Grant/revoke consent via `/api/v1/governance/consent-records/`
- View aggregate consent posture via `/api/v1/governance/consent-dashboard/`

Every mutation emits a durable audit event (`CONSENT_GRANTED`, `CONSENT_REVOKED`, or `CONSENT_PURPOSE_CHANGED`) so the audit log is the authoritative record of consent lifecycle.

## 2. Symptoms

### Consent grant returns 400

- **Symptom:** `POST /api/v1/governance/consent-records/` returns 400 with `PURPOSE_INACTIVE` or `SIGNING_KEYS_MISSING`
- **Expected:** The purpose is inactive or signing keys are not configured for the tenant
- **Response:** Check the purpose's `is_active` flag; verify `CONSENT_SIGNING_KEYS_JSON` setting has keys for the tenant

### Consent revoke returns 400

- **Symptom:** `POST /api/v1/governance/consent-records/{id}/revoke/` returns 400 with `PROOF_VERIFICATION_FAILED`
- **Expected:** The consent record's HMAC proof failed verification — possibly tampered or signing keys rotated without keeping prior keys
- **Response:** Check signing key ring configuration; ensure prior keys are retained for verification window

### Consent dashboard returns 403

- **Symptom:** `GET /api/v1/governance/consent-dashboard/` returns 403
- **Expected:** The user lacks DPO or TENANT_ADMIN role in the tenant
- **Response:** Assign the appropriate role; verify tenant scoping

### Audit events missing

- **Symptom:** Consent mutations succeed but no `CONSENT_GRANTED`/`CONSENT_REVOKED`/`CONSENT_PURPOSE_CHANGED` audit rows appear
- **Expected:** Every mutation path emits an audit event
- **Response:** Check audit DB connectivity; verify `create_audit_event` is not raising silently

## 3. Investigation Procedure

### 3.1 — Confirm flag state

```sql
SELECT id, name, slug, compliance_consent_enabled
FROM tenants_tenant
WHERE slug = '<tenant-slug>';
```

### 3.2 — Check audit trail

```
GET /api/v1/audit/events/?action=CONSENT_GRANTED&since=7d
GET /api/v1/audit/events/?action=CONSENT_REVOKED&since=7d
GET /api/v1/audit/events/?action=CONSENT_PURPOSE_CHANGED&since=7d
```

Look for:
- Which user granted/revoked consent (`actor_user_id`)
- Which purpose was affected (`details_json.purpose_key`)
- Whether the proof was verified (`details_json.proof_hmac` presence)

### 3.3 — Verify signing keys

```bash
python manage.py shell -c "
from django.conf import settings
keys = getattr(settings, 'CONSENT_SIGNING_KEYS_JSON', {})
print(f'Configured tenants: {list(keys.keys())}')
"
```

### 3.4 — Check consent record integrity

```bash
python manage.py shell -c "
from hub.apps.consent.services import ConsentService
from hub.apps.consent.models import ConsentRecord
for rec in ConsentRecord.objects.filter(status='GRANTED')[:50]:
    ok = ConsentService().verify_record_integrity(rec)
    if not ok:
        print(f'TAMPERED: record={rec.id} user={rec.user_id} purpose={rec.purpose_id}')
"
```

## 4. Remediation

### Signing keys missing for tenant

1. Generate a new key: `python -c "import secrets; print(secrets.token_hex(32))"`
2. Add to `CONSENT_SIGNING_KEYS_JSON` in settings/env
3. Restart the API service
4. Existing records will need re-grant (old proofs cannot be verified without old keys)

### Flag was disabled without authorisation

1. Re-enable: `PATCH /api/v1/admin/tenants/{id}/feature-flags/` with `compliance_consent_enabled=true`
2. File an incident in `#meshant-incidents`
3. Audit all consent mutations during the disabled window

### Proof verification failures (bulk)

1. Check if signing key rotation removed old keys prematurely
2. Restore prior keys to the key ring (keep last 3 keys)
3. Users with tampered records must re-grant consent

## 5. Recovery Validation

After remediation:
- [ ] `TENANT_FEATURE_FLAG_CHANGED` audit event shows `flag=compliance_consent_enabled`, `new_value=true`
- [ ] Consent grant via API succeeds and emits `CONSENT_GRANTED`
- [ ] Consent revoke via API succeeds and emits `CONSENT_REVOKED`
- [ ] Consent purpose create/update succeeds and emits `CONSENT_PURPOSE_CHANGED`
- [ ] Consent dashboard returns 200 for DPO/TENANT_ADMIN
- [ ] Signing key verification passes on existing records

## 6. Escalation

| Condition | Action |
|---|---|
| Flag disabled >1 hour without authorisation | Escalate to Platform Lead + DPO |
| Proof verification failures >5% of records | Escalate to privacy-eng on-call |
| Audit events missing for >10min | Escalate to audit-eng on-call |
| Signing keys missing for active tenant | Escalate to privacy-eng + Security |

## 7. Related Runbooks

- `RB-COMP-001-compliance-fail-closed.md` — compliance gate investigation
- `docs/runbooks/phase232-consent-processor.md` — consent processor operations
- `docs/runbooks/feature-flag-lifecycle.md` — feature flag lifecycle policy
