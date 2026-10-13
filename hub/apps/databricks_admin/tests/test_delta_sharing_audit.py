"""Phase 5 (openspec add-delta-sharing-server task 5.7) — the audit
formalization: the Delta Sharing event set is REGISTERED (constants +
``__all__``) and every emission site references the CANONICAL constants
(the 0.16 contract — production code imports the constants instead of
inlining string literals, so a typo fails at the import site).

The emission behavior itself is pinned by the 5.3/5.4 suites (the
per-request ACCESSED row with IP + user-agent, the 401 AUTH_FAILED row,
the 429 rate-limit row, the snapshot COMPLETED/FAILED rows, and the
audit-outage best-effort pins) — this suite pins the REGISTRATION layer
and the emission sites' constant discipline. No mocks: the AST pins read
the REAL module sources; the runtime pins import the REAL modules.
"""

import ast
from pathlib import Path

import pytest

from hub.apps.databricks_admin.tests.test_uc_browse import _setup_tenant

pytestmark = pytest.mark.django_db(transaction=True)

_REPO = Path(__file__).resolve().parents[4]

P5_SHARE_EVENTS = (
    "WAREHOUSE_SHARE_ACCESSED",
    "WAREHOUSE_SHARE_AUTH_FAILED",
    "DELTA_SHARE_RATE_LIMIT_EXCEEDED",
    "DATABRICKS_SHARE_SNAPSHOT_COMPLETED",
    "DATABRICKS_SHARE_SNAPSHOT_FAILED",
)


def _action_args_of_create_audit_event_calls(module_source: str) -> list[ast.expr]:
    """The AST shape of every ``create_audit_event(...)`` call's action
    argument in *module_source* (the emission-site pin's spine)."""
    tree = ast.parse(module_source)
    actions: list[ast.expr] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
        if name != "create_audit_event":
            continue
        for keyword in node.keywords:
            if keyword.arg == "action":
                actions.append(keyword.value)
    return actions


class TestDeltaSharingEventRegistration:
    """Every P5 share/snapshot event is registered (constant + __all__)
    and listed in the databricks_admin registration tuple."""

    def test_all_five_events_exist_and_are_exported(self):
        from hub.apps.audit import event_types

        for name in P5_SHARE_EVENTS:
            assert getattr(event_types, name, None) == name, f"{name} constant missing"
            assert name in event_types.__all__, f"{name} missing from __all__"

    def test_the_registration_tuple_lists_every_p5_event(self):
        from hub.apps.databricks_admin.tests.test_event_registration import (
            DATABRICKS_EVENTS,
        )

        for name in P5_SHARE_EVENTS:
            assert name in DATABRICKS_EVENTS, f"{name} missing from DATABRICKS_EVENTS"


class TestDeltaSharingEmissionSites:
    """Every production emission site references the CANONICAL constants
    — never an inlined string literal (the 0.16 contract)."""

    def test_the_protocol_views_import_the_constants_not_literals(self):
        from hub.apps.databricks_admin import delta_sharing_views as views

        source = Path(views.__file__).read_text()
        actions = _action_args_of_create_audit_event_calls(source)
        assert actions, "the views must carry create_audit_event emissions"
        for action in actions:
            assert isinstance(action, ast.Name), (
                f"the action {ast.dump(action)} must be a constant REFERENCE, "
                "never an inlined literal (the 0.16 contract)"
            )

    def test_the_throttle_emission_uses_the_constant(self):
        from hub.apps.databricks_admin import throttles

        source = Path(throttles.__file__).read_text()
        actions = _action_args_of_create_audit_event_calls(source)
        assert actions, "the throttle must carry the 429 emission"
        for action in actions:
            assert isinstance(action, ast.Name), (
                f"the action {ast.dump(action)} must be a constant REFERENCE"
            )

    def test_the_snapshot_service_emission_matches_the_registered_values(self):
        from hub.apps.audit import event_types
        from hub.apps.databricks_admin import delta_sharing_snapshot as snap

        assert snap._AUDIT_ACTION_COMPLETED == event_types.DATABRICKS_SHARE_SNAPSHOT_COMPLETED
        assert snap._AUDIT_ACTION_FAILED == event_types.DATABRICKS_SHARE_SNAPSHOT_FAILED
        # And the module imports them from event_types (the canonical
        # source), not from local literals.
        source = Path(snap.__file__).read_text()
        assert "from hub.apps.audit import event_types" in source or (
            "from hub.apps.audit.event_types import" in source
        )


class TestDeltaSharingAuditSmoke:
    """The registered values are what the emissions actually write (the
    layers agree end to end)."""

    def test_a_protocol_request_writes_the_registered_access_value(self):
        from hub.apps.audit import event_types
        from hub.apps.audit.models import AuditEvent
        from hub.apps.databricks_admin.tests._fixtures import require_dns
        from hub.apps.databricks_admin.tests.test_delta_sharing_endpoints import (
            PROTOCOL_BASE,
            _mk_asset,
            _mk_connection,
            _mk_recipient,
            _mk_token,
        )

        require_dns()
        tenant, admin = _setup_tenant()
        connection = _mk_connection(tenant)
        asset = _mk_asset(tenant, connection, table_ref="catalog.schema.orders")
        recipient = _mk_recipient(tenant, admin)
        _token, plaintext = _mk_token(recipient)

        from rest_framework.test import APIClient

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {plaintext}")
        before = set(AuditEvent.objects.values_list("id", flat=True))
        resp = client.get(f"{PROTOCOL_BASE}/shares/meshant/schemas/{asset.id.hex}/tables")
        assert resp.status_code == 200
        rows = AuditEvent.objects.filter(action=event_types.WAREHOUSE_SHARE_ACCESSED).exclude(
            id__in=before
        )
        assert rows.count() == 1
