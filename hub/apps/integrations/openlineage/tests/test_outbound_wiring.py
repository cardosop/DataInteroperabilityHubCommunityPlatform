"""
Phase 228 F4 (228.F4.27 self-audit GAP-1) — outbound OpenLineage
emission wiring tests.

The closeout claimed the outbound path was wired through the
``post_save`` signal handler, but a self-audit found that
``hub.apps.contracts.lineage_sync`` never invokes the adapter or the
``send_openlineage_event_async`` task — so Marquez receives nothing
in production. This test file pins the missing behaviour:

1. ``LineageEdge`` adds enqueue one ``send_openlineage_event_async``
   call (one event per added edge).
2. ``LineageEdge`` closes also enqueue one event per closed edge —
   the "edge removed" lineage transition is observable to the
   downstream catalog.
3. The capability flag ``lineage.openlineage_export`` gates
   emission: when OFF, zero dispatches.
4. A dispatch error MUST NOT roll back the relational edge write.
   The edge is the load-bearing record; the OpenLineage event is a
   downstream signal (same fail-soft contract as
   ``_emit_edge_audit_events`` per Phase 228.0 audit-2).
5. The dispatched event payload validates against the embedded
   OpenLineage 2.0.0 schema — i.e. the wiring threads through the
   real translator, not a hand-rolled stub.

The patches use ``mock.patch`` at the import-site
``hub.apps.contracts.lineage_sync.send_openlineage_event_async`` so a
future refactor that bypasses the helper fails this suite by name.
"""
from __future__ import annotations

import uuid
from unittest import mock

import pytest
from django.test import TransactionTestCase, override_settings


def _create_tenant(prefix: str = "OL"):
    from hub.apps.tenants.models import Tenant

    suffix = uuid.uuid4().hex[:8]
    return Tenant.objects.create(
        name=f"{prefix} Co {suffix}",
        slug=f"{prefix.lower()}-co-{suffix}",
    )


def _create_contract(tenant, *, lineage_entries=None, version: int = 1):
    from hub.apps.contracts.models import Contract

    hub_contract = {
        "models": [
            {
                "name": "m",
                "fields": [{"name": "id", "type": "string"}],
            },
        ],
        "schema": {"fields": []},
    }
    if lineage_entries is not None:
        hub_contract["lineage"] = {"contracts": lineage_entries}
    return Contract.objects.create(
        tenant=tenant,
        version=version,
        original_spec_type="ODCS",
        original_spec_version="3.0.2",
        original_format="YAML",
        original_raw=(
            "kind: DataContract\napiVersion: v3.0.2\nid: c\nname: c\n"
            "version: 1.0.0\nstatus: active\n"
        ),
        hub_contract_json=hub_contract,
        normalization_status="NORMALIZED_OK",
        validation_status="VALID",
        status="ACTIVE",
    )


@pytest.mark.django_db(transaction=True)
class TestOutboundEmissionOnAdd(TransactionTestCase):
    """Adding a lineage edge fires one ``send_openlineage_event_async``
    dispatch per edge."""

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

    def test_add_one_edge_emits_one_event(self):
        tenant = _create_tenant()
        upstream = _create_contract(tenant)

        with mock.patch(
            "hub.apps.contracts.lineage_sync.send_openlineage_event_async"
        ) as dispatch_target:
            # Project convention dispatches via ``.delay()`` (django_rq);
            # the bound method on a MagicMock auto-creates so we observe
            # it directly.
            dispatch = dispatch_target.delay
            _create_contract(
                tenant,
                lineage_entries=[
                    {
                        "source_contract": str(upstream.id),
                        "target_contract": "self",
                        "edge_type": "transformation",
                        "transformation_ref": "etl.run.v1",
                    },
                ],
            )

        # Exactly one dispatch for the single added edge.
        assert dispatch.call_count == 1, (
            f"expected 1 outbound dispatch for the 1 added edge; "
            f"got {dispatch.call_count}"
        )
        # Inspect payload — the event should validate against the
        # embedded OpenLineage 2.0.0 schema.
        from hub.apps.integrations.openlineage.translator import (
            validate_openlineage_event,
        )

        kwargs = dispatch.call_args.kwargs
        assert "event" in kwargs, (
            "dispatch must be called with keyword arg ``event``; got "
            f"{dispatch.call_args}"
        )
        event = kwargs["event"]
        validate_openlineage_event(event)
        assert event["eventType"] == "COMPLETE", (
            "transformation edge_type → COMPLETE eventType per translator"
        )
        # Tenant must be threaded through so the worker can resolve it.
        assert kwargs.get("tenant_id") == str(tenant.id)

    def test_add_three_edges_emits_three_events(self):
        tenant = _create_tenant()
        u1 = _create_contract(tenant)
        u2 = _create_contract(tenant)
        u3 = _create_contract(tenant)

        with mock.patch(
            "hub.apps.contracts.lineage_sync.send_openlineage_event_async"
        ) as dispatch_target:
            # Project convention dispatches via ``.delay()`` (django_rq);
            # the bound method on a MagicMock auto-creates so we observe
            # it directly.
            dispatch = dispatch_target.delay
            _create_contract(
                tenant,
                lineage_entries=[
                    {
                        "source_contract": str(u.id),
                        "target_contract": "self",
                        "edge_type": "reference",
                    }
                    for u in (u1, u2, u3)
                ],
            )

        assert dispatch.call_count == 3, dispatch.call_count


