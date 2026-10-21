# Risk: concurrent `manage.py migrate` across API replicas

**Status:** open — assessment only, no deploy configuration changed
**Assessed:** 2026-08-25
**Component:** `helm/templates/api/deployment.yaml` (production chart)
**Severity:** high likelihood, medium-to-high impact, no recorded production occurrence

---

## 1. What is supposed to happen

Database migrations should be applied **exactly once** per release, before application
pods begin serving. The chart's own comment states this and names the required
mechanism (`helm/templates/api/deployment.yaml:87-90`):

> Inline migration is safe for single-replica staging (no concurrent migration race).
> For multi-replica production, use a pre-deploy Job with sufficient cluster CPU
> headroom or a priorityClassName.

## 2. What actually happens

Migrations run **inside every API pod's startup command**
(`helm/templates/api/deployment.yaml:93-107`):

```sh
python hub/manage.py migrate --noinput && \
exec gunicorn hub.asgi:application ...
```

There is no migration Job, hook, or init container in the production chart — the
`wait-for-pgbouncer` init container handles dependency ordering only. Production
replica settings (`helm/values.yaml`):

| Setting | Value |
| --- | --- |
| `api.replicaCount` | 3 |
| `api.hpa.minReplicas` / `maxReplicas` | 2 / 10 |
| `api.hpa.behavior` | **not set** → Kubernetes default (up to +4 pods or 2× per 15s) |
| rollout strategy | `RollingUpdate`, `maxUnavailable: 0`, `maxSurge: 1` |

`helm/values.staging.yaml:33` overrides `replicaCount: 1`, so **staging satisfies the
documented precondition and production does not**.

### Where concurrency actually comes from

The `maxSurge: 1` / `maxUnavailable: 0` strategy **serialises a normal rolling
update** — one surge pod at a time. Rollouts are therefore *not* the main exposure.
The real triggers are:

| Trigger | Concurrent pods | Frequency |
| --- | --- | --- |
| **HPA scale-up** | up to +4 or 2× at once, no `behavior` cap | routine, load-driven |
| **Fresh `helm install`** / namespace recreate | all `replicaCount` pods at once | DR, new environment |
| **Multi-pod restart** (node drain, eviction, OOM) | several | occasional |
| Rolling update | 1 (serialised) | — |

Because `migrate` is chained with `&&` before `exec gunicorn`, **a pod that loses the
race never starts gunicorn**. It exits non-zero and enters `CrashLoopBackOff`.

## 3. Measured behaviour

Reproduced against PostgreSQL 16 on a clone of the shared test database (653
migrations applied, 16 pending — i.e. exactly a release rollout), running three
concurrent `manage.py migrate --noinput` processes, replicating an HPA scale-up:

```
pod1: 16 migrations applied   exit 0
pod2:  7 migrations applied   exit 1  ProgrammingError: relation "ar_comment_thread_idx" already exists
pod3:  7 migrations applied   exit 1  ProgrammingError: relation "ar_comment_thread_idx" already exists
```

**Two of three pods crashed.** In the real chart those two never reach gunicorn.

The migration ledger was also corrupted:

```
distinct=669  rows=683  duplicated_rows=14
```

Seven migrations were recorded **three times each**. The cause is structural:
`django_migrations` carries only `django_migrations_pkey` on `id` — Django ships **no
unique constraint on `(app, name)`** — so nothing prevents the same migration being
recorded repeatedly. Each racing process independently read the applied set, saw the
migration as pending, applied it, and inserted its own ledger row.

Note that `migrate --check` afterwards exits **0**: the schema converged and Django
considers everything applied. The damage is invisible to the obvious health check —
it shows up as crashed pods at the time, and a polluted ledger afterwards.

The failing index, `ar_comment_thread_idx`, comes from `governance/0017`, which is in
the current release set. This is reproducible with the migrations on `main` today,
not a hypothetical.

## 4. Incident history

**Direct evidence — the team built this exact fix and removed it 36 minutes later.**

| Commit | Date | Change |
| --- | --- | --- |
| `e1b40ed50` | 2026-04-16 | Adds `helm/templates/api/migration-job.yaml` — "Runs `manage.py migrate --noinput` exactly once before the API deployment starts, **preventing concurrent migration races when multiple pods scale up**" |
| `232a4a4d5` | 2026-04-16 22:03 | Raises the Job deadline 300 → 600s after `DeadlineExceeded` on first run |
| `9c3c13ded` / `c3c7358c4` | 2026-04-16 22:39 | **Deletes the Job**, restores inline migrate |

The removal rationale was explicitly **staging-specific**: "could not be scheduled on
the single-node staging cluster (0 spare CPU → Pending forever → DeadlineExceeded).
Inline migration is safe for single-replica staging (no concurrent race)."

