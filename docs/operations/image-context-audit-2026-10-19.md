# Image Build-Context Audit — 2026-10-19 (P0-14, G5)

Audit of every PUBLISHED image's build context for baked `.env*`
files and credential material. Published images carry whatever the
context held at build time — pre-scrub checkouts baked real env
files and the tracked `.claude/settings.json` (live `sk-` bearer
token) regardless of the git rewrite.

## Findings

### Credential exposure

The tracked `.claude/settings.json` carried a live bearer token and is baked by every whole-context (`COPY . .`) backend image (api-service, worker-service) plus the buildcache tags. Root-fixed 2026-10-19: the file is untracked (it was already gitignored), the root `.dockerignore` now excludes `.claude/`, and the house gitleaks config gained the anthropic rule (the gap that let the token pass the P0-9 tracked-tree scan).

Current tracked tree: 0 credential findings.

## Per-image disposition

| Image | Dockerfile | Context | Env findings | Dockerignore |
|---|---|---|---|---|
| ghcr.io/cardosop/datainteroperabilityhub-api-service | services/api/Dockerfile | . | none | yes |
| ghcr.io/cardosop/datainteroperabilityhub-worker-service | services/worker/Dockerfile | . | none | yes |
| ghcr.io/cardosop/datainteroperabilityhub-compliance-service | services/compliance-service/Dockerfile | . | none | yes |
| ghcr.io/cardosop/datainteroperabilityhub-prefect-integration-service | services/prefect-integration/Dockerfile | . | none | yes |
| ghcr.io/cardosop/datainteroperabilityhub-semantic-service | services/semantic-service/Dockerfile | . | none | yes |
| ghcr.io/cardosop/datainteroperabilityhub-dq-service | services/dq-service/Dockerfile | . | none | yes |
| ghcr.io/cardosop/datainteroperabilityhub-datacontract-service | services/datacontract-service/Dockerfile | . | none | yes |
| ghcr.io/cardosop/datainteroperabilityhub-frontend | frontend/Dockerfile | frontend | none | yes |
| ghcr.io/cardosop/datainteroperabilityhub-product-site | product-site/Dockerfile | . | none | yes |

## Affected images — the P2-6 input

Every tag published BEFORE the P1 rotations is affected (the
rotations are Phase 1, pending): all current tags of all 9
images plus their `buildcache` tags (BuildKit cache layers can
retain intermediate-layer content, incl. pre-fix `.claude/`).

P2-6 disposition: AFTER the rotations land (old values dead),
rebuild-and-republish (or delete) every pre-rotation tag of:

- `ghcr.io/cardosop/datainteroperabilityhub-api-service` (all tags + `:buildcache`)
- `ghcr.io/cardosop/datainteroperabilityhub-worker-service` (all tags + `:buildcache`)
- `ghcr.io/cardosop/datainteroperabilityhub-compliance-service` (all tags + `:buildcache`)
- `ghcr.io/cardosop/datainteroperabilityhub-prefect-integration-service` (all tags + `:buildcache`)
- `ghcr.io/cardosop/datainteroperabilityhub-semantic-service` (all tags + `:buildcache`)
- `ghcr.io/cardosop/datainteroperabilityhub-dq-service` (all tags + `:buildcache`)
- `ghcr.io/cardosop/datainteroperabilityhub-datacontract-service` (all tags + `:buildcache`)
- `ghcr.io/cardosop/datainteroperabilityhub-frontend` (all tags + `:buildcache`)
- `ghcr.io/cardosop/datainteroperabilityhub-product-site` (all tags + `:buildcache`)

## Lane disposition (P2-6)

The dormant `inference-service` lane (no Dockerfile since
inception — the deploy workflow guard always skipped it) is
DELETED per the delete-or-wire disposition: the workflow build
lane, the disabled helm chart (`enabled: false`, replicaCount
0, an image that could never be built) and its network policy
are removed; the package stays in the P2-6 remediation
executor's deleted-lane list so any published versions get
deleted (no rebuild is possible for a lane that no longer
exists). The remaining registry packages follow the
rebuild-after-rotation disposition above.


Enumeration at execution time (needs `read:packages` scope):

```bash
gh api 'user/packages/container/<package>/versions' \
  --paginate --jq '.[] | {name: .name, created: .created_at}'
```

