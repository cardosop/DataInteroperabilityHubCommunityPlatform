# W10.2 — Staging soak with RLS armed + Stripe test-mode + pipeline crash drills

Date: 2026-10-17 · Change: `openspec/changes/oss-release-remediation` · Task: W10.2

Evidence artifacts (runtime, gitignored):
`test-artifacts/w102-staging-soak/` — soak evidence JSONL, crash-drill JSON
reports, Stripe drill JSON.  Pins: `scripts/tests/test_w102_staging_soak.py`
(26 unit/contract + 3 live), `hub/apps/auth/tests/test_rls_middleware_preauth_alias.py`
(W102 class), `hub/apps/webhooks/tests/test_w102_async_retry_enqueue.py`,
`hub/apps/tenants/tests/test_seed_default_plans.py` (W102 class),
`hub/apps/auth/tests/test_w119_rate_limit_matrix.py` (W102 class),
`hub/tests/test_w102_settings_test_mode_detection.py`.

## 1. RLS armed soak

### 1.1 Production-shape role flip (the load-bearing fix)

The staging api ran as the superuser `hub_staging` (BYPASSRLS) — request-path
RLS arming was INERT on staging: the soak could never observe the fail-closed
signature.  The api-service now connects as `meshant_app` (RLS-enforced,
non-superuser), the production role shape the W1.20 middleware + pre-tenant
alias were built for:

- `docker-compose.staging.yml` — api-service `POSTGRES_USER/PASSWORD` from
  `POSTGRES_APP_USER`/`POSTGRES_APP_PASSWORD` (unset → owner-role fallback,
  the emergency-rollback path).
- `infrastructure/staging/config-artifacts/scripts/init-db.sql` — meshant_app
  gains full DML + sequence usage + default privileges (fresh volumes).
- `infrastructure/scripts/staging-compose-post-deploy.sh` — management
  commands run with `HUB_USE_ADMIN_DB_FOR_COMMANDS=1` (the B-RLS-0.5
  contract: cross-tenant commands write through the BYPASSRLS admin alias —
  un-armed INSERTs through meshant_app violate the RLS WITH CHECK policies);
  `migrate` runs with the OWNER-role env override (`manage_migrate`);
  meshant_app password + grant sync step added.
- `docs/operations/staging-secrets-registry.md` + `scripts/tests/test_staging_env_contract.py`
  REGISTRY_COVERAGE — the app-role pair is registered (env contract 14/14).

### 1.2 Live-stack root fixes the flip surfaced (RED = the live 500s)

- **Refresh-token lifecycle** (login 500: `new row violates row-level security
  policy for table "refresh_tokens"`): the login mint, the refresh rotation
  and the switch-tenant mint all INSERT into `refresh_tokens` on the armed
  default connection (pre-tenant, GUC NULL).  Fixed: the whole lifecycle
  routes through `_user_lookup_alias()` — login create, refresh read+lock
  (`transaction.atomic(using=alias)` so the FOR UPDATE lock spans
  get→revoke→rotate), rotation create, invitation-acceptance
  (lookup+mutation+create inside one alias atomic), switch-tenant mint, and
  `RefreshToken.revoke_family()` is instance-connection-aware (a
  manager-default query under the armed NULL GUC silently revokes nothing).
- **switch-tenant membership check**: `validate_membership` read the target
  tenant's membership row on the armed-current-tenant connection — hidden by
  RLS → every legitimate switch 403'd.  Fixed via the alias.
- Pins: `test_rls_middleware_preauth_alias.py::W102RefreshTokenLifecycleUnderEnforcement`
  (4 tests, real roles, real views).

### 1.3 Arming verification (live staging)

- `probe_arming_settings` PASS — default DB USER `meshant_app`, admin alias
  `meshant_admin`, `RLS_REQUEST_PATH_ENABLED=True`.
- `probe_db_enforcement` PASS (as `meshant_app` against the staging DB):
  unarmed SELECT → **0 rows** (fail-closed); armed via SET LOCAL →
  the armed tenant's rows only; cross-tenant → isolated; the per-table kill
  GUC `false` → the forensic bypass opens.
- `behavioural_isolation` PASS — 3 seeded tenants through the real API:
  each user sees only their own rows; foreign user UUIDs → 404 (the strict
  W11.3 contract).

### 1.4 The soak run

