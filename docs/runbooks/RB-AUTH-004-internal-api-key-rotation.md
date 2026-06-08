# RB-AUTH-004 — Internal API Key Rotation

## Status

**Active** (Phase 270.C.3 implementation complete).

## Purpose

Operational procedure for the 90-day rotation of the
`X-Internal-Api-Key` shared secret used by `api-service`↔microservice
calls (compliance-service, dq-service, semantic-service) per D-270.8.
Covers planned rotations driven by the AWS Secrets Manager rotation
Lambda AND emergency rotations triggered by suspected key compromise.

The `KeyRotationOverdue` Prometheus alert fires when the SM secret's
`LastRotatedDate` exceeds the 90-day cadence by 5 days (95 days total
grace) — see
[`monitoring/prometheus/alerts/marketplace-compliance-deltas.yml`](../../monitoring/prometheus/alerts/marketplace-compliance-deltas.yml).

## Architecture

- **AWS Secrets Manager** stores the key under `{secretsPrefix}/api`
  with two JSON properties:
  - `INTERNAL_API_KEY` — the current value (AWSCURRENT version stage)
  - `INTERNAL_API_KEY_PREVIOUS` — the just-retired value (empty in
    steady state; populated during the 24h overlap window after
    a rotation completes)

- **Rotation Lambda** —
  [`infrastructure/terraform/modules/secrets-manager-rotation/lambda/internal_api_key_rotation.py`](../../infrastructure/terraform/modules/secrets-manager-rotation/lambda/internal_api_key_rotation.py)
  implements the four-step AWS rotation protocol:
  - `createSecret` — generates a fresh 256-bit key via
    `secrets.token_hex(32)` AND copies the JUST-CURRENT value into
    `INTERNAL_API_KEY_PREVIOUS` in the same SecretString JSON
  - `setSecret` — no-op (no downstream DB to update; pods sync via ESO)
  - `testSecret` — validates the AWSPENDING JSON shape is well-formed
  - `finishSecret` — promotes AWSPENDING → AWSCURRENT via
    `update_secret_version_stage`

- **ExternalSecrets Operator** — the ExternalSecret at
  [`helm/templates/externalsecrets/external-secret.yaml`](../../helm/templates/externalsecrets/external-secret.yaml)
  syncs BOTH `INTERNAL_API_KEY` AND `INTERNAL_API_KEY_PREVIOUS`
  properties from the SM secret into the K8s Secret (and from there
  into pod env vars via `envFrom.secretRef`).

- **Middleware** —
  [`services/shared/auth.py:InternalApiKeyMiddleware`](../../services/shared/auth.py)
  reads BOTH env vars at startup. Each request's `X-Internal-Api-Key`
  header is compared (constant-time, via `hmac.compare_digest`) against
  `INTERNAL_API_KEY` first; if that fails AND `INTERNAL_API_KEY_PREVIOUS`
  is populated, it's compared against PREVIOUS too. Either match → 200.
  Neither match → 401 with `WWW-Authenticate: ApiKey`.

## Planned rotation flow

1. **Trigger** — the AWS SM rotation Lambda runs automatically every
   90 days per the `rate(90 days)` schedule on
   `aws_secretsmanager_secret_rotation.internal_api_key`. To trigger
   manually:
   ```bash
   aws secretsmanager rotate-secret \
     --secret-id <secretsPrefix>/api \
     --rotation-lambda-arn <Lambda ARN from terraform output>
   ```

2. **Verify the SM SecretString is well-formed**:
   ```bash
   aws secretsmanager get-secret-value \
     --secret-id <secretsPrefix>/api \
     --query SecretString --output text | jq .
   ```
   Expect:
   ```json
   {
     "INTERNAL_API_KEY": "<NEW 64-hex value>",
     "INTERNAL_API_KEY_PREVIOUS": "<just-retired 64-hex value>"
   }
   ```

3. **Wait for ExternalSecrets sync** — default `refreshInterval` is
   5m. Confirm the K8s Secret has both keys:
   ```bash
   kubectl -n <namespace> get secret <externalSecrets.targetSecretName> -o json \
     | jq '.data | {current: (.INTERNAL_API_KEY|@base64d|.[0:8]+"…"),
                    prev:    (.INTERNAL_API_KEY_PREVIOUS|@base64d|.[0:8]+"…")}'
   ```

