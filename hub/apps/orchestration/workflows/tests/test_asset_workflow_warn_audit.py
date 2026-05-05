"""
Phase 250.7.E — WARN audit emission for asset-creation workflows.

Pins the contract:
- when ``state_data.result_summary.warnings`` exists, the
  workflow's ``_audit_logging_task`` emits
  ``ASSET_WORKFLOW_WARN_LOGGED`` with that payload.
- when no warnings exist, no WARN audit row is emitted.
"""

from __future__ import annotations

import uuid
from typing import Any, cast

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.audit import event_types as audit_event_types
from hub.apps.audit.models import AuditEvent
from hub.apps.orchestration.models import (
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowStatus,
)
from hub.apps.orchestration.workflows.asset_creation import AssetCreationWorkflow
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


def _seed_tenant_user_asset():
    uid = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"warn-audit-{uid}",
        slug=f"warn-audit-{uid}",
        status="ACTIVE",
        kyc_status="UNVERIFIED",
    )
    ensure_tenant_has_active_subscription(tenant)
    user_manager = cast("Any", User.objects)
    user = user_manager.create_user(
        email=f"warn-{uid}@example.com",
        password="testpass123",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )
    asset = Asset.objects.create(
        tenant=tenant,
        key=f"warn-asset-{uid}",
        name="Warn Asset",
        status=AssetStatus.DRAFT,
        created_by=user,
    )
    return tenant, user, asset


def _seed_workflow_instance(*, tenant, user, asset, warnings_payload=None):
    workflow_def = WorkflowDefinition.objects.create(
        name="asset_creation_warn_test",
        version="1.0.0",
        dsl_json={
            "version": "1.0.0",
            "steps": [{"name": "audit_logging", "type": "task"}],
        },
        is_active=True,
        created_by=user,
    )
    state_data = {"asset_id": str(asset.id), "activated": False}
    if warnings_payload is not None:
        state_data["result_summary"] = {"warnings": warnings_payload}
    return WorkflowInstance.objects.create(
        workflow_definition=workflow_def,
        workflow_name="asset_creation_warn_test",
        workflow_version="1.0.0",
        tenant=tenant,
        status=WorkflowStatus.RUNNING,
        input_data={},
        state_data=state_data,
        created_by=user,
    )


class AssetWorkflowWarnAuditTest(TestCase):
    def test_emits_warn_audit_with_result_summary_warnings_payload(self):
        tenant, user, asset = _seed_tenant_user_asset()
        warnings_payload = [
            {
                "step": "create_asset_record",
                "message": "Asset validation warnings",
                "warnings": ["domain is uncommon"],
            },
            {
                "step": "activate_asset",
                "message": "Asset activation validation warnings",
                "warnings": ["minor lifecycle warning"],
            },
        ]
        instance = _seed_workflow_instance(
            tenant=tenant,
            user=user,
            asset=asset,
            warnings_payload=warnings_payload,
        )

        before = AuditEvent.objects.filter(
            tenant=tenant,
            action=audit_event_types.ASSET_WORKFLOW_WARN_LOGGED,
        ).count()

        AssetCreationWorkflow._audit_logging_task({}, instance, step=None)

        after_rows = AuditEvent.objects.filter(
            tenant=tenant,
            action=audit_event_types.ASSET_WORKFLOW_WARN_LOGGED,
        ).order_by("-timestamp")

        assert after_rows.count() == before + 1
        row = after_rows.first()
        assert row is not None
        assert row.result == "WARNING"
        assert row.details_json["tenant_id"] == str(tenant.id)
        assert row.details_json["asset_id"] == str(asset.id)
        assert row.details_json["workflow_instance_id"] == str(instance.id)
        assert row.details_json["result_summary"]["warnings"] == warnings_payload

    def test_does_not_emit_warn_audit_when_result_summary_has_no_warnings(self):
        tenant, user, asset = _seed_tenant_user_asset()
        instance = _seed_workflow_instance(
            tenant=tenant,
            user=user,
            asset=asset,
            warnings_payload=None,
        )

        before = AuditEvent.objects.filter(
            tenant=tenant,
            action=audit_event_types.ASSET_WORKFLOW_WARN_LOGGED,
        ).count()

        AssetCreationWorkflow._audit_logging_task({}, instance, step=None)

        after = AuditEvent.objects.filter(
            tenant=tenant,
            action=audit_event_types.ASSET_WORKFLOW_WARN_LOGGED,
        ).count()
        assert after == before
