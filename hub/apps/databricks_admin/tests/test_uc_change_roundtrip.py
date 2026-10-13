"""Task 2.11 (openspec add-databricks-uc-write) — the ACCEPTANCE round-trips.

The Phase 2 acceptance loop: DRAFT → submit → approve → execute → verify,
driving the REAL 2.2 service, the REAL 2.7 chains as pre-gates, and the
REAL 2.3 executor (production client in transport mode) against a REAL
local HTTP server — with the REAL 2.4 guards inside the executor (the
destructive flag is read from a REAL tenant row). No mocks: every leg is
the production path, and the wire request is asserted field-for-field.

The caller pattern pinned here is the 2.7 contract: run the chain
pre-gate (inside ``transaction.atomic()``), mutate through the 2.2
service, then hand the typed payload to the executor.
"""

import json
import uuid

import pytest
from django.db import transaction

from hub.apps.databricks_admin.tests._fixtures import require_dns
from hub.apps.databricks_admin.tests._http import RecordingHandler
from hub.apps.tenants.tests.factories import activate_billing
from tests.factories import TenantFactory

pytestmark = pytest.mark.django_db(transaction=True)


def _make_user(tenant, email, role_name=None):
    from hub.apps.users.models import Role, User, UserRole, UserStatus

    user = User.objects.create_user(
        email=f"{uuid.uuid4().hex[:8]}-{email}",
        password="testpass123",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )
    if role_name:
        role, _ = Role.objects.get_or_create(tenant=tenant, name=role_name)
        UserRole.objects.get_or_create(user=user, role=role)
    return user


def _make_workspace(tenant, name="ws-roundtrip"):
    from hub.apps.databricks_admin.models import DatabricksCloud, DatabricksWorkspace

    return DatabricksWorkspace.objects.create(
        tenant=tenant,
        name=f"{name}-{uuid.uuid4().hex[:8]}",
        host="dbc-6710eb95-8fe1.cloud.databricks.com",
        cloud=DatabricksCloud.AWS,
        region="us-east-1",
        status="ACTIVE",
    )


@pytest.fixture
def estate():
    """A tenant with an ACTIVE workspace, a TENANT_ADMIN approver, and a
    plain member (the step-2 approver in multi-step pins)."""
    require_dns()
    tenant = TenantFactory.create_tenant()
    activate_billing(tenant)
    admin = _make_user(tenant, "rt-admin@test.com", "TENANT_ADMIN")
    member = _make_user(tenant, "rt-member@test.com")
    workspace = _make_workspace(tenant)
    return tenant, admin, member, workspace


def _executor(port, tenant):
    from hub.apps.databricks_admin.client import DatabricksApiClient
    from hub.apps.databricks_admin.sql_statements import SqlStatementExecutor
    from hub.apps.databricks_admin.uc_change_executor import UCChangeExecutor

    client = DatabricksApiClient(
        base_url=f"http://127.0.0.1:{port}",
        credential_config={"token": "dapi-roundtrip"},
        max_retries=1,
        retry_base_delay=0.01,
        retry_max_delay=0.05,
    )
    return UCChangeExecutor(
        client=client,
        statement_executor=SqlStatementExecutor(client, warehouse_id="wh-1"),
        warehouse_id="wh-1",
        tenant=tenant,
    )


def _create(tenant, workspace, requested_by, **overrides):
    from hub.apps.databricks_admin.models import UCChangeAction, UCObjectType
    from hub.apps.databricks_admin.uc_changes import create_change_request

    kwargs = {
        "change_type": UCChangeAction.CREATE,
        "securable_type": UCObjectType.TABLE,
        "full_name": "main.sales.orders_v2",
        "definition": {
            "identifiers": ["main", "sales", "orders_v2"],
            "options": {"table_type": "MANAGED", "columns": []},
        },
    }
    kwargs.update(overrides)
    return create_change_request(
        tenant=tenant, workspace=workspace, requested_by=requested_by, **kwargs
    )