That reasoning is sound for staging (`replicaCount: 1`). The problem is that the
deletion removed the Job from the **shared** chart, so a single-node staging CPU
constraint silently withdrew a production safety mechanism. The warning comment left
behind in `deployment.yaml` is the only remaining trace.

**A working template still exists in-repo**: `helm/community/templates/migrate-job.yaml`
is a `pre-install,pre-upgrade` hook Job (`hook-weight: -5`,
`hook-delete-policy: before-hook-creation,hook-succeeded`). It is not used by
production — `deploy.yml` deploys the `helm/` chart exclusively.

**Same failure signature already documented**, in the compose test stack
(`docs/RUNBOOKS.md:416`):

> **`relation "tenants" already exists`** or **`UniqueViolation: pg_type_typname_nsp_index`**:
> (1) **Concurrent migrations** — api-service-test and workflow-engine-service-test both
> run `migrate` on `hub_test`; if they start together, PostgreSQL's pg_type catalog
> conflicts.

**Related production deploy failure** (`b0c9653f5`): a staging deploy blocked by
`column "kyc_expires_at" of relation "tenants" already exists` — not a race, but the
same "object already exists" class arising from migration state opacity.

**Circumstantial**: of **649** migration files, **128** use `IF (NOT) EXISTS` guards,
**15** query `information_schema` before DDL, and **15** use
`SeparateDatabaseAndState`. That density of defensive coding is consistent with a team
repeatedly bitten by partially- or double-applied migrations. (Counts re-verified
directly; an earlier pass reported 646/127 using a narrower glob.)

**No recorded production outage.** `INCIDENT_RESPONSE.md`, `docs/process/postmortems.md`,
`docs/retros/`, `docs/risk-register/` and `CHANGELOG.md` contain no incident matching
this signature. This risk has not yet fired in production — or has not been recognised
as this if it did.

## 5. Why the usual mitigations are unavailable

- **PostgreSQL advisory locks are prohibited repo-wide.** PgBouncer `pool_mode=transaction`
  silently releases/reassigns session-scoped locks (`hub/settings.py:766-773`), enforced
  as CI GATE-13 via `hub/tests/test_advisory_lock_not_used.py`.
- **No other serialisation exists**: no `flock`, no Redis lock, no leader election, no
  retry/backoff wrapper. The command is a bare `migrate --noinput &&`.
- **`helm upgrade --atomic` does not help.** It rolls back Kubernetes objects, not schema.
  Runbooks state migrations are forward-only (`runbooks/RB-DEPLOY-001.md:289`).

## 6. Impact if it fires

1. **Partial outage during scale-up.** Losing pods `CrashLoopBackOff` instead of serving.
   Under HPA scale-up this happens exactly when load is already high — the failure is
   correlated with the condition that triggered it.
2. **`--atomic` rollback on deploy**, if enough pods fail readiness inside the 15m timeout.
3. **Ledger pollution.** Duplicate `django_migrations` rows are not self-healing and
   distort `showmigrations`.
4. **Schema mutated by concurrent writers.** Here it converged; that is not guaranteed for
   every operation mix.
5. **Detection gap.** `migrate --check` passes afterwards, so the standard health signal
   does not reveal it.

## 6a. Can the hook Job actually be scheduled? (capacity analysis)

The 2026-04 removal happened because the Job could not be scheduled. Before
recommending its return, that blocker must be shown to be solved. It is **not** — the
same failure would recur in production today.

**Production node group** (`infrastructure/terraform/environments/prod/main.tf:92-98`):
`t3.medium`, `min_size 2`, `desired_size 3`, `max_size 6`. Note `t3.medium` is
2 vCPU / 4 GiB — *smaller* than the `t3.large` staging node the Job failed to schedule on.

**Enabled always-on requests**, computed from `helm/values.yaml` (Deployments and
StatefulSets only; CronJobs excluded as transient; `enabled: false` and
`replicaCount: 0` components excluded — `gpuWorker`, `inferenceServing`, `mailhog`,
`prefectIntegration`, `pgexporter`, `warehouseService`):

```
api x3, worker x3, workerHeavy x1, frontend x2, productSite x2, pgbouncer x2,
semanticService x2, clamav x1, fuseki x1, compliance x2, complianceWorker x1
  => 5250m CPU, 10240Mi memory
```

Against 3 × t3.medium (approximate EKS allocatable ~1930m CPU / ~3200Mi per node):

| | Allocatable | Requested | Free |
| --- | --- | --- | --- |
| CPU | ~5790m | 5250m | **+540m** |
| Memory | ~9600Mi | 10240Mi | **−640Mi** |

