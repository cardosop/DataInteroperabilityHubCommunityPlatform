"""P0 (openspec add-databricks-control-plane task 0.4) — workspace host + residency validation.

No mocks:
- The syntactic layer (host-family allowlist, normalisation) is pure and
  fully offline-deterministic.
- The SSRF layer reuses the canonical ``SSRFGuard`` (Phase 250.5.B) — its
  save-time path resolves real DNS and its dispatch-time path re-resolves
  via dnspython; negative cases are deterministic in both resolver
  configurations (unresolvable/private → violation).
- Positive save/dispatch cases against the real ``.env.test`` Databricks
  host are W16-gated: DNS-less environments skip locally and raise in CI
  (``envpolicy.environment_guard``).
- Residency reuses ``validate_warehouse_region`` — pure ISO mapping,
  offline-deterministic.
"""

import socket

import pytest
from django.core.exceptions import ValidationError
from django.test import TestCase

from envpolicy import environment_guard
from hub.apps.databricks_admin.models import DatabricksCloud, DatabricksWorkspace
from hub.apps.databricks_admin.validation import (
    check_host_family,
    normalise_host,
    revalidate_workspace_host,
    validate_workspace_host,
    validate_workspace_region,
)
from tests.factories import TenantFactory

pytestmark = pytest.mark.django_db(transaction=True)

# Real workspace host from .env.test — publicly resolvable (3.128.x).
REAL_HOST = "dbc-6710eb95-8fe1.cloud.databricks.com"


def _require_dns():
    """W16: positive cases need public DNS. CI raises; local runs skip."""
    try:
        socket.getaddrinfo(REAL_HOST, None)
    except OSError:
        environment_guard("public DNS unavailable — Databricks host resolution required")
        pytest.skip("public DNS unavailable — Databricks host resolution required")


class HostFamilyTests(TestCase):
    """Pure syntactic layer — no DNS, fully offline-deterministic."""

    def test_databricks_family_suffixes_accepted(self):
        for host in (
            "dbc-123.cloud.databricks.com",
            "adb-123.4.azuredatabricks.net",
            "xyz.gcp.databricks.com",
            "dbc-123.databricks.us",
        ):
            assert check_host_family(host) == host.lower()

    def test_non_databricks_family_rejected(self):
        for host in (
            "evil.example.com",
            "databricks.com",  # bare apex — not a workspace host
            "cloud.databricks.com",  # no subdomain label
            "cloud.databricks.com.attacker.com",  # suffix confusion
            "databricks.com.evil.com",
            "10.0.0.1",  # bare IP literal
        ):
            with pytest.raises(ValidationError) as excinfo:
                check_host_family(host)
            # Dict-form error (field-targeted, same as validate_workspace_region)
            # — Django does NOT propagate a top-level code into dict-form
            # field errors, so the code lives on the nested "host" error.
            assert excinfo.value.error_dict["host"][0].code == "DATABRICKS_HOST_NOT_ALLOWED"

    def test_normalisation_strips_scheme_path_port_and_case(self):
        assert (
            normalise_host("HTTPS://DBC-123.Cloud.Databricks.COM:443/api/2.0")
            == "dbc-123.cloud.databricks.com"
        )
        assert normalise_host("  dbc-123.cloud.databricks.com/  ") == "dbc-123.cloud.databricks.com"


class SsrfLayerTests(TestCase):
    """SSRFGuard reuse — negative cases deterministic in both resolver configs."""

    def test_unresolvable_databricks_host_rejected_at_save(self):
        # Family-valid but bogus: DNS resolution fails (NXDOMAIN online,
        # gaierror offline) — SSRFGuard maps both to a violation.
        with pytest.raises(ValidationError) as excinfo:
            validate_workspace_host("localhost.cloud.databricks.com")
        assert excinfo.value.error_dict["host"][0].code == "SSRF_PROTECTION_TRIGGERED"

    def test_dispatch_revalidation_rejects_unresolvable_or_private(self):
        # dnspython re-resolution of a family-valid bogus host: NXDOMAIN or
        # a private answer — both must surface as a rebinding rejection.
        with pytest.raises(ValidationError) as excinfo:
            revalidate_workspace_host("localhost.cloud.databricks.com")
        assert excinfo.value.error_dict["host"][0].code == "SSRF_DNS_REBINDING"

    def test_positive_save_and_dispatch_against_real_host(self):
        _require_dns()
        normalised = validate_workspace_host(REAL_HOST)
        assert normalised == REAL_HOST
        revalidate_workspace_host(REAL_HOST)  # must not raise


class ResidencyTests(TestCase):
    def setUp(self):
        self.tenant = TenantFactory.create_tenant()

    def test_region_mismatch_rejected(self):
        self.tenant.data_residency_region = "eu"
        self.tenant.save(update_fields=["data_residency_region"])
        with pytest.raises(ValidationError) as excinfo:
            validate_workspace_region(self.tenant, "us-east-1")
        # Dict-form error (field-targeted, same as WarehouseConnection) —
        # the code lives on the nested field error.
        assert excinfo.value.error_dict["region"][0].code == "DATA_RESIDENCY_MISMATCH"

    def test_matching_region_accepted(self):
        self.tenant.data_residency_region = "eu"
        self.tenant.save(update_fields=["data_residency_region"])
        validate_workspace_region(self.tenant, "eu-central-1")  # DE ∈ EU allowlist

    def test_unknown_region_skipped(self):
        self.tenant.data_residency_region = "eu"
        self.tenant.save(update_fields=["data_residency_region"])
        validate_workspace_region(self.tenant, "not-a-known-region")

    def test_tenant_without_residency_skipped(self):
        validate_workspace_region(self.tenant, "us-east-1")


class ModelIntegrationTests(TestCase):
    def setUp(self):
        self.tenant = TenantFactory.create_tenant()

    def _workspace(self, host, **kwargs):
        kwargs.setdefault("cloud", DatabricksCloud.AWS)
        kwargs.setdefault("region", "us-east-1")
        return DatabricksWorkspace(tenant=self.tenant, name="ws", host=host, **kwargs)

    def test_save_rejects_bad_family(self):
        with pytest.raises(ValidationError) as excinfo:
            self._workspace("evil.example.com").save()
        assert excinfo.value.error_dict["host"][0].code == "DATABRICKS_HOST_NOT_ALLOWED"

    def test_save_rejects_bogus_databricks_host(self):
        with pytest.raises(ValidationError) as excinfo:
            self._workspace("localhost.cloud.databricks.com").save()
        assert excinfo.value.error_dict["host"][0].code == "SSRF_PROTECTION_TRIGGERED"

    def test_save_rejects_residency_mismatch(self):
        _require_dns()
        self.tenant.data_residency_region = "eu"
        self.tenant.save(update_fields=["data_residency_region"])
        with pytest.raises(ValidationError) as excinfo:
            self._workspace(REAL_HOST, region="us-east-1").save()
        assert excinfo.value.error_dict["region"][0].code == "DATA_RESIDENCY_MISMATCH"

    def test_save_persists_normalised_host(self):
        _require_dns()
        ws = self._workspace("https://" + REAL_HOST + "/")
        ws.save()
        ws.refresh_from_db()
        assert ws.host == REAL_HOST

    def test_validate_for_dispatch_routes_through_revalidation(self):
        ws = self._workspace("localhost.cloud.databricks.com")
        with pytest.raises(ValidationError) as excinfo:
            ws.validate_for_dispatch()
        assert excinfo.value.error_dict["host"][0].code == "SSRF_DNS_REBINDING"