@pytest.mark.django_db(transaction=True)
class TestOutboundEmissionOnRemove(TransactionTestCase):
    """Closing a lineage edge ALSO fires one dispatch — edge removal is
    a lineage transition the downstream catalog must see."""

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

    def test_close_emits_one_event(self):
        # Patch from setup-time so the initial edge-create dispatch
        # doesn't hit the real Marquez URL (which would 31-sec retry +
        # write a DLQ row in tests).
        with mock.patch(
            "hub.apps.contracts.lineage_sync.send_openlineage_event_async"
        ) as dispatch_target:
            dispatch = dispatch_target.delay
            tenant = _create_tenant()
            upstream = _create_contract(tenant)
            target = _create_contract(
                tenant,
                lineage_entries=[
                    {
                        "source_contract": str(upstream.id),
                        "target_contract": "self",
                        "edge_type": "reference",
                    },
                ],
            )
            # The initial create fired one dispatch; reset the mock so
            # we can attribute the next assertion to the close alone.
            assert dispatch.call_count == 1, (
                f"setup expected 1 dispatch from the initial add; "
                f"got {dispatch.call_count}"
            )
            dispatch.reset_mock()

            # Drop all lineage entries → triggers a close.
            target.hub_contract_json = dict(target.hub_contract_json)
            target.hub_contract_json["lineage"] = {"contracts": []}
            target.save()

            assert dispatch.call_count == 1, (
                f"expected 1 dispatch for the 1 closed edge; "
                f"got {dispatch.call_count}"
            )


@pytest.mark.django_db(transaction=True)
@override_settings(CAPABILITY_FLAGS={"lineage.openlineage_export": False})
class TestCapabilityFlagGatesDispatch(TransactionTestCase):
    """When ``lineage.openlineage_export`` is OFF, zero dispatches fire
    even though the LineageEdge rows are still written."""

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

    def test_flag_off_skips_dispatch(self):
        from hub.apps.contracts.models import LineageEdge

        tenant = _create_tenant()
        upstream = _create_contract(tenant)

        with mock.patch(
            "hub.apps.contracts.lineage_sync.send_openlineage_event_async"
        ) as dispatch_target:
            # Project convention dispatches via ``.delay()`` (django_rq);
            # the bound method on a MagicMock auto-creates so we observe
            # it directly.
            dispatch = dispatch_target.delay
            target = _create_contract(
                tenant,
                lineage_entries=[
                    {
                        "source_contract": str(upstream.id),
                        "target_contract": "self",
                        "edge_type": "reference",
                    },
                ],
            )

        # No dispatch — but the edge row was still written.
        assert dispatch.call_count == 0, (
            f"capability OFF must skip dispatch; got "
            f"{dispatch.call_count} calls"
        )
        edge_count = LineageEdge.objects.filter(
            target_contract=target, valid_to__isnull=True
        ).count()
        assert edge_count == 1, (
            f"capability OFF must NOT block edge write; got {edge_count}"
        )


@pytest.mark.django_db(transaction=True)
class TestDispatchFailureDoesNotRollback(TransactionTestCase):
    """A raised exception inside the dispatch path MUST NOT roll back
    the LineageEdge write. The relational row is the canonical record;
    the OpenLineage event is a downstream signal. Mirrors the
    fail-soft contract of ``_emit_edge_audit_events``."""

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

    def test_dispatch_raise_does_not_rollback_edge_write(self):
        from hub.apps.contracts.models import LineageEdge

        tenant = _create_tenant()
        upstream = _create_contract(tenant)

        with mock.patch(
            "hub.apps.contracts.lineage_sync.send_openlineage_event_async"
        ) as dispatch_target:
            # The production code dispatches via ``.delay()``; force
            # that path to raise to simulate a Marquez outage / RQ
            # connection failure.
            dispatch_target.delay.side_effect = RuntimeError(
                "Marquez unreachable"
            )
            target = _create_contract(
                tenant,
                lineage_entries=[
                    {
                        "source_contract": str(upstream.id),
                        "target_contract": "self",
                        "edge_type": "reference",
                    },
                ],
            )

        # Edge row persisted despite dispatch failure.
        edge_count = LineageEdge.objects.filter(
            target_contract=target, valid_to__isnull=True
        ).count()
        assert edge_count == 1, (
            f"dispatch failure must not roll back edge write; "
            f"got {edge_count} edges"
        )


@pytest.mark.django_db(transaction=True)
class TestNoopDoesNotEmit(TransactionTestCase):
    """A same-state save (no add, no remove) MUST NOT emit any
    OpenLineage events — the diff is a noop and there is no lineage
    transition to publish."""

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

    def test_resave_with_identical_lineage_emits_zero(self):
        with mock.patch(
            "hub.apps.contracts.lineage_sync.send_openlineage_event_async"
        ) as dispatch_target:
            dispatch = dispatch_target.delay
            tenant = _create_tenant()
            upstream = _create_contract(tenant)
            target = _create_contract(
                tenant,
                lineage_entries=[
                    {
                        "source_contract": str(upstream.id),
                        "target_contract": "self",
                        "edge_type": "reference",
                    },
                ],
            )
            # The initial create fires one dispatch; reset to count
            # ONLY the dispatches the no-op resave produces.
            dispatch.reset_mock()
            target.save()

            assert dispatch.call_count == 0, (
                f"noop diff must emit zero events; got {dispatch.call_count}"
            )
