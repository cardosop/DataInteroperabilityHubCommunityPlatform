"""
Phase 260.3.E — sample endpoint PII redaction and VIEW_PII include_pii.

TDD coverage for tenant.redact_sample_pii_in_ui, GET .../sample/ metadata flags,
and permission-based unredaction (no mocks of Django ORM or auth backends).
"""

import pytest

from hub.apps.datasets.tests.test_base import DatasetsAPITestBase
from hub.apps.datasets.sample_pii_redaction import (
    SAMPLE_PII_REPLACEMENT,
    redact_sample_cell,
    redact_sample_rows,
)
from hub.apps.users.models import Role, UserRole
from rest_framework import status


pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.integration
def test_redact_sample_cell_email_and_plain_name():
    assert redact_sample_cell("email", "x@y.co") == SAMPLE_PII_REPLACEMENT
    assert redact_sample_cell("name", "Jane") == "Jane"


@pytest.mark.integration
def test_redact_sample_rows_preserves_non_strings():
    rows = [{"a": 1, "email": "a@b.co"}]
    out = redact_sample_rows(rows)
    assert out[0]["a"] == 1
    assert out[0]["email"] == SAMPLE_PII_REPLACEMENT


@pytest.mark.parametrize(
    "value",
    [
        "user@example.com",
        "  user@example.com  ",
        "first.last+tag@sub.example.co.uk",
    ],
)
@pytest.mark.integration
def test_redact_sample_cell_email_pattern_matches_in_neutral_column(value):
    """Email regex catches PII even when the column name isn't a hint."""
    assert redact_sample_cell("free_text", value) == SAMPLE_PII_REPLACEMENT


@pytest.mark.parametrize(
    "value",
    [
        "555-555-1234",
        "555.555.1234",
        "+15555551234",
        "5555551234567",
    ],
)
@pytest.mark.integration
def test_redact_sample_cell_phone_pattern_matches(value):
    assert redact_sample_cell("contact", value) == SAMPLE_PII_REPLACEMENT


@pytest.mark.parametrize(
    "value",
    [
        "4111-1111-1111-1111",
        "4111 1111 1111 1111",
        "4111111111111111",
    ],
)
@pytest.mark.integration
def test_redact_sample_cell_card_pattern_matches(value):
    assert redact_sample_cell("payment_pan", value) == SAMPLE_PII_REPLACEMENT


@pytest.mark.integration
def test_redact_sample_cell_ssn_pattern_matches():
    assert redact_sample_cell("notes", "123-45-6789") == SAMPLE_PII_REPLACEMENT


@pytest.mark.parametrize(
    "field_name",
    [
        "ssn",
        "social_security",
        "credit_card",
        "creditcard",
        "pan",
        "national_id",
        "passport",
        "drivers_license",
        "iban",
        "password",
        "password_hash",
        "api_key",
        "token",
        "secret",
        # Case variations + nested-like substring matches
        "SSN",
        "user_ssn_last4",
        "SecretKey",
    ],
)
@pytest.mark.integration
def test_redact_sample_cell_column_name_hint_redacts_strings(field_name):
    assert redact_sample_cell(field_name, "anything") == SAMPLE_PII_REPLACEMENT


@pytest.mark.parametrize(
    "value",
    [
        123456789,                # int
        123456789.0,              # float
        True,                     # bool
        ["123-45-6789"],          # list
        {"nested": "123-45-6789"},
    ],
)
@pytest.mark.integration
def test_redact_sample_cell_column_name_hint_redacts_non_strings(value):
    """Root-cause fix: column-name hint must redact regardless of value type.

    Before this fix, ``{"ssn": 123456789}`` leaked because the helper
    only entered the redaction branch for string values.
    """
    assert redact_sample_cell("ssn", value) == SAMPLE_PII_REPLACEMENT


@pytest.mark.integration
def test_redact_sample_cell_passes_through_safe_values():
    assert redact_sample_cell("count", 42) == 42
    assert redact_sample_cell("count", None) is None
    assert redact_sample_cell("description", "hello world") == "hello world"


@pytest.mark.integration
def test_redact_sample_cell_uuid_does_not_match_phone_regex():
    """UUIDs were previously matched by the phone regex via run-on digit groups; explicit guard."""
    uuid_str = "11111111-2222-3333-4444-555555555555"
    assert redact_sample_cell("entity_id", uuid_str) == uuid_str


@pytest.mark.integration
def test_redact_sample_rows_redacts_int_typed_sensitive_columns():
    """End-to-end row pass redacts integer-typed sensitive columns."""
    rows = [{"id": 1, "ssn": 987654321, "name": "Bob"}]
    out = redact_sample_rows(rows)
    assert out[0]["id"] == 1  # neutral non-string value preserved
    assert out[0]["ssn"] == SAMPLE_PII_REPLACEMENT
    assert out[0]["name"] == "Bob"