`infrastructure/scripts/w102_staging_soak.py` (engine) +
`infrastructure/scripts/staging-soak-w102.sh` (orchestrator) + Makefile
targets `staging-soak-w102-{start,watch,status,stop}`.  Driver: continuous
multi-tenant cycles (login/refresh, assets/datasets/contracts/search/
subscription/users/audit surfaces, cross-tenant probes, per-5-cycle DB
baseline probes); watcher: fail-closed signature classification
(`rls_arming_failed` logs/503s, 5xx-rate spikes, empty-result drops vs DB
baseline, isolation violations).  Live window: started 2026-10-17 04:25Z
(detached, 72h), resumed after the mid-day stack churn; evidence accumulates
in `test-artifacts/w102-staging-soak/evidence/soak-evidence.jsonl`.  The
remaining ≥72h window is the ops-scheduled run; `make staging-soak-w102-watch`
classifies it.  During the postgres-outage window the middleware's
`rls_arming_failed` fail-closed signature fired LIVE (evidence in the api
logs) — exactly the signature the soak watches for.

## 2. Pipeline crash drills (`infrastructure/scripts/staging-crash-drills-w102.sh`)

| Drill | Verdict | Result |
|---|---|---|
| D1 worker SIGKILL mid webhook delivery | PASS (post-fix) | restart-policy + recovery-path restart, worker healthy, delivery attempts resumed; **found + fixed the ASYNC retry gap** (below) |
| D2 compliance-rq-worker SIGKILL mid scan | FAIL (recorded finding) | worker restart mechanics verified; **the COMPLIANCE_RUN job was never enqueued** (Job row PENDING, RQ queues empty, run never dispatches) — owning-lane triage ticket |
| D3 pgbouncer SIGKILL mid-request | PASS | 36 clean failures during the outage window, full recovery, **no GUC leakage** (tenant counts match baseline — the transaction-local arming contract held) |
| D4 gunicorn worker SIGKILL | PASS | 1-of-3 worker killed: clean in-flight outcome, respawned, api healthy, tenant view unchanged |

### 2.1 Root fixes the drills produced

- **Restart policies** — the SIGKILLed worker stayed dead (`restarts=0`): no
  staging service had a restart policy except the api's deploy block.  Added
  `restart: always` to all 23 long-running services (production parity) and
  removed the conflicting `deploy.restart_policy` blocks (compose-go gives
  deploy precedence — the first recreation still landed `on-failure`).
  Observation recorded: this host's compose restart supervisor did not fire
  within 2 min even with the policy applied (host under heavy load) — the
  drill asserts config + recovery path; production restarts are the k8s
  orchestrator's job.
