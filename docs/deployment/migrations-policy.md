# Migrations-on-Boot Policy (W8.1)

Where database migrations run, and why.

## Production (Helm)

**Migrations MUST NOT run inside the api pod.** They run ONCE in a
dedicated pre-upgrade/pre-install Helm hook Job
(`helm/templates/api/migrations-job.yaml`):

- Helm blocks the release on the hook's success, so no api pod ever
  boots against an unmigrated schema.
- With `replicaCount > 1`, an inline `manage.py migrate` would race:
  every pod of a rolling update starts its own migrate, and a pod crash
  mid-migrate can leave the schema at an arbitrary intermediate
  migration. The Job removes the class.
- The Job mirrors the api pod's image, secret materialisation
  (`envFrom`), and the wait-for-pgbouncer init container.

Rollout ordering: `helm upgrade --atomic` runs the Job hook first
(`hook-weight: -5`), then rolls the Deployment only after the hook
succeeds.

Rollback: migrations are forward-only in the shipped schema. A rollback
of the application version is safe as long as the deployed migrations
are a superset of the previous version's — which is always true for a
`helm rollback` (the Job does not undo anything).

## Development and test (Docker Compose)

The compose stacks keep the inline `python hub/manage.py migrate
--noinput && ...` in the api-service command (plus `seed_default_plans`
on the dev stack). This is a **single-replica developer convenience**:

- The dev/test stacks run one api container, so there is no concurrent
  migration race.
- The test stack (`docker-compose.test.yml`) does NOT rely on it for
  isolation — `migrate-test-db` builds the test databases separately and
  the api-service-test container boots straight into gunicorn.

## Enforcement

`scripts/tests/test_w81_image_hardening.py` pins the policy:
`test_production_api_pod_does_not_migrate_inline` (the helm api pod
command contains no `manage.py migrate`) and
`test_migrations_job_exists_and_runs_migrate` (the hook Job exists,
runs `migrate --noinput`, and carries the pre-upgrade hook annotation).
The pin runs in the CI lint job (GATE-29 list).
