# Marquez quarterly upgrade procedure

**Phase:** 228 F4 (228.F4.29)
**Owner:** Data Platform Eng
**Cadence:** Quarterly (or sooner for security advisories)
**Last reviewed:** 2026-04-30

## Purpose

Marquez is the canonical OpenLineage receiver (228.F4.1 OP-1
sign-off). The upstream Marquez project releases ~monthly; we
upgrade quarterly to balance security-patch latency against
operational stability.

## Pre-upgrade checklist

- [ ] Read the [Marquez release notes](https://github.com/MarquezProject/marquez/releases)
      between the deployed version and the target version. Look for:
  - **OpenLineage spec version bump** — if Marquez requires a newer
    spec (e.g., 2.1.0 → 3.0.0), the Hub adapter's
    `_OPENLINEAGE_RUN_EVENT_SCHEMA` constant in
    `hub/apps/integrations/openlineage/translator.py` MUST be
    re-grounded against the new spec before the Marquez upgrade.
  - **Schema migrations** — Marquez ships its own RDS migrations.
    Estimate downtime per the release notes; >1 min downtime
    requires a maintenance window.
  - **Breaking API changes** — `/api/v1/lineage` is stable but
    Marquez occasionally deprecates the older `/api/v1/jobs` shape
    we use in the integration test (228.F4.23).
- [ ] Bump the `openlineage-python` dep in `requirements.txt` if a
      compatible 1.x release matches the Marquez target. Stay on
      `1.x` until 228.F4 explicitly migrates to 2.x.
- [ ] Run the integration test against a local Marquez container of
      the target version:

```bash
docker run --rm -d --name marquez-upgrade-test \
    -p 5000:5000 marquezproject/marquez:<target-version>

MARQUEZ_INTEGRATION_TEST_URL=http://localhost:5000/api/v1/lineage \
    python -m pytest hub/apps/integrations/openlineage/tests/test_openlineage_marquez_integration.py
```

## Upgrade procedure (staging first)

1. **Pin** the new Marquez chart version in
   `helm/values-staging.yaml` under `marquez.image.tag`.
2. **Deploy** to staging:
   ```bash
   helmfile -e staging apply -l name=marquez
   ```
3. **Smoke** — run the integration test against the staging
   Marquez URL (CI workflow does this automatically):
   ```bash
   MARQUEZ_INTEGRATION_TEST_URL=https://meshant-internal.example.com/api/v1/lineage \
       python -m pytest hub/apps/integrations/openlineage/tests/test_openlineage_marquez_integration.py
   ```
4. **Soak 7 days** — watch the DLQ panel + the Marquez Grafana dashboard. P0 escalation if any of:
   - DLQ pending count climbs above 100 sustained 24h.
   - Marquez pod CrashLoopBackOff.
   - Hub adapter starts producing `http_400` permanent failures
     (schema mismatch).

## Production cutover

If staging soak is clean for 7 days:

1. Pin the same chart version in `helm/values-prod.yaml`.
2. Open a maintenance window per the platform release calendar (the
   Marquez RDS migration is the load-bearing risk).
3. Deploy: `helmfile -e prod apply -l name=marquez`.
4. Run the integration test against the production Marquez URL.
5. Hold a 1-hour DLQ-watching window; rollback if the DLQ spikes.

## Rollback procedure

If the upgrade causes incidents:

1. Re-pin the previous chart version in `helm/values-{env}.yaml`.
2. Apply: `helmfile -e {env} apply -l name=marquez`.
3. The rollback is **not** automatic for RDS migrations — Marquez's
   migrations are typically additive but verify with the release
   notes. If migrations are non-additive, restore RDS from the
   pre-upgrade snapshot.
4. Replay the DLQ once Marquez is back: `python manage.py replay_openlineage_dlq --max=100000`.

## Documentation

After every upgrade, update:

- `docs/integrations/openlineage.md` — the deployed Marquez version
  (front-matter "deployed version" line).
- `requirements.txt` — the `openlineage-python` pin if it moved.
- `tasks.md` — append a one-line entry under §227.F4.29
  documenting the upgrade date, target version, and any defects
  surfaced.

## Related

- [OpenLineage integration doc](../integrations/openlineage.md)
- [Marquez outage runbook](marquez-outage.md)
- [DLQ replay runbook](openlineage-dlq-replay.md)
- Upstream: https://github.com/MarquezProject/marquez/releases