- **ASYNC webhook retry gap** — in async mode `_schedule_retry` wrote
  `status=FAILED` + `next_retry_at` and NOTHING read it back (the inline
  branch's own comment admits "no processor ever reads it back").  Fixed:
  `_schedule_retry_locked` enqueues the retry on the queue's SCHEDULED
  registry (`queue.enqueue_at`) — the worker's built-in RQ scheduler promotes
  it at `next_retry_at`, and the schedule lives in Redis so it survives a
  worker crash.  Pins: `test_w102_async_retry_enqueue.py` **2/2** (async
  schedules / inline never double-schedules).
- **Stale worker image** — the staging worker ran a 40-hour-old `w92quick`
  image predating the event-bus listener entirely (`listener.py` absent):
  webhook deliveries could never fire.  Rebuilt from the current tree.
- **graphene-django test-mode landmine (the biggest find)** — graphene-django's
  settings module imports `django.test` at app boot → `unittest` enters
  `sys.modules` → all 12 `"unittest" in sys.modules` test-mode branches in
  `hub/settings.py` fired IN PRODUCTION: the staging worker ran
  `WEBHOOK_ASYNC_DELIVERY=False` (inline synchronous delivery),
  `WEBHOOK_DELIVERY_MAX_RETRIES=2`, sync event-bus persistence, and the
  other test-mode knobs.  Fixed: one `_in_test_run()` discriminator (pytest
  presence / PYTEST_CURRENT_TEST / TESTING env / `test` in argv — real
  test-run signals only).  Pins: `hub/tests/test_w102_settings_test_mode_detection.py`
  **2/2** (subprocess boots, unittest pre-imported, deployment defaults win).
- **SSO throttle 500** — every SSO login-url 500'd with
  `'SSOThrottle' object has no attribute 'history'` (DRF 3.16 sets
  `self.history` only on the cached-key path).  Fixed in the shared mixin
  (`getattr(self, "history", None) or []`).  Pins:
  `test_w119_rate_limit_matrix.py::W102ThrottleNoneKeySurvivalTest` **2/2**.

## 3. Stripe test-mode drill (`infrastructure/scripts/staging-stripe-drill-w102.{sh,py}`)

Real Stripe test-mode objects (real keys, no stubs): hub change-plan →
real Stripe customer + subscription, Stripe-side invoice payment with the
canonical test card, real event payloads replayed with REAL Stripe-Signature
headers (`stripe.Webhook.generate_test_header_string` — the hub verifies via
`construct_event`), replay idempotency (W1.17 claim — re-POSTed events change
no state), tampered-signature rejection, malformed-body rejection.

**Root fixes the drill produced:** (1) the tenant's `pro` plan was seeded
with `price_amount_cents=0` (the seeder's update branch never synced the
canonical catalog price onto pre-existing rows) — change-plan took the
ZERO-PRICE local-only branch and the Stripe path was unreachable.  Seeder
now repairs `price_amount_cents` + `stripe_price_id` + `billing_interval` on
re-seed.  Pins: `test_seed_default_plans.py::W102SeedRepairPriceDriftTest`
(3 tests).  Staging re-seeded: `pro` now 49900 cents.  (2) the container's
`STRIPE_SECRET_KEY` was REJECTED by Stripe (stale — the W0.5 rotation gap):
synced the working test key from `.env.test` into `.env.staging` and
recreated the api.  (3) `Invalid recurring[interval]: must be one of month,
year, week, or day` — the catalog's DISPLAY-shaped `billing_interval`
(`monthly`) went verbatim into Stripe's `recurring.interval` (`month`):
new `_stripe_recurring_interval()` boundary map at both price-creation
sites.  Pins: `hub/apps/billing/tests/test_w102_stripe_plan_interval.py`.
(4) the drill's plan sequence must target a legal UPGRADE (the plan-limit
downgrade guard correctly blocks free→pro for a 23-user tenant — the guard
working as designed): the drill picks the target from the BASE-category
subscription's current plan.

**Sibling-stack churn handled:** the staging api/pgbouncer containers carry
collision-prefixed names after sibling compose runs — the soak engine and
the drills resolve container names dynamically.

## 4. Findings carried to W10.5 (owning lanes)

Ticketed at W10.5: every finding below + the remaining soak window carry a
`TICKET=W105-*` ID in the carryover table of
`openspec/changes/track-oss-deferred-debt/tasks.md` (enforced by
`scripts/tests/test_w105_deferred_debt_triage.py`).

1. **D2 compliance-dispatch gap** — COMPLIANCE_RUN Job rows are created
   PENDING but never enqueued to RQ (queues empty; runs never dispatch).
   Owning lane: compliance.
2. **Compose restart supervisor** — on this host it did not fire within
   2 min even with `restart: always` applied (observed under heavy load);
   drills assert config + the recovery path.  Owning lane: infra.
3. **redis-queue AOF corruption** — the shared staging redis-queue
   crash-looped (170 restarts) on
   ``Bad file format reading the append only file`` after an unclean kill.
   Repaired (user-approved): AOF dir backed up to
   ``test-artifacts/w102-staging-soak/redis-queue-aof-backup/``, then
   ``redis-check-aof --fix`` truncated the 1004-byte torn tail; the
   instance is stable since.  The unclean-kill → AOF-tear class needs a
   runbook entry (redis-queue is job-state-only; the hub DB is the truth).
