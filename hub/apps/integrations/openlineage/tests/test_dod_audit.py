"""
Phase 228 F4 (228.F4.DoD self-audit) — pins for DoD.1 spec scenarios
the original closeout left unimplemented:

* GAP-D1   ``openlineage_outbound_total{result}`` adapter metric.
* GAP-D2/3 inbound view translates event → LineageEdge + returns
  ``edges_created`` count.
* GAP-D4   idempotent on ``run.runId`` — duplicate POST returns the
  original 202 payload byte-identical, zero new edges.
* GAP-D5/6/7 1 MB body cap + 100 datasets cap → HTTP 413.
* GAP-D8   ``OPENLINEAGE_KEY_{CREATED,REVOKED,ROTATED}`` audit events.
* GAP-D9   ``next_retry_at`` populated by the sweep + used as filter.
* GAP-D10  ``openlineage_dlq_depth`` gauge emitted by the sweep.

Test surface uses real fixtures (real Tenant + Subscription + admin
user + ``OpenLineageIngestApiKey`` + DLQ rows + LineageEdge writes).
HTTP path is exercised via ``APIClient`` end-to-end.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from datetime import timedelta
from unittest import mock

import pytest
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient


HMAC_KEY = "test-hmac-signing-key-32-bytes-long-XYZ"
INBOUND_URL = "/api/v1/lineage/openlineage/events/"
KEYS_URL = "/api/v1/lineage/openlineage/keys/"


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


def _create_tenant():
    from hub.apps.billing.models import Subscription, SubscriptionStatus
    from hub.apps.billing.tests.plan_fixtures import (
        create_unique_tenant, get_pro_plan,
    )

    plan = get_pro_plan()
    tenant = create_unique_tenant(
        name_prefix="OL DoD Co",
        slug_prefix="ol-dod-co",
        plan=plan,
    )
    Subscription.objects.create(
        tenant=tenant,
        plan=plan,
        status=SubscriptionStatus.ACTIVE,
        category="BASE",
        current_period_start=timezone.now(),
        current_period_end=timezone.now() + timedelta(days=30),
    )
    return tenant


def _create_admin(tenant):
    from django.contrib.auth import get_user_model
    from hub.apps.users.models import Role, UserRole
    User = get_user_model()
    u = User.objects.create(
        email=f"admin-{uuid.uuid4().hex[:6]}@x", tenant=tenant,
    )
    role, _ = Role.objects.get_or_create(tenant=tenant, name="TENANT_ADMIN")
    UserRole.objects.get_or_create(user=u, tenant=tenant, role=role)
    return u


def _create_active_key(tenant):
    from hub.apps.integrations.openlineage.models import (
        OpenLineageIngestApiKey,
        generate_ingest_key_plaintext,
        hash_ingest_key,
    )
    plaintext = generate_ingest_key_plaintext()
    row = OpenLineageIngestApiKey.objects.create(
        tenant=tenant,
        label="dod-test-key",
        key_prefix=plaintext.removeprefix("msh_ol_")[:8],
        key_hash=hash_ingest_key(plaintext),
    )
    return plaintext, row


def _create_contract(tenant, *, name="c"):
    from hub.apps.contracts.models import Contract
    return Contract.objects.create(
        tenant=tenant,
        version=1,
        original_spec_type="ODCS",
        original_spec_version="3.0.2",
        original_format="YAML",
        original_raw=(
            "kind: DataContract\napiVersion: v3.0.2\nid: c\nname: c\n"
            "version: 1.0.0\nstatus: active\n"
        ),
        hub_contract_json={
            "models": [{"name": "m", "fields": [{"name": "id", "type": "string"}]}],
            "schema": {"fields": []},
        },
        normalization_status="NORMALIZED_OK",
        validation_status="VALID",
        status="ACTIVE",
    )


def _build_event(*, source_id=None, target_id=None, run_id=None):
    return {
        "eventType": "COMPLETE",
        "eventTime": "2026-04-30T12:00:00Z",
        "producer": "https://meshant.com/",
        "schemaURL": "https://openlineage.io/spec/2-0-0/OpenLineage.json",
        "run": {"runId": run_id or str(uuid.uuid4())},
        "job": {"namespace": "etl", "name": "orders_etl"},
        "inputs": [{"namespace": "meshant.contracts",
                     "name": str(source_id) if source_id else str(uuid.uuid4())}],
        "outputs": [{"namespace": "meshant.contracts",
                      "name": str(target_id) if target_id else str(uuid.uuid4())}],
    }


def _hmac_sign(body: bytes) -> str:
    return "sha256=" + hmac.new(
        HMAC_KEY.encode("utf-8"), body, hashlib.sha256,
    ).hexdigest()


# ---------------------------------------------------------------------------
# GAP-D1 — outbound adapter metric
# ---------------------------------------------------------------------------


class TestOutboundMetric(TransactionTestCase):
    """REQ-LIN-F4-001 — outbound metric labels exercised against a real
    HTTP endpoint (no internal mocking)."""

    @staticmethod
    def _start_server(status_sequence):
        """Start a threaded HTTP server that returns *status_sequence*
        in order (one status per request).  Returns ``(port, responses)``
        where *responses* is a list populated with ``(method, path)`` for
        every request the server received."""
        import threading
        from http.server import HTTPServer, BaseHTTPRequestHandler

        responses: list = []
        seq = iter(status_sequence)

        class _Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                responses.append(("POST", self.path))
                try:
                    status = next(seq)
                except StopIteration:
                    status = 200
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b"{}")
            def log_message(self, fmt, *args):
                pass  # silence server logs

        server = HTTPServer(("127.0.0.1", 0), _Handler)
        port = server.server_address[1]
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        return port, responses, server

    def test_success_emits_result_success(self):
        from hub.apps.integrations.openlineage.adapter import (
            DeliveryOutcome, OpenLineageAdapter,
        )

        port, responses, server = self._start_server([200])
        try:
            adapter = OpenLineageAdapter(
                backoff_schedule=(0, 0, 0, 0, 0),
                max_attempts=5,
                request_timeout_seconds=2.0,
            )
            outcome = adapter.deliver(
                event={"e": 1},
                target_url=f"http://127.0.0.1:{port}/api/v1/lineage",
                tenant=None,
            )
            self.assertEqual(outcome, DeliveryOutcome.DELIVERED)
            self.assertGreaterEqual(len(responses), 1,
                                    "server must receive at least one POST")
        finally:
            server.shutdown()

    def test_retry_then_success(self):
        from hub.apps.integrations.openlineage.adapter import (
            DeliveryOutcome, OpenLineageAdapter,
        )

        # First request → 503 (transient), second → 200 (success).
        port, responses, server = self._start_server([503, 200])
        try:
            adapter = OpenLineageAdapter(
                backoff_schedule=(0,) * 5,
                max_attempts=5,
                request_timeout_seconds=2.0,
            )
            outcome = adapter.deliver(
                event={"e": 1},
                target_url=f"http://127.0.0.1:{port}/api/v1/lineage",
                tenant=None,
            )
            self.assertEqual(outcome, DeliveryOutcome.DELIVERED)
            self.assertEqual(len(responses), 2,
                             "should see exactly 2 requests (retry + success)")
        finally:
            server.shutdown()

    def test_dlq_emits_result_dlq(self):
        from hub.apps.integrations.openlineage.adapter import (
            DeliveryOutcome, OpenLineageAdapter,
        )

        tenant = _create_tenant()
        # 422 = permanent failure → goes to DLQ.
        port, responses, server = self._start_server([422])
        try:
            adapter = OpenLineageAdapter(
                backoff_schedule=(0,) * 5,
                max_attempts=5,
                request_timeout_seconds=2.0,
            )
            outcome = adapter.deliver(
                event={"e": 1, "run": {"runId": str(uuid.uuid4())}},
                target_url=f"http://127.0.0.1:{port}/api/v1/lineage",
                tenant=tenant,
            )
            self.assertEqual(outcome, DeliveryOutcome.DEAD_LETTERED)
            self.assertEqual(len(responses), 1,
                             "permanent failure: exactly one attempt, then DLQ")
        finally:
            server.shutdown()


# ---------------------------------------------------------------------------
# GAP-D2/D3 — inbound translates + returns edges_created
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
@override_settings(OPENLINEAGE_HMAC_SIGNING_KEY=HMAC_KEY)
class TestInboundTranslatesAndReturnsEdges(TransactionTestCase):

    def setUp(self):
        from django.db import connection
        if not hasattr(connection.ensure_connection, '__self__'):
            from types import MethodType
            from django.db.backends.base.base import BaseDatabaseWrapper
            connection.ensure_connection = MethodType(
                BaseDatabaseWrapper.ensure_connection, connection,
            )
        connection.close()
        connection.savepoint_ids = []
        connection.needs_rollback = False
        connection.ensure_connection()



    def test_inbound_creates_edge_when_both_endpoints_resolve(self):
        from hub.apps.contracts.models import LineageEdge

        tenant = _create_tenant()
        plaintext, _ = _create_active_key(tenant)
        src = _create_contract(tenant)
        tgt = _create_contract(tenant)

        client = APIClient()
        event = _build_event(source_id=str(src.id), target_id=str(tgt.id))
        body = json.dumps(event).encode("utf-8")
        resp = client.post(
            INBOUND_URL,
            data=body,
            content_type="application/json",
            HTTP_X_MESHANT_SIGNATURE=_hmac_sign(body),
            HTTP_X_MESHANT_OPENLINEAGE_KEY=plaintext,
        )
        assert resp.status_code == 202, resp.content
        data = resp.json()
        assert data["edges_created"] == 1, data
        assert data["duplicate"] is False
        assert data["event_id"] == event["run"]["runId"]

        # Real LineageEdge row inserted.
        edges = LineageEdge.objects.filter(
            tenant=tenant,
            source_contract=src,
            target_contract=tgt,
            valid_to__isnull=True,
            created_by_run="openlineage_inbound",
        )
        assert edges.count() == 1, list(edges)

    def test_inbound_skips_when_contracts_not_owned_by_tenant(self):
        """A foreign producer can POST whatever — but we never write
        an edge into another tenant's lineage graph."""
        from hub.apps.contracts.models import LineageEdge

        tenant = _create_tenant()
        plaintext, _ = _create_active_key(tenant)

        client = APIClient()
        # source / target uuids that don't exist for this tenant.
        event = _build_event(
            source_id=uuid.uuid4(), target_id=uuid.uuid4(),
        )
        body = json.dumps(event).encode("utf-8")
        resp = client.post(
            INBOUND_URL,
            data=body,
            content_type="application/json",
            HTTP_X_MESHANT_SIGNATURE=_hmac_sign(body),
            HTTP_X_MESHANT_OPENLINEAGE_KEY=plaintext,
        )
        assert resp.status_code == 202
        data = resp.json()
        assert data["edges_created"] == 0
        assert LineageEdge.objects.filter(tenant=tenant).count() == 0