Two conclusions:

1. **Memory is already over-committed at `desired_size: 3`** by roughly 640Mi. This is a
   pre-existing capacity finding independent of migrations — the cluster must already be
   running above 3 nodes, or some pods are Pending/evicted.
2. **CPU headroom is fragmented, so the Job cannot schedule.** 540m free is a cluster-wide
   sum; a pod must fit on a *single* node. Spread evenly, each node holds ~1750m of the
   5250m, leaving ~180m free per node. A migration Job sized like `api` (500m) **does not
   fit on any node** — it would go Pending.

**And nothing would rescue it: cluster-autoscaler is NOT installed.** The staging
Terraform records this explicitly (`infrastructure/terraform/environments/staging/main.tf:211`,
audit D127): "NOT installed. The IAM IRSA role exists but ... `grep -rn "helm install
cluster-autoscaler"` → 0 hits". A Pending Job therefore stays Pending until
`activeDeadlineSeconds` expires — **precisely the 2026-04 `Pending → DeadlineExceeded`
failure, reproduced in production**.

**Available lever:** PriorityClasses already exist (`k8s/priority-classes.yaml`:
`high-priority` 1000, `medium-priority` 500, `low-priority` 100), defined outside the
Helm chart. Only `dqService` currently wires `priorityClassName`
(`helm/values.yaml:1824`). Kubernetes preemption would let a high-priority migration Job
evict a lower-priority pod in order to schedule.

*Caveats:* allocatable figures are standard EKS approximations for `t3.medium`, not
measured from the live cluster; actual node count may differ from `desired_size` (manual
scaling, or the ASG drifting — `ignore_changes = [scaling_config[0].desired_size]` at
`modules/eks/main.tf:326`); per-environment value overrides for production were not
found beyond `helm/values.yaml`. Confirm against the live cluster with
`kubectl describe nodes` before acting.

## 7. Recommended remediation (not implemented)

1. **Reinstate a `pre-install,pre-upgrade` hook Job** in `helm/`, modelled on the working
   `helm/community/templates/migrate-job.yaml`, and remove `migrate` from the API
   container command — **but only after §6a's scheduling blocker is solved**, otherwise
   it repeats the 2026-04 failure. In preference order:
   - **Right-size the Job.** `migrate` is single-threaded and mostly IO-wait; it does not
     need `api`-sized resources. Even so, ~180m free per node means requests must be very
     small, so this alone is not sufficient.
   - **Raise `desired_size` 3 → 4.** `max_size` is already 6, so no Terraform limit change
     is needed. This also resolves the memory over-commitment in §6a, which is worth
     fixing regardless.
   - **Give the Job `priorityClassName: high-priority`** so preemption evicts a
     lower-priority pod rather than waiting. Works without new nodes, at the cost of
     evicting something during deploy.
   - **Install cluster-autoscaler.** The IAM IRSA role already exists. This addresses the
     root cause — that a Pending pod never triggers capacity — rather than the symptom.
   Gate the Job on a value so single-node staging can retain inline behaviour.
2. **Run drift-check and pre-flight inside that Job** before `migrate`
   (`makemigrations --check`, then `scripts/preflight_migrations.py`) — production has
   neither today.
3. **Consider a unique index on `django_migrations (app, name)`.** It converts silent
   double-recording into a loud constraint violation. Verify against Django's own
   recorder behaviour before adopting.
4. **Set `api.hpa.behavior`** to cap scale-up step size, reducing simultaneous pod starts
   as defence in depth.

## 8. Evidence index

| Claim | Source |
| --- | --- |
| Inline migrate in pod command | `helm/templates/api/deployment.yaml:93-107` |
| Precondition documented and violated | `helm/templates/api/deployment.yaml:87-90`; `helm/values.yaml` (replicaCount 3, HPA 2–10) |
| Staging is single-replica | `helm/values.staging.yaml:33` |
| Rolling update is serialised | `helm/templates/api/deployment.yaml:19-27` |
| Race reproduced, 2/3 pods failed, 14 duplicate ledger rows | measured 2026-08-25, PostgreSQL 16, 3 concurrent `migrate` on a 653-applied/16-pending clone |
| No unique constraint on `(app, name)` | `pg_constraint` on `django_migrations` → `django_migrations_pkey` only |
| Job built then removed | `e1b40ed50`, `232a4a4d5`, `9c3c13ded`, `c3c7358c4` |
| Working hook template exists | `helm/community/templates/migrate-job.yaml` |
| Same signature seen before | `docs/RUNBOOKS.md:416` |
| Advisory locks prohibited | `hub/settings.py:766-773`; GATE-13 in `.github/workflows/_reusable.lint.yml:97-99` |
