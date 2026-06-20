"""
285.11.2.6 — Tests for lineage-based auto-derivation.
"""

import uuid
from io import StringIO

import pytest
from django.core.management import call_command
from django.test import TestCase

from hub.apps.orchestration.models import (
    PipelineDependency,
)

pytestmark = pytest.mark.django_db(transaction=True)


def _make_tenant():
    from hub.apps.tenants.models import Tenant

    slug = f"t-{uuid.uuid4().hex[:8]}"
    return Tenant.objects.create(
        name=f"Test-{slug}",
        slug=slug,
        status="ACTIVE",
        pipeline_dependency_enabled=True,
    )


@pytest.mark.integration
class TestAutoDerivation(TestCase):
    @pytest.mark.integration
    def test_dry_run_no_edges_produces_zero(self):
        tenant = _make_tenant()
        out = StringIO()
        call_command(
            "derive_dependencies_from_lineage",
            tenant_id=str(tenant.id),
            dry_run=True,
            stdout=out,
        )
        self.assertIn("No new pipeline dependencies derived", out.getvalue())

    @pytest.mark.integration
    def test_command_with_unknown_tenant(self):
        """Unknown tenant UUID should not error — just find no edges."""
        out = StringIO()
        call_command(
            "derive_dependencies_from_lineage",
            tenant_id=str(uuid.uuid4()),
            stdout=out,
        )
        self.assertIn("No new pipeline dependencies derived", out.getvalue())

    @pytest.mark.integration
    def test_alert_email_validates(self):
        """EmailField validation — valid emails should pass full_clean."""

        dep = PipelineDependency(
            tenant=_make_tenant(),
            pipeline_type="dq",
            pipeline_id=str(uuid.uuid4()),
            dependency_type="DATA",
            downstream_pipeline_type="transformation",
            downstream_pipeline_id=str(uuid.uuid4()),
            alert_email="admin@example.com",
        )
        # Should not raise — alert_webhook_url (which had SSRF validation) was
        # removed in migration 0010; alert_email is a plain EmailField.
        dep.full_clean()
        self.assertEqual(dep.alert_email, "admin@example.com")

    @pytest.mark.integration
    def test_alert_email_rejects_invalid(self):
        """EmailField should reject non-email values at the DB/model level."""
        from django.core.exceptions import ValidationError

        dep = PipelineDependency(
            tenant=_make_tenant(),
            pipeline_type="dq",
            pipeline_id=str(uuid.uuid4()),
            dependency_type="DATA",
            downstream_pipeline_type="transformation",
            downstream_pipeline_id=str(uuid.uuid4()),
            alert_email="not-an-email",
        )
        with self.assertRaises(ValidationError):
            dep.full_clean()
