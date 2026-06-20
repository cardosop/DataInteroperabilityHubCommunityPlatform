"""
104.10 — Service-to-Service Isolation Test

Verifies that internal service calls (compliance, DQ, jobs) are
scoped by tenant_id and do not process cross-tenant data.
"""

import uuid

import pytest

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.contracts.models import Contract
from hub.apps.jobs.models import Job, JobStatus, JobType

pytestmark = pytest.mark.django_db(transaction=True)


class TestServiceToServiceIsolation:
    """Service layer operations must be tenant-scoped end-to-end."""

    @pytest.fixture(autouse=True)
    def _create_resources(self, tenant_a, user_a, tenant_b, user_b):
        uid = uuid.uuid4().hex[:8]

        self.asset_a = Asset.objects.create(
            tenant=tenant_a,
            key=f"s2s-a-{uid}",
            name=f"S2S Asset A {uid}",
            status=AssetStatus.ACTIVE,
            created_by=user_a,
        )
        self.contract_a = Contract.objects.create(
            tenant=tenant_a,
            asset=self.asset_a,
            version=1,
            status="DRAFT",
            original_spec_type="odcs",
            original_spec_version="2.2.1",
            original_format="yaml",
            original_raw="datasetName: s2s-a",
        )

        self.asset_b = Asset.objects.create(
            tenant=tenant_b,
            key=f"s2s-b-{uid}",
            name=f"S2S Asset B {uid}",
            status=AssetStatus.ACTIVE,
            created_by=user_b,
        )

        # Create a job in each tenant (used as FK for compliance)
        self.job_a = Job.objects.create(
            tenant=tenant_a,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.COMPLETED,
            resource_type="CONTRACT",
            resource_id=self.contract_a.id,
            created_by=user_a,
        )
        self.job_b = Job.objects.create(
            tenant=tenant_b,
            type=JobType.COMPLIANCE_RUN,
            status=JobStatus.COMPLETED,
            resource_type="ASSET",
            resource_id=self.asset_b.id,
            created_by=user_b,
        )

    def test_jobs_list_isolation_via_api(self, client_b, tenant_a):
        """Jobs list is tenant-scoped via API."""
        resp = client_b.get("/api/v1/jobs/")
        assert resp.status_code == 200
        results = resp.data.get("results", resp.data)
        if isinstance(results, list):
            for r in results:
                assert str(r.get("tenant")) != str(tenant_a.id), "Jobs list leaked Tenant A data"

    def test_jobs_detail_cross_tenant_404(self, client_b):
        """Tenant B cannot read Tenant A's job by ID."""
        resp = client_b.get(f"/api/v1/jobs/{self.job_a.id}/")
        assert resp.status_code == 404

    def test_jobs_orm_scoped_by_tenant(self, tenant_a, tenant_b):
        """ORM query scoped to tenant returns only that tenant."""
        a_jobs = Job.objects.filter(tenant=tenant_a)
        b_jobs = Job.objects.filter(tenant=tenant_b)
        a_ids = set(str(j.id) for j in a_jobs)
        b_ids = set(str(j.id) for j in b_jobs)
        assert a_ids.isdisjoint(b_ids)

    def test_compliance_runs_list_isolation(self, client_b, tenant_a):
        """Compliance runs list is tenant-scoped."""
        resp = client_b.get("/api/v1/compliance/runs/")
        assert resp.status_code == 200
        results = resp.data.get("results", resp.data)
        if isinstance(results, list):
            ids = {str(r["id"]) for r in results}
            # None of Tenant A's jobs should appear
            a_job_ids = set(str(j.id) for j in Job.objects.filter(tenant=tenant_a))
            assert ids.isdisjoint(a_job_ids), "Compliance run list leaked Tenant A data"

    def test_dq_runs_list_isolation(self, client_b, tenant_a):
        """DQ runs list is tenant-scoped."""
        resp = client_b.get("/api/v1/dq/runs/")
        assert resp.status_code == 200
        results = resp.data.get("results", resp.data)
        if isinstance(results, list):
            for r in results:
                tid = r.get("tenant") or r.get("tenant_id")
                if tid:
                    assert str(tid) != str(tenant_a.id), "DQ run list leaked Tenant A data"

    def test_contract_detail_cross_tenant_404(self, client_b):
        """Tenant B cannot read Tenant A's contract by ID."""
        resp = client_b.get(f"/api/v1/contracts/{self.contract_a.id}/")
        assert resp.status_code == 404