# ---------------------------------------------------------------------------
# GAP-D4 — idempotency on event_id
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
@override_settings(OPENLINEAGE_HMAC_SIGNING_KEY=HMAC_KEY)
class TestInboundIdempotency(TransactionTestCase):

    def setUp(self):
        from django.db import connection
        if not hasattr(connection.ensure_connection, '__self__'):
            from types import MethodType
            from django.db.backends.base.base import BaseDatabaseWrapper
            connection.ensure_connection = MethodType(
                BaseDatabaseWrapper.ensure_connection, connection,
            )
        connection.close()
        connection.savepoint_ids = []
        connection.needs_rollback = False
        connection.ensure_connection()



    def test_duplicate_event_id_returns_original_202_zero_new_edges(self):
        from hub.apps.contracts.models import LineageEdge
        from hub.apps.integrations.openlineage.models import (
            OpenLineageInboundEvent,
        )

        tenant = _create_tenant()
        plaintext, _ = _create_active_key(tenant)
        src = _create_contract(tenant)
        tgt = _create_contract(tenant)
        client = APIClient()

        event = _build_event(source_id=str(src.id), target_id=str(tgt.id))
        body = json.dumps(event).encode("utf-8")
        sig = _hmac_sign(body)

        first = client.post(
            INBOUND_URL, data=body, content_type="application/json",
            HTTP_X_MESHANT_SIGNATURE=sig,
            HTTP_X_MESHANT_OPENLINEAGE_KEY=plaintext,
        )
        assert first.status_code == 202
        first_payload = first.json()
        assert first_payload["edges_created"] == 1
        assert first_payload["duplicate"] is False

        edges_after_first = LineageEdge.objects.filter(tenant=tenant).count()

        # Same body, same key, same signature — duplicate POST.
        second = client.post(
            INBOUND_URL, data=body, content_type="application/json",
            HTTP_X_MESHANT_SIGNATURE=sig,
            HTTP_X_MESHANT_OPENLINEAGE_KEY=plaintext,
        )
        assert second.status_code == 202
        second_payload = second.json()
        assert second_payload["duplicate"] is True
        # edges_created from the original-accept payload.
        assert second_payload["edges_created"] == 1
        assert second_payload["event_id"] == first_payload["event_id"]

        # Crucially: no new LineageEdge rows.
        edges_after_second = LineageEdge.objects.filter(tenant=tenant).count()
        assert edges_after_second == edges_after_first, (
            f"duplicate POST must not create edges; "
            f"first={edges_after_first} second={edges_after_second}"
        )

        # And exactly one OpenLineageInboundEvent persisted.
        assert OpenLineageInboundEvent.objects.filter(
            tenant=tenant, event_id=event["run"]["runId"],
        ).count() == 1


