"""
W12.8 (oss-release-remediation) — execute_pipeline idempotency veracity pins.

The named liar: the ``idempotency_key`` param docstring promised "retry
safety" while the replay check ran AFTER the plan-limit check and the
queue-depth metric — a replay of a completed execution burned plan
quota (and could be REJECTED with plan_limit_exceeded instead of
returning the completed run) and bumped the metric; the key itself was
only written after the workflow landed, and a concurrent same-key race
surfaced as a raw IntegrityError (500-shaped INTERNAL_ERROR).

Root fix (W12.8): the idempotency check now runs FIRST — replays
return the terminal execution without consuming quota or metrics — and
the concurrent race converts the unique-constraint failure into the
classified duplicate error.  The claim timing (key written when the
execution lands) is now stated honestly in the docstring.

The pins run against the REAL service with REAL DB rows — no mocks.
"""

from __future__ import annotations

import uuid

import pytest
from django.test import TestCase

from hub.apps.assets.models import Asset
from hub.apps.tenants.models import PlanCategory, PlanTier, Tenant, TenantPlan
from hub.apps.transformation.exceptions import TransformationExecutionError
from hub.apps.transformation.models import (
    ExecutionMode,
    ExecutionStatus,
    PipelineExecution,
    PipelineStatus,
    TransformationPipeline,
)
from hub.apps.transformation.services import TransformationService

pytestmark = [pytest.mark.django_db]


class ExecutePipelineIdempotencyTest(TestCase):
    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Idem Tenant {uid}",
            slug=f"idem-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        # Plan capped at ONE transformation run per month: any second
        # run (or a replay under the pre-fix ordering) trips the limit.
        self.plan = TenantPlan.objects.create(
            slug=f"capped-{uid}",
            name=f"Capped {uid}",
            tier=PlanTier.FREE,
            category=PlanCategory.BASE,
            order=99,
            is_active=True,
            price_amount_cents=0,
            price_currency="USD",
            billing_interval="monthly",
            limits_json={"max_transformation_runs_per_month": 1},
        )
        self.tenant.plan = self.plan
        self.tenant.save(update_fields=["plan"])

        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"idem-asset-{uid}",
            name=f"idem-asset-{uid}",
        )
        self.pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            name=f"idem-pipeline-{uid}",
            pipeline_definition={
                "version": "1.0.0",
                "steps": [
                    {
                        "name": "noop_step",
                        "type": "task",
                        "operation": "filter",
                        "config": {},
                    }
                ],
            },
            status=PipelineStatus.ACTIVE,
        )
        self.key = f"w128-key-{uid}"
        self.result_asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"idem-result-{uid}",
            name=f"idem-result-{uid}",
        )
        # The completed run counts toward the monthly cap.
        self.execution = PipelineExecution.objects.create(
            pipeline=self.pipeline,
            asset=self.asset,
            result_asset=self.result_asset,
            execution_mode=ExecutionMode.ASYNC,
            status=ExecutionStatus.COMPLETED,
            idempotency_key=self.key,
        )
        self.service = TransformationService(tenant_id=str(self.tenant.id))

    def test_replay_returns_terminal_execution_without_consuming_quota(self):
        """At the plan cap, a replay of a COMPLETED execution must return
        the existing execution — NOT trip plan_limit_exceeded (the
        pre-fix ordering checked the plan limit first)."""
        result = self.service.execute_pipeline(
            pipeline_id=str(self.pipeline.id),
            asset_id=str(self.asset.id),
            idempotency_key=self.key,
        )
        assert result.id == self.execution.id
        assert result.status == ExecutionStatus.COMPLETED
        # No new execution row was created — the cap is untouched.
        assert (
            PipelineExecution.objects.filter(pipeline=self.pipeline).count()
            == 1
        )

    def test_non_terminal_duplicate_raises_the_classified_error(self):
        self.execution.status = ExecutionStatus.RUNNING
        self.execution.save(update_fields=["status"])
        with pytest.raises(TransformationExecutionError) as excinfo:
            self.service.execute_pipeline(
                pipeline_id=str(self.pipeline.id),
                asset_id=str(self.asset.id),
                idempotency_key=self.key,
            )
        assert "already exists" in str(excinfo.value)
        assert (
            PipelineExecution.objects.filter(pipeline=self.pipeline).count()
            == 1
        )

    def test_docstring_states_the_replay_contract(self):
        import inspect

        doc = inspect.getdoc(TransformationService.execute_pipeline)
        assert doc, "execute_pipeline docstring missing"
        flat = " ".join(doc.split())  # docstrings wrap — normalize
        assert "REPLAY" in flat, (
            "the docstring must state the replay contract (terminal "
            "executions return without consuming quota/metrics)"
        )
        assert "claimed when the execution lands" in flat, (
            "the docstring must state when the key is claimed (a crash "
            "before that leaves the retry unguarded)"
        )
