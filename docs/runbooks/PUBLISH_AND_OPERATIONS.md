# Publish & Operations Runbook

The operational procedures around the OSS publish pipeline. This is the
canonical home for the recipes that used to live only in the tasks.md
closeout prose.

## Publish ordering (never reorder)

1. **Commit** the change in the private repo (the tree builder sources
   `git ls-files` — uncommitted work never ships).
2. **`make publish-check`** — boundary + guards + the openspec structural
   gate (NET-growth baseline) + gitleaks + publish-tree parity. It must be
   green BEFORE the scrub.
3. **Scrub** — the history scrub produces the sanitized tree (paid paths
   physically absent; gitleaks clean). The scrub is one-time-per-publish.
4. **Publish** — `PYTHON=venv/bin/python bash scripts/publish_public.sh`
   syncs the full snapshot to `mirror/public-core`. The sync commit is a
   FULL snapshot: the public tree is replaced, not patched.

## `.env.test` GCP key rotation

`docs/test-infrastructure/host-env-matrix.md` records that `.env.test`
carries a **stale** `GCP_SERVICE_ACCOUNT_JSON`. Rotation steps:

1. Generate a fresh key for the test service account.
2. Replace `GCP_SERVICE_ACCOUNT_JSON` (and `GCP_CREDENTIALS_JSON` if set)
   in `.env.test` with the new key.
3. Re-run the GCP connector tests — a stale key now SKIPS (the tests probe
   real auth) instead of producing `UNAUTHENTICATED` failures.
4. Never commit the key: `.env.test` is gitignored (`scripts/publish_paths_exclude.txt`
   excludes the `.env*` family).

## Dev-stack restore

After a full teardown, restore the local stack with:

```bash
docker compose -f docker-compose.test.yml -f docker-compose.test.core.yml \
  --env-file .env.test up -d --build
```

For the host-side (p313) containers the recipe lives in
`docs/runbooks/HOST_SIDE_VERIFICATION.md`.

## Revert path for a bad public merge

A bad public merge is **one revert + one publish**:

1. In the PRIVATE repo: `git revert <bad-commit>` (or revert the merge).
2. Re-run `make publish-check`, then the publish (step 4 above).

This works because the sync commit is a full snapshot — rolling the
private source back and re-publishing overwrites the public tree
completely. There is no partial state to reconcile.