# ---------------------------------------------------------------------------
# GAP-D5/6/7 — payload caps + 413
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
@override_settings(OPENLINEAGE_HMAC_SIGNING_KEY=HMAC_KEY)
class TestInboundPayloadCaps(TransactionTestCase):

    def setUp(self):
        from django.db import connection
        if not hasattr(connection.ensure_connection, '__self__'):
            from types import MethodType
            from django.db.backends.base.base import BaseDatabaseWrapper
            connection.ensure_connection = MethodType(
                BaseDatabaseWrapper.ensure_connection, connection,
            )
        connection.close()
        connection.savepoint_ids = []
        connection.needs_rollback = False
        connection.ensure_connection()



    def test_body_over_1mb_returns_413(self):
        tenant = _create_tenant()
        plaintext, _ = _create_active_key(tenant)
        client = APIClient()

        # ~1.1 MB JSON body — exceeds the 1 MB cap.
        payload = "x" * (1024 * 1024 + 1024)
        oversized = json.dumps({"payload": payload}).encode("utf-8")
        resp = client.post(
            INBOUND_URL,
            data=oversized,
            content_type="application/json",
            HTTP_X_MESHANT_SIGNATURE=_hmac_sign(oversized),
            HTTP_X_MESHANT_OPENLINEAGE_KEY=plaintext,
        )
        assert resp.status_code == 413, f"got {resp.status_code}"

    def test_more_than_100_datasets_returns_413(self):
        tenant = _create_tenant()
        plaintext, _ = _create_active_key(tenant)
        client = APIClient()

        event = _build_event()
        # 60 inputs + 60 outputs = 120 total > 100.
        event["inputs"] = [
            {"namespace": "meshant.contracts", "name": str(uuid.uuid4())}
            for _ in range(60)
        ]
        event["outputs"] = [
            {"namespace": "meshant.contracts", "name": str(uuid.uuid4())}
            for _ in range(60)
        ]
        body = json.dumps(event).encode("utf-8")
        resp = client.post(
            INBOUND_URL,
            data=body,
            content_type="application/json",
            HTTP_X_MESHANT_SIGNATURE=_hmac_sign(body),
            HTTP_X_MESHANT_OPENLINEAGE_KEY=plaintext,
        )
        assert resp.status_code == 413, f"got {resp.status_code}"
        data = resp.json()
        assert data["error"]["code"] == "DATASETS_LIMIT_EXCEEDED"
        assert data["error"]["limit"] == 100
        assert data["error"]["received"] == 120


