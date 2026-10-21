"""P0-7 (close-oss-release-conditions, ticket W105-ASYNC-LISTENER-LIVENESS)
— the async-listener staging probe wiring pins (Django-free, CI lint tier).

The W10.2 soak carried the async-listener liveness re-verification to
W10.5: the RUNNING listener threads stopped producing deliveries amid
stack churn and nothing outside the worker process could tell — liveness
was unobservable.  P0-7 closes the gap with two halves: (1) a heartbeat
metric emitted by the listener watchdog (the unit pins in
``hub/apps/core/events/tests/test_listener_heartbeat.py`` own the code
behavior), and (2) a staging delivery probe that re-verifies delivery +
retry + heartbeat against the real settled stack.

These pins hold the WIRING contract — the probe script's three
assertions (delivery, the D1-pending retry, the heartbeat scrape), the
Makefile target, the CI lint registration, and the deployment contract
(settings interval + the listener flag staying armed on worker AND api)
— so the probe can never silently lose one of its assertions or drift
out of CI.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MAKEFILE = REPO_ROOT / "Makefile"
PROBE = REPO_ROOT / "infrastructure" / "scripts" / "staging-listener-probe-w102.sh"
COMPOSE = REPO_ROOT / "docker-compose.staging.yml"
METRICS = REPO_ROOT / "hub" / "apps" / "core" / "events" / "metrics.py"
LISTENER = REPO_ROOT / "hub" / "apps" / "core" / "events" / "listener.py"
SETTINGS = REPO_ROOT / "hub" / "settings.py"
CI_LINT = REPO_ROOT / ".github" / "workflows" / "_reusable.lint.yml"


def _text(path: Path) -> str:
    assert path.is_file(), f"expected committed artifact: {path}"
    return path.read_text(encoding="utf-8")


def test_probe_script_exists_and_carries_the_three_assertions():
    text = _text(PROBE)
    # L1 — the delivery assertion: an asset.created event must flow through
    # the WORKER's listener into an EXECUTED delivery attempt.  A PENDING
    # row is NOT delivery — the trigger creates it; only an attempt
    # (attempt_number >= 1 / status leaving PENDING) proves the worker
    # executed the RQ job (the exact W10.2 parked-PENDING failure mode).
    assert "webhooks/webhooks/" in text, "probe must create a real webhook via the API"
    assert "assets/" in text, "probe must trigger the pipeline via a real asset create"
    assert "webhook_deliveries" in text, "probe must poll the real delivery rows"
    assert "attempt_number" in text, (
        "probe must assert the delivery row was EXECUTED (attempt_number) — "
        "a row-existence check is fooled by the trigger's own PENDING row"
    )
    assert "SUM(attempt_number)" in text, (
        "the retry signal must be attempt-number GROWTH on the same row — "
        "the retry pipeline re-executes the SAME WebhookDelivery row "
        "(the D1 drill's row-count-growth assumption was the reason its "
        "retry assertion stayed 'pending')"
    )
    assert "PENDING" in text, (
        "probe must gate the executed-attempt count on status leaving PENDING"
    )
    # Hygiene: the webhook delete does not cascade its delivery rows —
    # the probe must remove its own rows (stale ACTIVE drill webhooks
    # already poison the shared tenant; probe residue must not add more).
    assert "DELETE FROM webhook_deliveries" in text, (
        "probe must clean up its own delivery rows"
    )
    # The psql -A separator trap: unaligned mode joins the two count
    # columns with '|' — a whitespace awk split reads "1|0" as ONE field
    # and the executed column parses as empty (the probe's first live-run
    # bug, caught on staging).  The split must be -F'|'.
    assert "awk -F'|'" in text, (
        "probe must split the two-column psql output on '|'"
    )
    # L2 — the retry assertion (the D1-pending piece): the failed blackhole
    # attempt must be RETRIED — a second EXECUTED attempt must appear.
    assert "203.0.113.1" in text, "probe must use the TEST-NET blackhole target"
    assert "retry_intervals" in text, "probe must pin a short retry interval"
    assert re.search(r"count.*>|attempts.*>|count.*-gt", text), (
        "probe must assert the attempt count GROWS (the retry happened)"
    )
    # L3 — the heartbeat assertion: the worker /metrics scrape must carry a
    # FRESH timestamp gauge and TICKING healthy counter (two scrapes).
    assert "event_listener_heartbeat_timestamp_seconds" in text, (
        "probe must scrape the heartbeat timestamp gauge"
    )
    assert "event_listener_heartbeat_total" in text, (
        "probe must scrape the heartbeat healthy counter"
    )
    assert re.search(r"/metrics", text), "probe must scrape the worker /metrics endpoint"
    # Evidence + exit contract: a FAIL is evidence too, and the exit code
    # must carry the verdict (0 only when all three assertions hold).
    assert re.search(r"verdict", text), "probe must record a verdict"
    assert "exit 1" in text or "exit 0" in text, "probe must set its exit code from the verdict"


def test_probe_wired_into_the_makefile():
    makefile = _text(MAKEFILE)
    assert re.search(r"^staging-listener-probe-w102:", makefile, re.MULTILINE), (
        "Makefile must define the staging-listener-probe-w102 target"
    )
    # The target must invoke THIS probe script (not a stale path).
    target_body = makefile.split("staging-listener-probe-w102:", 1)[1].split("\n\n", 1)[0]
    assert "infrastructure/scripts/staging-listener-probe-w102.sh" in target_body, (
        "the Makefile target must call the probe script"
    )
    # And the target must be .PHONY (the repo convention for script targets).
    phony = re.search(r"^\.PHONY:.*staging-listener-probe-w102.*$", makefile, re.MULTILINE)
    assert phony, "staging-listener-probe-w102 must be declared .PHONY"


def test_probe_pin_registered_in_the_ci_lint_list():
    ci = _text(CI_LINT)
    assert "scripts/tests/test_w102_listener_probe.py" in ci, (
        "the probe pin must sit in the CI lint list (_reusable.lint.yml)"
    )


def test_heartbeat_metric_definitions_exist():
    metrics = _text(METRICS)
    for name in (
        "event_listener_heartbeat_timestamp_seconds",
        "event_listener_heartbeat_total",
    ):
        assert f'"{name}"' in metrics, f"{name} missing from events/metrics.py"
    # Both metrics carry the subscriber_name label — per-subscriber liveness
    # is the granularity the alert needs (one dead subscriber, one alert).
    timestamp_block = metrics.split("event_listener_heartbeat_timestamp_seconds", 1)[1]
    timestamp_block = timestamp_block.split("\n\n", 1)[0]
    assert "subscriber_name" in timestamp_block, "timestamp gauge must be labeled per subscriber"
    total_block = metrics.split("event_listener_heartbeat_total", 1)[1]
    total_block = total_block.split("\n\n", 1)[0]
    assert "subscriber_name" in total_block, "tick counter must be labeled per subscriber"
    assert '"healthy"' in total_block, "tick counter must carry the healthy label"


def test_heartbeat_interval_setting_defined():
    settings = _text(SETTINGS)
    match = re.search(
        r"EVENT_BUS_LISTENER_HEARTBEAT_INTERVAL\s*=\s*env\.float\(.*?default=([0-9.]+)",
        settings,
        re.DOTALL,
    )
    assert match, "EVENT_BUS_LISTENER_HEARTBEAT_INTERVAL setting missing from settings.py"
    default = float(match.group(1))
    assert 15.0 <= default <= 120.0, (
        f"heartbeat interval default {default} outside the sane 15..120s band"
    )


def test_heartbeat_staleness_alert_completes_the_loop():
    """The metric alone does not detect the W10.2 failure mode — a
    staleness alert over the timestamp gauge is the closing half of the
    observability loop (metric → scrape → alert).  The assertion reads
    the TRACKED canonical rules file (the staging host serves a live
    copy from gitignored config-artifacts — the canonical file's header
    states the sync contract)."""
    alerts = _text(REPO_ROOT / "infrastructure" / "observability" / "prometheus"
                   / "alerts" / "event-bus-alerts.yml")
    assert "EventBusListenerHeartbeatStale" in alerts, (
        "event-bus-alerts.yml must carry the heartbeat staleness alert"
    )
    alert_block = alerts.split("EventBusListenerHeartbeatStale", 1)[1]
    assert "event_listener_heartbeat_timestamp_seconds" in alert_block, (
        "the staleness alert must be over the heartbeat timestamp gauge"
    )
    assert "time()" in alert_block, "the staleness expr must compare against time()"


def test_webhook_delivery_rides_a_worker_consumed_queue():
    """The probe's first live run found the parked-PENDING root cause:
    ``deliver_webhook`` + the retry scheduler enqueued to the legacy
    ``default`` queue — a queue NO process in the stack consumes (the
    worker lanes are job_critical/job_default/job_low; 33 jobs parked
    forever on staging).  The delivery path must ride ``job_default``,
    the queue the WORKER_TYPE light lane joins (webhook delivery is its
    documented workload)."""
    tasks = _text(REPO_ROOT / "hub" / "apps" / "webhooks" / "tasks.py")
    service = _text(REPO_ROOT / "hub" / "apps" / "webhooks" / "service.py")
    assert '@job("job_default", timeout=120)' in tasks, (
        "deliver_webhook must be pinned to job_default (the worker-consumed queue)"
    )
    assert '@job("default"' not in tasks, (
        "deliver_webhook must not enqueue to the orphaned 'default' queue"
    )
    assert 'get_queue("job_default").enqueue_at(' in service, (
        "the W10.2 retry scheduler must enqueue to job_default's scheduled registry"
    )
    assert 'get_queue("default")' not in service, (
        "the webhook service must not reference the orphaned 'default' queue"
    )


def test_no_enqueuer_targets_the_orphaned_default_queue():
    """The probe's first live run exposed the systemic class: every
    ``@job("default")`` / ``get_queue("default")`` enqueuer parks jobs in
    a Redis queue NO process in the stack consumes (the worker lanes are
    job_critical/job_default/job_low; the semantic service is an HTTP
    API, not an RQ worker).  This ratchet blocks regrowth: no non-test
    Python file under hub/ may enqueue to "default".  (The RQ_QUEUES
    settings entry itself stays — removing it would silently break any
    straggler; its comment states the truth.)"""
    violations = []
    for path in (REPO_ROOT / "hub").rglob("*.py"):
        if "/tests/" in str(path) or "/migrations/" in str(path):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for line_no, line in enumerate(text.splitlines(), start=1):
            if '@job("default"' in line or 'get_queue("default")' in line:
                violations.append(f"{path.relative_to(REPO_ROOT)}:{line_no}: {line.strip()}")
    assert not violations, "orphaned 'default'-queue enqueuers remain:\n" + "\n".join(violations)


def test_worker_entrypoint_passes_the_queue_serializer_explicitly():
    """The probe's first post-deploy run caught the second serializer
    split: django-rq's rqworker command defaults ``--serializer`` to
    ``rq.serializers.DefaultSerializer`` and passes it to the Worker,
    OVERRIDING the queue's ``RQ_SERIALIZER`` (JSON) config — so even a
    freshly built worker crashed every JSON job with
    DeserializationError (the probe's L1 caught the parked rows).  The
    worker entrypoint must pass the serializer explicitly so the
    enqueue and consume sides agree."""
    main = _text(REPO_ROOT / "services" / "worker" / "main.py")
    assert "serializer=" in main, (
        "worker entrypoint must pass serializer= to the rqworker call_command"
    )
    assert "RQ_SERIALIZER" in main, (
        "the passed serializer must resolve from the RQ_SERIALIZER setting"
    )


def test_listener_flag_stays_armed_on_worker_and_api():
    compose = _text(COMPOSE)
    worker_block = compose.split("worker-service:", 1)[1].split("  compliance-rq-worker:", 1)[0]
    api_block = compose.split("api-service:", 1)[1]
    api_block = api_block.split("  prefect-server:", 1)[0]
    for block, service in ((worker_block, "worker-service"), (api_block, "api-service")):
        assert "EVENT_BUS_LISTENER_ENABLED: \"true\"" in block, (
            f"{service} must keep the listener armed (the W4.1 deployment contract)"
        )