@pytest.mark.integration
def test_redact_sample_rows_skips_non_dict_rows():
    rows = [{"email": "a@b.co"}, "not-a-dict", None, ["a", "b"]]
    out = redact_sample_rows(rows)
    assert len(out) == 1
    assert out[0]["email"] == SAMPLE_PII_REPLACEMENT


@pytest.mark.integration
def test_redact_sample_rows_does_not_mutate_input():
    rows = [{"email": "a@b.co", "tags": ["x"]}]
    out = redact_sample_rows(rows)
    # Input is unchanged (deep copy + reassignment in helper).
    assert rows[0]["email"] == "a@b.co"
    assert rows[0]["tags"] == ["x"]
    assert out[0]["email"] == SAMPLE_PII_REPLACEMENT


class TenantRedactSamplePIIDefaultTest(DatasetsAPITestBase):
    """Pin Phase 260.3.E.1 ``Tenant.save()`` default — VERIFIED tenants ON, others OFF."""

    @pytest.mark.integration
    def test_create_tenant_verified_defaults_redact_to_true(self):
        from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus

        tenant = Tenant.objects.create(
            name="verified-defaults-test",
            slug="verified-defaults-test",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        try:
            self.assertTrue(tenant.redact_sample_pii_in_ui)
        finally:
            tenant.delete()

    @pytest.mark.integration
    def test_create_tenant_unverified_defaults_redact_to_false(self):
        from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus

        tenant = Tenant.objects.create(
            name="unverified-defaults-test",
            slug="unverified-defaults-test",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.UNVERIFIED,
        )
        try:
            self.assertFalse(tenant.redact_sample_pii_in_ui)
        finally:
            tenant.delete()

    @pytest.mark.integration
    def test_save_after_create_does_not_overwrite_explicit_false(self):
        """The save-on-create stamp runs only on insert; later edits are honoured."""
        from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus

        tenant = Tenant.objects.create(
            name="post-create-edit-test",
            slug="post-create-edit-test",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        try:
            self.assertTrue(tenant.redact_sample_pii_in_ui)
            tenant.redact_sample_pii_in_ui = False
            tenant.save(update_fields=["redact_sample_pii_in_ui", "updated_at"])
            tenant.refresh_from_db()
            self.assertFalse(tenant.redact_sample_pii_in_ui)
        finally:
            tenant.delete()


class SamplePIIRedactionAPITest(DatasetsAPITestBase):
    def setUp(self):
        super().setUp()
        self.sample_data = [
            {"id": 1, "name": "Alice", "email": "alice@example.com"},
        ]
        from hub.apps.datasets.models import Dataset

        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            file=self.file,
            format="CSV",
            schema_json={"fields": []},
            sample_data_json=self.sample_data,
            row_count=1,
            created_by=self.user,
        )

    @pytest.mark.integration
    def test_tenant_flag_off_returns_raw_and_no_redaction(self):
        self.tenant.redact_sample_pii_in_ui = False
        self.tenant.save(update_fields=["redact_sample_pii_in_ui", "updated_at"])
        url = f"/api/v1/datasets/{self.dataset.id}/sample/"
        data = self.client.get(url).json()
        self.assertEqual(data["sample_data"][0]["email"], "alice@example.com")
        self.assertFalse(data["tenant_redacts_sample_pii"])
        self.assertFalse(data["sample_pii_redaction_applied"])

    @pytest.mark.integration
    def test_include_pii_without_role_is_ignored(self):
        self.tenant.redact_sample_pii_in_ui = True
        self.tenant.save(update_fields=["redact_sample_pii_in_ui", "updated_at"])
        url = f"/api/v1/datasets/{self.dataset.id}/sample/?include_pii=true"
        data = self.client.get(url).json()
        self.assertFalse(data["viewer_may_include_pii"])
        self.assertFalse(data["include_pii_effective"])
        self.assertEqual(data["sample_data"][0]["email"], SAMPLE_PII_REPLACEMENT)

    @pytest.mark.integration
    def test_include_pii_true_with_pii_viewer_unredacts(self):
        self.tenant.redact_sample_pii_in_ui = True
        self.tenant.save(update_fields=["redact_sample_pii_in_ui", "updated_at"])

        role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="PII_VIEWER",
            defaults={
                "description": "Test PII viewer",
            },
        )
        UserRole.objects.create(user=self.user, tenant=self.tenant, role=role)

        url = f"/api/v1/datasets/{self.dataset.id}/sample/?include_pii=true"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertTrue(data["viewer_may_include_pii"])
        self.assertTrue(data["include_pii_effective"])
        self.assertFalse(data["sample_pii_redaction_applied"])
        self.assertEqual(data["sample_data"][0]["email"], "alice@example.com")