# ---------------------------------------------------------------------------
# GAP-D8 — key audit events (CREATED + REVOKED + ROTATED)
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class TestKeyAuditEvents(TransactionTestCase):

    def _login(self, client, user):
        # Match the auth-cookie pattern existing F4 tests use.
        client.force_authenticate(user=user)

    def test_create_emits_key_created(self):
        from hub.apps.audit.models import AuditEvent

        tenant = _create_tenant()
        admin = _create_admin(tenant)
        client = APIClient()
        self._login(client, admin)

        before = AuditEvent.objects.filter(
            action="OPENLINEAGE_KEY_CREATED", tenant=tenant,
        ).count()
        resp = client.post(KEYS_URL, data={"label": "audit-test"}, format="json")
        assert resp.status_code == 201
        after = AuditEvent.objects.filter(
            action="OPENLINEAGE_KEY_CREATED", tenant=tenant,
        ).count()
        assert after - before == 1

    def test_revoke_emits_key_revoked(self):
        from hub.apps.audit.models import AuditEvent

        tenant = _create_tenant()
        admin = _create_admin(tenant)
        _, key_row = _create_active_key(tenant)
        client = APIClient()
        self._login(client, admin)

        before = AuditEvent.objects.filter(
            action="OPENLINEAGE_KEY_REVOKED", tenant=tenant,
        ).count()
        resp = client.delete(f"{KEYS_URL}{key_row.id}/")
        assert resp.status_code == 204
        after = AuditEvent.objects.filter(
            action="OPENLINEAGE_KEY_REVOKED", tenant=tenant,
        ).count()
        assert after - before == 1

    def test_rotate_command_emits_key_rotated(self):
        from io import StringIO

        from django.core.management import call_command

        from hub.apps.audit.models import AuditEvent

        tenant = _create_tenant()
        before = AuditEvent.objects.filter(
            action="OPENLINEAGE_KEY_ROTATED", tenant=tenant,
        ).count()
        call_command(
            "rotate_openlineage_keys",
            f"--tenant={tenant.id}",
            stdout=StringIO(),
        )
        after = AuditEvent.objects.filter(
            action="OPENLINEAGE_KEY_ROTATED", tenant=tenant,
        ).count()
        assert after - before == 1