class TestDdlRoundTripAcceptance:
    def test_create_table_roundtrip_executes_and_verifies(self, estate, local_http_server):
        """THE acceptance loop — the chain pre-gates, the 2.2 service, the
        2.3 executor, and the wire request all real."""
        from hub.apps.core.business_rules.chains import execute_chain
        from hub.apps.databricks_admin.models import UCChangeRequestStatus
        from hub.apps.databricks_admin.uc_changes import (
            approve_change_request,
            build_ddl_payload,
            mark_executed,
            mark_executing,
            submit_change_request,
        )

        tenant, admin, _member, workspace = estate
        RecordingHandler.script = [200]

        change_request = _create(tenant, workspace, admin)
        with transaction.atomic():
            pre_gate = execute_chain(
                "databricks.uc.change.request", tenant=tenant, request=change_request
            )
        assert pre_gate["outcome"] == "PASS", pre_gate

        change_request = submit_change_request(change_request=change_request)
        assert change_request.status == UCChangeRequestStatus.PENDING_APPROVAL
        change_request = approve_change_request(change_request=change_request, approver=admin)
        assert change_request.status == UCChangeRequestStatus.APPROVED

        with transaction.atomic():
            exec_gate = execute_chain(
                "databricks.uc.change.execute", tenant=tenant, request=change_request
            )
        assert exec_gate["outcome"] == "PASS", exec_gate

        change_request = mark_executing(change_request=change_request)
        result = _executor(local_http_server, tenant).execute(build_ddl_payload(change_request))
        assert result.terminal == "EXECUTED", result

        request = RecordingHandler.requests[-1]
        assert request["method"] == "POST"
        assert request["path"] == "/api/2.1/unity-catalog/tables"
        assert request["headers"].get("Authorization") == "Bearer dapi-roundtrip"
        body = json.loads(request["body"])
        assert body["name"] == "orders_v2"
        assert body["catalog_name"] == "main"
        assert body["schema_name"] == "sales"
        assert body["table_type"] == "MANAGED"

        change_request = mark_executed(change_request=change_request, executor=admin)
        change_request.refresh_from_db()
        assert change_request.status == UCChangeRequestStatus.EXECUTED
        assert change_request.executed_by == admin
        assert change_request.executed_at is not None

    def test_multi_step_roundtrip_completes(self, estate, local_http_server):
        """272.4 through the whole loop: step 1 → PENDING_NEXT_APPROVER →
        step 2 → APPROVED → executed (the 2.7 stage agreement)."""
        from hub.apps.databricks_admin.models import UCChangeRequestStatus
        from hub.apps.databricks_admin.uc_changes import (
            approve_change_request,
            build_ddl_payload,
            mark_executed,
            mark_executing,
            submit_change_request,
        )

        tenant, admin, member, workspace = estate
        RecordingHandler.script = [200]

        change_request = _create(
            tenant,
            workspace,
            admin,
            required_approval_chain=[
                {"step": 1, "role": "TENANT_ADMIN", "label": "Admin"},
                {"step": 2, "approvers": [str(member.id)], "label": "Data engineer"},
            ],
        )
        change_request = submit_change_request(change_request=change_request)
        change_request = approve_change_request(change_request=change_request, approver=admin)
        assert change_request.status == UCChangeRequestStatus.PENDING_NEXT_APPROVER
        change_request = approve_change_request(change_request=change_request, approver=member)
        assert change_request.status == UCChangeRequestStatus.APPROVED

        change_request = mark_executing(change_request=change_request)
        result = _executor(local_http_server, tenant).execute(build_ddl_payload(change_request))
        assert result.terminal == "EXECUTED", result
        change_request = mark_executed(change_request=change_request, executor=member)
        assert change_request.status == UCChangeRequestStatus.EXECUTED

    def test_destructive_drop_roundtrip_on_flag_on_tenant(self, estate, local_http_server):
        """The denylist leg of the loop: a DROP on a flag-ON tenant passes
        the guards and reaches the DELETE pin on the wire."""
        from hub.apps.core.business_rules.chains import execute_chain
        from hub.apps.databricks_admin.models import (
            UCChangeAction,
            UCChangeRequestStatus,
            UCObjectType,
        )
        from hub.apps.databricks_admin.uc_changes import (
            approve_change_request,
            build_ddl_payload,
            mark_executed,
            mark_executing,
            submit_change_request,
        )

        tenant, admin, _member, workspace = estate
        tenant.databricks_uc_destructive_ddl_enabled = True
        tenant.save(update_fields=["databricks_uc_destructive_ddl_enabled", "updated_at"])
        RecordingHandler.script = [200]

        change_request = _create(
            tenant,
            workspace,
            admin,
            change_type=UCChangeAction.DROP,
            securable_type=UCObjectType.CATALOG,
            full_name="main",
            definition={"identifiers": ["main"], "options": {}},
        )
        with transaction.atomic():
            pre_gate = execute_chain(
                "databricks.uc.change.request", tenant=tenant, request=change_request
            )
        assert pre_gate["outcome"] == "PASS", pre_gate
        change_request = submit_change_request(change_request=change_request)
        change_request = approve_change_request(change_request=change_request, approver=admin)
        change_request = mark_executing(change_request=change_request)
        result = _executor(local_http_server, tenant).execute(build_ddl_payload(change_request))
        assert result.terminal == "EXECUTED", result
        request = RecordingHandler.requests[-1]
        assert request["method"] == "DELETE"
        assert request["path"] == "/api/2.1/unity-catalog/catalogs/main"
        change_request = mark_executed(change_request=change_request, executor=admin)
        assert change_request.status == UCChangeRequestStatus.EXECUTED

    def test_requires_no_approval_shortcut_executes(self, estate, local_http_server):
        """requires_approval=False routes DRAFT → APPROVED on submit — the
        approval-skip leg of the loop."""
        from hub.apps.databricks_admin.models import UCChangeRequestStatus
        from hub.apps.databricks_admin.uc_changes import (
            build_ddl_payload,
            mark_executed,
            mark_executing,
            submit_change_request,
        )

        tenant, admin, _member, workspace = estate
        RecordingHandler.script = [200]

        change_request = _create(tenant, workspace, admin, requires_approval=False)
        change_request = submit_change_request(change_request=change_request)
        assert change_request.status == UCChangeRequestStatus.APPROVED
        change_request = mark_executing(change_request=change_request)
        result = _executor(local_http_server, tenant).execute(build_ddl_payload(change_request))
        assert result.terminal == "EXECUTED", result
        change_request = mark_executed(change_request=change_request, executor=admin)
        assert change_request.status == UCChangeRequestStatus.EXECUTED

    def test_workspace_rejection_roundtrip_fails_then_rolls_back(self, estate, local_http_server):
        """The FAILED → ROLLED_BACK spine on a REAL workspace rejection:
        the classified error is recorded and the rollback completes."""
        from hub.apps.databricks_admin.client import DatabricksServerError
        from hub.apps.databricks_admin.models import UCChangeRequestStatus
        from hub.apps.databricks_admin.uc_changes import (
            approve_change_request,
            build_ddl_payload,
            mark_executing,
            mark_failed,
            mark_rolled_back,
            submit_change_request,
        )

        tenant, admin, _member, workspace = estate
        RecordingHandler.script = [500]

        change_request = _create(tenant, workspace, admin)
        change_request = submit_change_request(change_request=change_request)
        change_request = approve_change_request(change_request=change_request, approver=admin)
        change_request = mark_executing(change_request=change_request)
        with pytest.raises(DatabricksServerError) as excinfo:
            _executor(local_http_server, tenant).execute(build_ddl_payload(change_request))
        change_request = mark_failed(change_request=change_request, error=str(excinfo.value))
        change_request.refresh_from_db()
        assert change_request.status == UCChangeRequestStatus.FAILED
        assert "500" in change_request.execution_error
        change_request = mark_rolled_back(change_request=change_request, actor=admin)
        assert change_request.status == UCChangeRequestStatus.ROLLED_BACK
        assert change_request.rolled_back_by == admin

    def test_execute_pre_gate_blocks_before_approval(self, estate):
        """The caller pattern's refusal leg: the execute chain FAILS on a
        PENDING_APPROVAL request with the 2.9 approval-required code, so
        the caller never reaches the executor."""
        from hub.apps.core.business_rules.chains import execute_chain
        from hub.apps.databricks_admin.uc_changes import submit_change_request

        tenant, admin, _member, workspace = estate
        RecordingHandler.script = [200]

        change_request = _create(tenant, workspace, admin)
        change_request = submit_change_request(change_request=change_request)
        with transaction.atomic():
            exec_gate = execute_chain(
                "databricks.uc.change.execute", tenant=tenant, request=change_request
            )
        assert exec_gate["outcome"] == "FAIL", exec_gate
        assert any("DATABRICKS_DDL_APPROVAL_REQUIRED" in err for err in exec_gate["errors"]), (
            exec_gate
        )
        assert len(RecordingHandler.requests) == 0, "the pre-gate refusal must not hit the network"
