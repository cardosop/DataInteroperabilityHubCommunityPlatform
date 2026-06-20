"""
Test helpers for asset activation flow.

Provides ``ensure_activation_prereqs()`` which gives an asset
everything the activation gate requires so business-rule tests
can focus on what they're actually testing rather than
re-creating the same prerequisites in every setUp method.

Usage::

    from hub.apps.testing.activation_helpers import ensure_activation_prereqs

    class MyTest(TestCase):
        def test_activate(self):
            asset = Asset.objects.create(...)
            contract = Contract.objects.create(asset=asset, ...)
            ensure_activation_prereqs(asset, self.tenant, self.user)
            response = self.client.post(f"/api/v1/assets/{asset.id}/activate/", ...)
            self.assertEqual(response.status_code, 200)
"""

import uuid

from django.utils import timezone


def ensure_activation_prereqs(asset, tenant, user):
    """
    Give *asset* everything the activation gate requires:
    - dq_status = PASS
    - compliance_status = PASS
    - a SUCCEEDED ComplianceRun with allowed_to_store = True

    Returns the created ComplianceRun instance (or None on failure).
    """
    from hub.apps.assets.models import ComplianceStatus, DQStatus
    from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus
    from hub.apps.jobs.models import JobType
    from hub.apps.jobs.utils import create_job

    asset.dq_status = DQStatus.PASS
    asset.compliance_status = ComplianceStatus.PASS
    asset.save(update_fields=["dq_status", "compliance_status", "updated_at"])

    try:
        job = create_job(
            tenant=tenant,
            user=user,
            job_type=JobType.COMPLIANCE_RUN,
            resource_type="COMPLIANCE_RUN",
            resource_id=str(uuid.uuid4()),
            details_json={"scan_mode": "internal"},
            executed_by_prefect=True,
        )
    except Exception:
        job = None

    return ComplianceRun.objects.create(
        tenant=tenant,
        asset=asset,
        job=job,
        status=ComplianceRunStatus.SUCCEEDED,
        allowed_to_store=True,
        completed_at=timezone.now(),
    )