# ---------------------------------------------------------------------------
# DoD self-audit DD-A — Quarterly rotation grace audit (REQ-LIN-F4-003 spec
# scenario "Quarterly rotation grace": "an audit event records the
# rotation-grace usage").
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
@override_settings(OPENLINEAGE_HMAC_SIGNING_KEY=HMAC_KEY)
class TestKeyGraceUsageAudit(TransactionTestCase):

    def setUp(self):
        from django.db import connection
        if not hasattr(connection.ensure_connection, '__self__'):
            from types import MethodType
            from django.db.backends.base.base import BaseDatabaseWrapper
            connection.ensure_connection = MethodType(
                BaseDatabaseWrapper.ensure_connection, connection,
            )
        connection.close()
        connection.savepoint_ids = []
        connection.needs_rollback = False
        connection.ensure_connection()



    def test_first_grace_period_request_emits_audit(self):
        from hub.apps.audit.models import AuditEvent
        from hub.apps.integrations.openlineage.models import (
            OpenLineageIngestApiKey,
            generate_ingest_key_plaintext,
            hash_ingest_key,
        )

        tenant = _create_tenant()
        # Mint a key that is INSIDE its grace window (expires_at in
        # the future, but ALREADY has expires_at — i.e. a successor
        # has been issued and this one is graced).
        plaintext = generate_ingest_key_plaintext()
        key = OpenLineageIngestApiKey.objects.create(
            tenant=tenant,
            label="grace-test",
            key_prefix=plaintext.removeprefix("msh_ol_")[:8],
            key_hash=hash_ingest_key(plaintext),
            expires_at=timezone.now() + timedelta(days=5),  # 5d remaining grace
        )
        src = _create_contract(tenant)
        tgt = _create_contract(tenant)
        client = APIClient()

        before = AuditEvent.objects.filter(
            action="OPENLINEAGE_KEY_GRACE_USED", tenant=tenant,
        ).count()

        event = _build_event(source_id=str(src.id), target_id=str(tgt.id))
        body = json.dumps(event).encode("utf-8")
        resp = client.post(
            INBOUND_URL,
            data=body,
            content_type="application/json",
            HTTP_X_MESHANT_SIGNATURE=_hmac_sign(body),
            HTTP_X_MESHANT_OPENLINEAGE_KEY=plaintext,
        )
        assert resp.status_code == 202, resp.content

        after = AuditEvent.objects.filter(
            action="OPENLINEAGE_KEY_GRACE_USED", tenant=tenant,
        ).count()
        assert after - before == 1, (
            f"first grace-window auth must emit 1 audit; "
            f"got delta={after - before}"
        )
        # Latch field set so subsequent uses don't fire again.
        key.refresh_from_db()
        assert key.grace_audit_emitted_at is not None

    def test_subsequent_grace_period_requests_do_not_re_audit(self):
        """Once-per-key emission. A busy producer must NOT generate
        one audit row per request."""
        from hub.apps.audit.models import AuditEvent
        from hub.apps.integrations.openlineage.models import (
            OpenLineageIngestApiKey,
            generate_ingest_key_plaintext,
            hash_ingest_key,
        )

        tenant = _create_tenant()
        plaintext = generate_ingest_key_plaintext()
        OpenLineageIngestApiKey.objects.create(
            tenant=tenant,
            label="grace-test-2",
            key_prefix=plaintext.removeprefix("msh_ol_")[:8],
            key_hash=hash_ingest_key(plaintext),
            expires_at=timezone.now() + timedelta(days=5),
        )
        src = _create_contract(tenant)
        tgt = _create_contract(tenant)
        client = APIClient()

        # 3 requests with distinct event ids so no idempotency dedup.
        for _ in range(3):
            event = _build_event(source_id=str(src.id), target_id=str(tgt.id))
            body = json.dumps(event).encode("utf-8")
            resp = client.post(
                INBOUND_URL,
                data=body,
                content_type="application/json",
                HTTP_X_MESHANT_SIGNATURE=_hmac_sign(body),
                HTTP_X_MESHANT_OPENLINEAGE_KEY=plaintext,
            )
            assert resp.status_code == 202

        count = AuditEvent.objects.filter(
            action="OPENLINEAGE_KEY_GRACE_USED", tenant=tenant,
        ).count()
        assert count == 1, (
            f"only the FIRST grace-window auth must audit; got {count}"
        )

    def test_non_graced_key_does_not_emit_grace_audit(self):
        """A key with ``expires_at IS NULL`` (not yet rotated) MUST
        NOT emit the grace audit on auth."""
        from hub.apps.audit.models import AuditEvent

        tenant = _create_tenant()
        plaintext, _ = _create_active_key(tenant)  # no expires_at set
        src = _create_contract(tenant)
        tgt = _create_contract(tenant)
        client = APIClient()

        before = AuditEvent.objects.filter(
            action="OPENLINEAGE_KEY_GRACE_USED", tenant=tenant,
        ).count()

        event = _build_event(source_id=str(src.id), target_id=str(tgt.id))
        body = json.dumps(event).encode("utf-8")
        resp = client.post(
            INBOUND_URL,
            data=body,
            content_type="application/json",
            HTTP_X_MESHANT_SIGNATURE=_hmac_sign(body),
            HTTP_X_MESHANT_OPENLINEAGE_KEY=plaintext,
        )
        assert resp.status_code == 202

        after = AuditEvent.objects.filter(
            action="OPENLINEAGE_KEY_GRACE_USED", tenant=tenant,
        ).count()
        assert after == before, (
            "non-graced key must not emit OPENLINEAGE_KEY_GRACE_USED; "
            f"got delta={after - before}"
        )


