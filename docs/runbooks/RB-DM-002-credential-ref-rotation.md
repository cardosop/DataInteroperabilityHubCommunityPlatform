# RB-DM-002 — Credential Reference Rotation

**Feature:** Data Movement (dlt), `data_movement_enabled` GA
**Owner:** data-plane-eng@meshant.com
**Created:** 2026-05-18 (Phase 285.6.6)

## Symptom Index

| Symptom | Likely cause | First checks |
|---------|-------------|--------------|
| Pipeline auth failure after rotation | `credential_ref` ARN not updated; old secret deleted | `ScheduledIngestion.credential_ref` field; AWS SM secret status |
| All pipelines failing with auth error | IAM role missing `secretsmanager:GetSecretValue` | AWS IAM policy; CloudTrail for `AccessDenied` |
| Prefect block credential not resolving | Block name changed; Prefect server unreachable | Prefect UI → Blocks; `resolve_credentials("prefect://...")` |
| Local dev credentials missing | `.dlt/secrets.toml` not configured | `~/.dlt/secrets.toml` exists; contains `[destination]` section |

## Rotation Procedure

### AWS Secrets Manager
1. **Create new secret version** in AWS SM (same ARN). Previous version auto-retained.
2. **No Hub-side action needed.** `resolve_credentials()` fetches the latest version on each pipeline run.
3. **Verify:** Trigger a pipeline run; check logs for `aws_sm_resolve_success`.
4. **Cleanup:** Delete old secret version after 7-day soak (all in-flight pipelines complete).

### Prefect Block
1. **Update block value** in Prefect UI (same block name).
2. **No Hub-side action needed.** `resolve_credentials("prefect://block-name")` fetches latest.
3. **Verify:** Trigger a pipeline run; check logs for `prefect_resolve_success`.

### .dlt/secrets.toml (Development)
1. Edit `~/.dlt/secrets.toml` with new credentials.
2. Restart development worker.
3. Verify: `python -c "from hub.data_movement.dlt_credentials import resolve_credentials; print(resolve_credentials())"`

## Credential Ref Migration

During the dual-path transition (inline creds + credential_ref):

1. **Migrate inline → ref:** `python manage.py migrate_credentials_to_refs --execute`
2. **Dry-run first:** `python manage.py migrate_credentials_to_refs --dry-run`
3. **Rollback:** `source_config_backup` JSON field preserves original creds; revert per row
4. **Monitor:** `credential_ref IS NOT NULL` count → should increase toward 100%

## Escalation

- **P3:** Single tenant credential rotation not picked up (manual re-trigger)
- **P2:** AWS SM resolution failing for all tenants (IAM or SM service issue)
- **P1:** Credential leak detected — keys in logs/configs. Rotate immediately + incident response.

## Related

- `hub/data_movement/dlt_credentials.py` — resolve_credentials()
- `docs/runbooks/RB-DM-001-dlt-pipeline-failure.md` — pipeline failure investigation
- `docs/runbooks/RB-SEC-001-credential-rotation.md` — general credential rotation

## Maintenance

- **Owner:** Data Plane Engineering
- **Last reviewed:** 2026-05-18
- **Next review:** 2026-08-18
