"""
Base test classes for DQ tests to follow DRY principle.

This module provides common base classes to eliminate code duplication
in setUp methods across test files.
"""

import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from hub.apps.dq.services import DQService
from hub.apps.files.models import File, FileStatus
from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import UserStatus

User = get_user_model()


def _create_dq_test_fixtures(test_case):
    """Create the common tenant/user/service/file/job fixtures on *test_case*.

    Extracted from the duplicated ``setUp`` bodies in ``DQTestBase`` and
    ``DQTestBaseExtended`` so the two classes share a single source of
    truth for fixture creation.
    """
    test_case.tenant = Tenant.objects.create(
        name=f"Test Tenant {uuid.uuid4().hex[:8]}",
        slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
        status=TenantStatus.ACTIVE,
        kyc_status=KYCStatus.VERIFIED,
        # Phase 240.4.B audit-fix Gap 1 — both DQ flags default
        # ON in test fixtures so the existing 240.3.B
        # advanced-endpoint tests (test_quality_endpoints.py)
        # don't regress to 403 on the conjunctive gate.  The
        # advanced flag's PRODUCTION default is False (D240.18,
        # staged rollout) but TEST fixtures want full DQ access
        # by default — feature-flag-specific tests
        # (test_feature_flag.py) override these via
        # _set_flags(...) when they need to assert per-flag
        # behaviour.  The model default is still False
        # production-side; this only changes test-fixture
        # behaviour.
        data_quality_enabled=True,
        data_quality_advanced_enabled=True,
    )
    ensure_tenant_has_active_subscription(test_case.tenant)

    test_case.user = User.objects.create_user(
        email=f"test-{uuid.uuid4().hex[:8]}@example.com",
        password="testpass123",
        tenant=test_case.tenant,
        status=UserStatus.ACTIVE,
    )

    test_case.service = DQService(
        tenant_id=str(test_case.tenant.id), user_id=str(test_case.user.id)
    )

    file_id = uuid.uuid4()
    test_case.file = File.objects.create(
        id=file_id,
        tenant=test_case.tenant,
        name="test.csv",
        content_type="text/csv",
        size=1024,
        status=FileStatus.ACTIVE,
        storage_path=f"{test_case.tenant.id}/{file_id}/test.csv",
        created_by=test_case.user,
    )

    test_case.job = Job.objects.create(
        tenant=test_case.tenant,
        type=JobType.DQ_RUN,
        status=JobStatus.PENDING,
        resource_type="DQ_RUN",
        resource_id=uuid.uuid4(),
        created_by=test_case.user,
        timeout_seconds=1800,
    )


class DQTestBase(TestCase):
    """Base test class for DQ tests with common setUp code."""

    def setUp(self):
        """Set up common test fixtures."""
        super().setUp()
        _create_dq_test_fixtures(self)


class DQTestBaseExtended(TestCase):
    """Base test class for DQ tests requiring a distinct hierarchy from
    ``DQTestBase``.

    .. note::

        This class extends ``TestCase``, **not** ``TransactionTestCase``.
        The original name ``DQTransactionTestBase`` was a misnomer — it
        was never refactored to extend ``TransactionTestCase``, and
        renaming it avoids misleading developers about the transaction
        isolation semantics.
    """

    def setUp(self):
        """Set up common test fixtures."""
        super().setUp()
        _create_dq_test_fixtures(self)


class DQAPITestBase(DQTestBase):
    """Base test class for API tests with authenticated client."""

    def setUp(self):
        """Set up API test fixtures."""
        super().setUp()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)


class DQAPITestBaseExtended(DQTestBaseExtended):
    """Base test class for API tests using the extended hierarchy.

    Inherits from ``DQTestBaseExtended`` instead of ``DQTestBase`` so
    tests that need a separate class hierarchy (e.g. for different
    ``TestCase`` subclasses in the future) can coexist.
    """

    def setUp(self):
        """Set up API test fixtures."""
        super().setUp()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