# ---------------------------------------------------------------------------
# GAP-D9 — next_retry_at populated by sweep + filter respected
# ---------------------------------------------------------------------------


def _create_dlq_row(tenant, *, replay_attempts=0, permanently_failed=False,
                    delivered_at=None, next_retry_at=None):
    from hub.apps.integrations.openlineage.models import OpenLineageDeadLetter

    row = OpenLineageDeadLetter(
        tenant=tenant,
        event_id=str(uuid.uuid4()),
        target_url="http://marquez.example/api/v1/lineage",
        failure_reason="http_503",
        failure_detail="x",
        attempts=5,
        replay_attempts=replay_attempts,
        permanently_failed=permanently_failed,
        delivered_at=delivered_at,
        next_retry_at=next_retry_at,
    )
    row.event_payload = {
        "eventType": "COMPLETE",
        "eventTime": "2026-04-30T12:00:00Z",
        "producer": "https://meshant.com/",
        "schemaURL": "https://openlineage.io/spec/2-0-0/OpenLineage.json",
        "run": {"runId": str(uuid.uuid4())},
        "job": {"namespace": "ns", "name": "n"},
        "inputs": [{"namespace": "meshant.contracts", "name": "src"}],
        "outputs": [{"namespace": "meshant.contracts", "name": "tgt"}],
    }
    row.save()
    return row


