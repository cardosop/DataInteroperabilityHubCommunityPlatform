# SPARQL determinism on staging

**Phase 226 OQ2 (resolved 2026-04-26)** — context for reviewers and on-call.

## TL;DR

Staging runs Apache Jena Fuseki 4.8.0 as a StatefulSet
(`hub-staging-fuseki`, helm values at
[helm/values.staging.yaml#L362-L399](../../helm/values.staging.yaml)). The
semantic service proxies SPARQL queries via the platform API at
`POST /api/v1/semantic/sparql`. **Fuseki is reachable; semantic E2E specs
no longer need to skip the SPARQL leg of `verifySemanticIri`.**

E2E SPARQL determinism rests on two contracts:

1. **Per-tenant named graphs** — Each tenant's triples live in a graph
   IRI derived from `tenant.id`. Cross-tenant tests cannot pollute one
   another by construction.
2. **Per-test ephemeral tenants** — Within-tenant test pollution is
   mitigated by the `disposableTenantTest` fixture (Phase 226 OQ4),
   which provisions a fresh tenant per test via
   `POST /api/v1/tenants/ephemeral/`. The tenant's named graph is
   write-empty at test start.

When a spec needs cross-test triple isolation it MUST use
`disposableTenantTest`, not the shared static tenant.

## Health-check gate

Before the staging Playwright run, CI runs
[scripts/check_sparql_health.cjs](../../scripts/check_sparql_health.cjs)
against `https://api.stagingmeshant-internal.example.com/api/v1/semantic/sparql`. The
script issues a minimal `ASK { ?s ?p ?o }` and validates the SPARQL 1.1
JSON binding shape (a single `boolean` field). A non-2xx, malformed
response, or timeout fails the workflow before any spec runs — converting
a Fuseki outage into one infrastructure-level failure rather than dozens
of flaky-spec failures.

See the workflow step "SPARQL endpoint health check (Fuseki)" in
[.github/workflows/playwright-mvp-quarantine-nightly.yml](../../.github/workflows/playwright-mvp-quarantine-nightly.yml).

## What this does NOT cover

- **Result-order non-determinism within a SELECT.** SPARQL leaves result
  order undefined unless the query has `ORDER BY`. Specs that compare
  ordered results MUST use explicit `ORDER BY`. Use
  `sparqlResultHasExpectedTriple` from
  [verifySemantic.ts](../../frontend/e2e/fixtures/verifySemantic.ts), which
  treats results as a set rather than a list.
- **Backup-restore drift.** The
  [fuseki-tdb2 backup CronJob](../../helm/templates/cronjob/backup-fuseki-tdb2.yaml)
  takes a nightly snapshot to S3. After a restore, named-graph contents
  match the snapshot timestamp; specs that assume a clean slate must
  re-provision via the disposable-tenant path.
- **JVM-level OOM events.** Fuseki's JVM is bounded at 512 MB heap +
  256 MB metaspace + 256 MB direct memory (root-cause fix for the 125+
  restarts incident on 2026-04-14). Heavy SPARQL queries that exceed
  these bounds will trip `OOMKilled`. The health-check above will then
  fail before the spec run, surfacing the issue at the right altitude.

## Owner

Operational owner is whoever is on-call for the staging cluster
(`hub-staging` namespace). The health-check + named-graph guarantee are
maintained as part of the semantic service contract; code changes that
break them are caught by:

1. The pytest harness for `check_sparql_health.cjs`
   ([scripts/tests/test_check_sparql_health.py](../../scripts/tests/test_check_sparql_health.py)).
2. The semantic backend tests under
   [hub/apps/semantic/tests/](../../hub/apps/semantic/tests/).
3. `verifySemanticIri` adoption in the 5 critical-path specs (per
   226.G7 / 226.G7a).