4. **Rolling restart** so pods pick up the new env vars (ESO updates
   the Secret but pods don't re-read env until restart):
   ```bash
   kubectl -n <namespace> rollout restart deployment/api
   kubectl -n <namespace> rollout restart deployment/compliance-service
   # … etc. for every service that reads INTERNAL_API_KEY
   ```

5. **Smoke-test** — confirm an api-service→compliance-service call
   succeeds with the NEW key AND a sentinel call with the PREVIOUS
   key also succeeds (proves the overlap is active):
   ```bash
   # New key
   curl -s -o /dev/null -w '%{http_code}\n' \
     -H "X-Internal-Api-Key: $NEW_KEY" \
     https://compliance-service.<env>.meshant.com/health
   # → 200

   # Previous key (during 24h overlap)
   curl -s -o /dev/null -w '%{http_code}\n' \
     -H "X-Internal-Api-Key: $PREV_KEY" \
     https://compliance-service.<env>.meshant.com/protected
   # → 200 during overlap, 401 after
   ```

6. **Close the overlap (optional)** — after 24h, the next scheduled
   sync naturally clears the PREVIOUS slot when the Lambda runs
   again (90 days later). To compress the window:
   ```bash
   # Run a second rotation immediately — the PREVIOUS slot now
   # carries the CURRENT value (just rotated); the next rotation
   # sets PREVIOUS to the previous CURRENT, clearing the original.
   ```

## Emergency rotation flow (suspected compromise)

1. **Immediate** — trigger the SM rotation Lambda with the override
   that empties the PREVIOUS slot (no 24h overlap):
   ```bash
   # Step 1 — normal rotation puts the leaked key into PREVIOUS.
   aws secretsmanager rotate-secret --secret-id <secretsPrefix>/api
   # Step 2 — IMMEDIATELY re-rotate; the leaked key is replaced
   # in CURRENT and the (just-rotated) value drops to PREVIOUS.
   # After step 2, neither AWSCURRENT nor AWSPREVIOUS holds the
   # compromised value.
   aws secretsmanager rotate-secret --secret-id <secretsPrefix>/api
   ```

2. **Accept the propagation gap** — between the second rotation and
   the ESO sync + pod restarts, some api-service↔microservice calls
   return 401. The platform's standard retry-with-backoff
   (Phase 19.8) absorbs transient failures.

3. **Notify** the platform-security mailing list + open a sev-1
   incident in the on-call system. Record:
   - Time of suspected compromise
   - First rotation timestamp
   - Second (clearing) rotation timestamp
   - Pod-restart completion timestamps

## Pre-rotation checklist

- [ ] ExternalSecrets controller healthy:
      `kubectl -n external-secrets get pods` → all `Running`
- [ ] SM IAM role on the rotation Lambda intact:
      `aws iam get-role --role-name <lambda-execution-role>`
- [ ] Last rotation timestamp <95 days old (no overdue alert active)
- [ ] All target services' `/health` endpoints respond 200

## Post-rotation evidence pack

- SM `LastRotatedDate` timestamp (from `describe-secret`)
- ExternalSecret resource status:
  `kubectl -n <namespace> get externalsecret -o yaml | yq .status`
- Rolling-deploy completion timestamps per service
- Sample successful 200 + sample 401 count from the 24h overlap
  window (from the API gateway access log — proves the overlap worked
  AND eventually expired)

## Failure modes + remediation

| Failure mode | Symptom | Remediation |
|---|---|---|
| Rotation Lambda crashes | CloudWatch ERROR for the Lambda; `KeyRotationOverdue` alert eventually fires | Inspect Lambda logs; re-run with `aws secretsmanager rotate-secret`; check IAM perms |
| ExternalSecret sync stuck | K8s Secret stale; pods serve 401 after rolling restart | Restart ExternalSecrets controller; check `kubectl describe externalsecret` for events |
| Both keys rejected after rotation | All inter-service calls 401 | Roll back ESO Secret to a known-good snapshot; restore SM SecretString from a CloudTrail-recorded prior version |
| SM SecretString corrupted (non-JSON) | Rotation Lambda's `testSecret` step raises | Manual `aws secretsmanager put-secret-value` with the well-formed JSON shape |
| Lambda cross-secret invocation | Lambda raises `RuntimeError("rotation invoked for X but bound to Y")` | Inspect the SM rotation configuration; ensure each Lambda is wired to ONE secret |

## Related

- Spec: [`marketplace-tax-compliance-deltas/spec.md`](../../openspec/changes/preprod01/specs/marketplace-tax-compliance-deltas/spec.md) §
  *X-Internal-Api-Key Rotation Cadence*
- Design: [`design.md#decision-d-2708`](../../openspec/changes/preprod01/design.md) (D-270.8)
- Code:
  - [`services/shared/auth.py`](../../services/shared/auth.py) — `InternalApiKeyMiddleware` dual-key support
  - [`infrastructure/terraform/modules/secrets-manager-rotation/`](../../infrastructure/terraform/modules/secrets-manager-rotation/) — Terraform module + Lambda source
  - [`helm/templates/externalsecrets/external-secret.yaml`](../../helm/templates/externalsecrets/external-secret.yaml) — dual-property ESO sync
- Alert: [`monitoring/prometheus/alerts/marketplace-compliance-deltas.yml`](../../monitoring/prometheus/alerts/marketplace-compliance-deltas.yml) (`KeyRotationOverdue`)
- Related runbook: [`RB-AUTH-001-rls-kill-switch.md`](RB-AUTH-001-rls-kill-switch.md)
  (cross-service auth kill-switch precedent)

## Maintenance

- **Owner**: Security Team
- **Last reviewed**: 2026-05-13
- **Next review**: 2026-08-11