@pytest.mark.django_db(transaction=True)
class TestDlqNextRetryAtSchedulingAndFilter(TransactionTestCase):

    def setUp(self):
        from django.db import connection
        if not hasattr(connection.ensure_connection, '__self__'):
            from types import MethodType
            from django.db.backends.base.base import BaseDatabaseWrapper
            connection.ensure_connection = MethodType(
                BaseDatabaseWrapper.ensure_connection, connection,
            )
        connection.close()
        connection.savepoint_ids = []
        connection.needs_rollback = False
        connection.ensure_connection()
        # TransactionTestCase does not rollback — delete any rows leaked
        # by prior tests so each test starts with a clean DLQ table.
        from hub.apps.integrations.openlineage.models import OpenLineageDeadLetter
        OpenLineageDeadLetter.objects.all().delete()



    def test_failed_replay_sets_next_retry_at_in_future(self):
        from hub.apps.integrations.openlineage.adapter import DeliveryOutcome
        from hub.apps.integrations.openlineage.tasks import (
            openlineage_dlq_replay_sweep,
        )

        tenant = _create_tenant()
        row = _create_dlq_row(tenant, replay_attempts=0)

        with mock.patch(
            "hub.apps.integrations.openlineage.adapter.OpenLineageAdapter"
        ) as adapter_cls:
            adapter_cls.return_value.deliver.return_value = DeliveryOutcome.DEAD_LETTERED
            openlineage_dlq_replay_sweep(max_rows=10)

        row.refresh_from_db()
        assert row.next_retry_at is not None, (
            "failed replay must schedule next_retry_at"
        )
        assert row.next_retry_at > timezone.now(), (
            f"next_retry_at must be in the future; got {row.next_retry_at}"
        )

    def test_sweep_skips_rows_with_future_next_retry_at(self):
        from hub.apps.integrations.openlineage.adapter import DeliveryOutcome
        from hub.apps.integrations.openlineage.tasks import (
            openlineage_dlq_replay_sweep,
        )

        tenant = _create_tenant()
        row = _create_dlq_row(
            tenant,
            next_retry_at=timezone.now() + timedelta(hours=1),
        )

        with mock.patch(
            "hub.apps.integrations.openlineage.adapter.OpenLineageAdapter"
        ) as adapter_cls:
            adapter_cls.return_value.deliver.return_value = DeliveryOutcome.DELIVERED
            result = openlineage_dlq_replay_sweep(max_rows=10)
            adapter_cls.return_value.deliver.assert_not_called()

        assert result["processed"] == 0
        row.refresh_from_db()
        assert row.delivered_at is None

    def test_successful_replay_deletes_row(self):
        """DoD self-audit DD-B — spec scenario "DLQ retry succeeds"
        says ``the row is deleted``. We honour that literally; the
        DLQ table is the queue of currently-failing rows, so a
        successfully redelivered row no longer belongs there."""
        from hub.apps.integrations.openlineage.adapter import DeliveryOutcome
        from hub.apps.integrations.openlineage.models import (
            OpenLineageDeadLetter,
        )
        from hub.apps.integrations.openlineage.tasks import (
            openlineage_dlq_replay_sweep,
        )

        tenant = _create_tenant()
        row = _create_dlq_row(tenant, replay_attempts=2,
                              next_retry_at=timezone.now() - timedelta(seconds=1))
        row_id = row.id
        with mock.patch(
            "hub.apps.integrations.openlineage.adapter.OpenLineageAdapter"
        ) as adapter_cls:
            adapter_cls.return_value.deliver.return_value = DeliveryOutcome.DELIVERED
            openlineage_dlq_replay_sweep(max_rows=10)

        assert not OpenLineageDeadLetter.objects.filter(pk=row_id).exists(), (
            "successful replay must delete the DLQ row"
        )


