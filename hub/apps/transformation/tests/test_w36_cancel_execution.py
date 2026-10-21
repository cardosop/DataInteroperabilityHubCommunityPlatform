"""W3.6 (oss-release-remediation R2-P4/F13) — the transformation cancel
endpoint reaches the RUNNING workflow.

The pre-existing endpoint cancels the PipelineExecution + its Job — but
a RUNNING WorkflowInstance kept executing its steps (the engine held a
row lock and had no checkpoint).  The endpoint now writes the
out-of-band ``WorkflowCancellationRequest`` for a RUNNING instance (the
engine's between-step checkpoints consume it and stop the run) and
marks a not-yet-started (DRAFT) instance CANCELLED directly.

Pins (real DB + the real endpoint; no mocks):

  * RUNNING instance → execution CANCELLED, job CANCELLED, and a
    cancellation request exists for the workflow instance.
  * DRAFT instance → the instance itself is CANCELLED (no engine run
    will ever start it).
  * A COMPLETED execution cannot be cancelled (400 — the existing
    contract).
"""

from __future__ import annotations

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.orchestration.models import (
    WorkflowCancellationRequest,
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowStatus,
)
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.transformation.models import (
    ExecutionMode,
    ExecutionStatus,
    PipelineExecution,
    TransformationPipeline,
)

pytestmark = pytest.mark.django_db(transaction=True)

User = get_user_model()


class TransformationCancelExecutionTest(TestCase):
    def setUp(self):
        unique = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"W36 Transform Tenant {unique}",
            slug=f"w36-transform-tenant-{unique}",
            status="ACTIVE",
            kyc_status=KYCStatus.UNVERIFIED,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"w36-transform-{unique}@example.com",
            password="testpass123",
            tenant=self.tenant,
        )
        # P3-1: the execution surface requires the transformation scopes
        # (the viewset's HasScope contract; scopes resolve from the
        # user's ROLES) — the pre-fix tests had no roles and every
        # cancel returned 403 AUTH_FORBIDDEN before reaching the view
        # body. Mirrors the canonical test_views.py setup.
        from hub.apps.auth.models import APIKey
        from hub.apps.users.models import Role

        APIKey.objects.create(
            tenant=self.tenant,
            user=self.user,
            name="w36-test-key",
            scopes=["transformation:write", "transformation:read"],
        )
        data_provider_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="DATA_PROVIDER",
            defaults={"description": "Data Provider Role"},
        )
        self.user.user_roles.create(role=data_provider_role)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"w36-asset-{unique}",
            name="W36 Asset",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )

        self.result_asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"w36-result-{unique}",
            name="W36 Result Asset",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )

        self.pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            name=f"W36 Pipeline {unique}",
            pipeline_definition={"version": "1.0.0", "steps": [{"name": "s1", "type": "filter"}]},
            status="ACTIVE",
            created_by=self.user,
        )

        self.workflow_def = WorkflowDefinition.objects.create(
            name="transformation_pipeline",
            version="1.0.0",
            description="fixture",
            dsl_json={
                "version": "1.0.0",
                "steps": [
                    {"name": "validate_pipeline", "type": "task", "task": "t"},
                    {"name": "run_pipeline", "type": "task", "task": "t"},
                ],
            },
        )

    def _mk_workflow_instance(self, wf_status):
        return WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name="transformation_pipeline",
            workflow_version="1.0.0",
            tenant_id=self.tenant.id,
            status=wf_status,
            input_data={},
        )

    def _mk_job(self):
        return Job.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            type=JobType.TRANSFORMATION,
            status=JobStatus.RUNNING,
            resource_type="TRANSFORMATION_PIPELINE",
            resource_id=str(self.pipeline.id),
            details_json={},
        )

    def _mk_execution(self, exec_status, workflow_instance=None, job=None):
        return PipelineExecution.objects.create(
            pipeline=self.pipeline,
            asset=self.asset,
            execution_mode=ExecutionMode.ASYNC,
            status=exec_status,
            workflow_instance=workflow_instance,
            job=job,
            result_asset=(self.result_asset if exec_status == ExecutionStatus.COMPLETED else None),
        )

    def _cancel(self, execution_id):
        return self.client.post(
            f"/api/v1/transformation/executions/{execution_id}/cancel/",
            format="json",
        )

    def test_cancel_running_execution_writes_cancellation_request(self):
        workflow_instance = self._mk_workflow_instance(WorkflowStatus.RUNNING)
        job = self._mk_job()
        execution = self._mk_execution(
            ExecutionStatus.RUNNING, workflow_instance=workflow_instance, job=job
        )

        resp = self._cancel(execution.id)

        assert resp.status_code == status.HTTP_200_OK, resp.data
        execution.refresh_from_db()
        job.refresh_from_db()
        assert execution.status == ExecutionStatus.CANCELLED
        assert job.status == JobStatus.CANCELLED
        request_row = WorkflowCancellationRequest.objects.filter(
            workflow_instance_id=workflow_instance.id
        ).first()
        assert request_row is not None, (
            "a RUNNING workflow needs the out-of-band request — the engine's "
            "checkpoints stop the run; same-row writes can never commit under "
            "its select_for_update"
        )

    def test_cancel_draft_execution_cancels_instance_directly(self):
        workflow_instance = self._mk_workflow_instance(WorkflowStatus.DRAFT)
        execution = self._mk_execution(ExecutionStatus.PENDING, workflow_instance=workflow_instance)

        resp = self._cancel(execution.id)

        assert resp.status_code == status.HTTP_200_OK, resp.data
        workflow_instance.refresh_from_db()
        assert workflow_instance.status == WorkflowStatus.CANCELLED, (
            "a not-yet-started instance is cancelled directly — no engine run may ever start it"
        )

    def test_completed_execution_cannot_be_cancelled(self):
        execution = self._mk_execution(ExecutionStatus.COMPLETED)

        resp = self._cancel(execution.id)

        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        execution.refresh_from_db()
        assert execution.status == ExecutionStatus.COMPLETED