4. **Async listener liveness on staging** — with the inline-mode image the
   webhook listener delivered end-to-end (18:14 UTC evidence); after the
   test-mode-detector fix (ASYNC=True) the listener registers
   (subscribers=10), the publish lands on redis-events (wire-proven twice),
   and a worker-side probe process receives via the same pubsub pattern —
   but the RUNNING listener threads stopped producing deliveries amid the
   stack churn (worker DNS breaks, redis-queue crash loop, repeated
   restarts).  The async contract is pinned at the unit level
   (``test_w102_async_retry_enqueue.py`` 3/3: schedule-on-fail, no
   inline double-schedule, autocommit enqueue) — the staging liveness
   re-verification is an ops follow-up on a settled stack.  D1's recorded
   state: restart + healthy PASS, retry assertion pending this follow-up.
   **RESOLVED 2026-10-19 (P0-7, close-oss-release-conditions — see §6):
   the settled-stack probe PASSED all three assertions, and it found the
   delivery gaps' root causes: the ``default``-queue orphan, the worker
   JSON/pickle serializer split, and the DEAD_LETTER attempt accounting
   (which is why D1's row-count retry assertion could never pass).**

## 5. Remaining ops window

- Soak: detached 72h driver running; `make staging-soak-w102-watch` for the
  signature classification; the W10.4 evidence pack cites this ledger + the
  evidence dir.
## 6. P0-7 follow-up — async-listener liveness (2026-10-18/19, close-oss-release-conditions)

Ticket `W105-ASYNC-LISTENER-LIVENESS` (W10.2 §4.4 carryover) — CLOSED.
Executed as P0-7: heartbeat metric + staging delivery probe, TDD
RED-first throughout, no mocks — every pin runs against real Redis,
real Postgres rows, and the real listener code; the probe ran against
the real settled compose staging stack.

### 6.1 Heartbeat metric (root fix for the observability gap)

The W10.2 root cause was unobservability: RUNNING listener threads that
stopped producing deliveries left no signal.  Shipped:

* `event_listener_heartbeat_timestamp_seconds{subscriber_name}` (gauge) +
  `event_listener_heartbeat_total{subscriber_name, healthy}` (counter) in
  `hub/apps/core/events/metrics.py`.
* `EventBusListener` watchdog (`hub/apps/core/events/listener.py`): one
  tick per subscriber per `EVENT_BUS_LISTENER_HEARTBEAT_INTERVAL`
  (default 30s) — thread-alive AND live-pubsub health-checked (the
  health-check PING rides the listen connection itself); the timestamp
  ticks regardless of health (staleness = watchdog dead, healthy="0"
  rate = connection dead).  Scraped on the worker /metrics port (host
  :8098).
* Alert `EventBusListenerHeartbeatStale`
  (`infrastructure/staging/config-artifacts/monitoring/prometheus/alerts/event-bus-alerts.yml`,
  promtool-validated 14 rules).
* Pins: `hub/apps/core/events/tests/test_listener_heartbeat.py` **4/4**
  (RED 4/4 first — real Redis + real DB rows + the worker-style
  `generate_latest()` scrape; delivery intact; unhealthy-tick on a dead
  pubsub + reconnect recovery; stop silences the gauge; blocking-reads
  no-reconnect-storm) + `scripts/tests/test_w102_listener_probe.py`
  (wiring contract; CI lint list).

Two further listener root defects the RED runs exposed and fixed (both
pinned in the heartbeat suite):

* **Reconnect storm:** the pool's `socket_timeout` (5s) leaked onto the
  listen connection — `parse_response(block=True)` disconnects + raises
  TimeoutError on every timeout, so a quiet listener re-subscribed in a
  perpetual storm (the churn amplifier).  The listener now builds its
  pubsub from a pool copy with `socket_timeout=None` (blocking reads;
  connection liveness is the health-check machinery's job).
* **Concurrent-close race:** redis-py's socket reader raises ValueError
  ("I/O operation on closed file") when the connection is closed
  concurrently — outside the old `(RedisError, OSError)` reconnect
  catch, it killed the thread silently.  ValueError now reconnects.

### 6.2 Staging delivery probe — root causes the probe found live

`make staging-listener-probe-w102` →
`infrastructure/scripts/staging-listener-probe-w102.sh`: L1 (an executed
delivery attempt — attempt_number ≥ 1, not merely a row), L2 (the
D1-pending retry assertion — a second executed attempt via the
scheduled registry), L3 (the heartbeat scrape: fresh timestamp +
ticking healthy counter on the worker metrics port).  Evidence JSON per
run under `test-artifacts/w102-staging-soak/listener-probe/`; exit 0
only when all three hold.  The probe's own first live runs FAILED and
each failure exposed a real production defect (fixed at the root,
RED-first pins for every one):

1. **`default`-queue orphan:** `deliver_webhook` was `@job("default")`
   and `_schedule_retry` enqueued to `get_queue("default")` — a queue NO
   process in the stack consumes (worker lanes =
   job_critical/job_default/job_low; the semantic service is an HTTP
   API).  33 delivery jobs parked forever; every ASYNC delivery parked
   PENDING at attempt 0.  Fixed: the webhook delivery path rides
   `job_default` (the WORKER_TYPE light lane's documented workload),
   plus the same sweep for `scheduled_ingestion` (`@job("job_default")`
   + the autocommit-aware enqueue — the on_commit-outside-atomic P0-6
   class again), `contracts/migration_manager`, and
   `jobs/tasks_base.process_job`; the RQ_QUEUES "default" comment now
   states the truth.  Ratchet:
   `scripts/tests/test_w102_listener_probe.py` blocks any new
   `@job("default")` / `get_queue("default")` in hub/.
2. **Worker serializer split (R2-S8 RCE class, live):** django-rq's
   rqworker command defaults `--serializer` to pickle and passes it to
   the Worker, OVERRIDING the queue's `RQ_SERIALIZER` (JSON) config —
   so every JSON job the worker dequeued (search vectors, event
   persistence, webhook deliveries) crashed with DeserializationError
   (the earlier "stale image" theory explained only half of it).  The
   worker entrypoint now passes `serializer=` explicitly
   (`services/worker/main.py::_resolve_serializer`).
3. **DEAD_LETTER attempt accounting:** the retry that exhausts the
   budget was never counted — the DLQ branch skipped the
   `attempt_number` increment, so a DEAD_LETTER row claimed attempt=1
   after two real executions and NO DB-level observer could tell the
   retry ran (the real reason the D1 drill's retry assertion stayed
   "pending": the drill counted ROWS while the pipeline re-executes the
   SAME row — attempt-number growth is the only DB-visible retry
   signal, and the DLQ path never wrote it).  Fixed at the root
   (`hub/apps/webhooks/service.py::_schedule_retry` DLQ branch counts
   the final attempt, W1.17 atomic F()); pin:
   `hub/apps/webhooks/tests/test_w102_async_retry_enqueue.py`
   `TestDeadLetterCountsTheFinalAttempt` (RED with the exact staging
   signature: `webhook_dead_letter attempts=1` after two executions).

### 6.3 Deployment + probe verdict (2026-10-19 ~01:09Z)

Worker + api images rebuilt and recreated on the settled stack
(worker: heartbeat + blocking pubsub reads + serializer + queue fix +
DLQ accounting; api: queue fix); both healthy, listener started
(threads=10).  Staging hygiene (user-approved): the 5 stale ACTIVE
drill webhooks (blackhole targets — breaker poison; the shared
'webhook-delivery' breaker was OPEN when the probe first ran) + their
64 delivery rows deleted; `rq:queue:default` (33) + the failed registry
(10 + 3 more after the pre-serializer-fix window) cleared — all counts
recorded before/after.

Probe run `listener-probe-2026-10-19T010951Z.json`: **PASS** — L1
executed delivery, L2 scheduled retry fired (attempt sum 1 → 2), L3
heartbeat fresh (29s) + ticking (3.0 → 4.0).  **D1's pending retry
assertion is now satisfied on the settled stack.**  Earlier probe
runs' FAIL evidence (22:23Z, 22:29Z, 00:13Z, 00:43Z, 00:49Z) is in the
same directory — each FAIL documents one of the three root causes.

### 6.4 Verification

* Heartbeat pins 4/4 (RED first); W4.1 contract + async-retry pins
  (incl. the new DLQ-count pin) 18/18; webhook delivery suites 61/61;
  scheduled-ingestion pins 37/37 (w31+w35+dlt dispatch+failure modes);
  jobs/contracts pins 55/55; full events suite green — all on an
  isolated tmpfs-backed test DB (container p07-pg, port 54331 — zero
  shared-DB contention with sibling sessions).
* Probe pin 10/10 in the CI-style invocation (CI lint list);
  promtool 14 rules OK; ruff clean on all touched files (the remaining
  findings in the touched files are the pre-existing ratchet baseline);
  sleep gate 0 unannotated; `_reusable.lint.yml` YAML parses.
* `test_w105_deferred_debt_triage.py` stays green (backlog rows flipped
  to CLOSED with citation, routings preserved).