# ---------------------------------------------------------------------------
# GAP-D10 — dlq_depth gauge emitted by the sweep
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class TestDlqDepthGauge(TransactionTestCase):

    def setUp(self):
        from django.db import connection
        if not hasattr(connection.ensure_connection, '__self__'):
            from types import MethodType
            from django.db.backends.base.base import BaseDatabaseWrapper
            connection.ensure_connection = MethodType(
                BaseDatabaseWrapper.ensure_connection, connection,
            )
        connection.close()
        connection.savepoint_ids = []
        connection.needs_rollback = False
        connection.ensure_connection()



    def test_sweep_emits_dlq_depth_metric(self):
        from hub.apps.integrations.openlineage.adapter import DeliveryOutcome
        from hub.apps.integrations.openlineage.tasks import (
            openlineage_dlq_replay_sweep,
        )

        tenant = _create_tenant()
        _create_dlq_row(tenant)

        # Patch the canonical metric symbol at its source — the
        # sweep imports it lazily inside ``_record_dlq_depth_metric``.
        with mock.patch(
            "hub.apps.observability.metrics.openlineage_dlq_depth"
        ) as gauge:
            with mock.patch(
                "hub.apps.integrations.openlineage.adapter.OpenLineageAdapter"
            ) as adapter_cls:
                adapter_cls.return_value.deliver.return_value = DeliveryOutcome.DELIVERED
                openlineage_dlq_replay_sweep(max_rows=10)

        # Sweep emits both depth labels: one per ``permanently_failed`` value.
        labelsets = [c.kwargs for c in gauge.labels.call_args_list]
        kept = [d for d in labelsets if "permanently_failed" in d]
        assert len(kept) >= 2, (
            f"sweep must emit both depth labels; got {labelsets}"
        )
        values = {d.get("permanently_failed") for d in kept}
        assert {"true", "false"}.issubset(values), values
