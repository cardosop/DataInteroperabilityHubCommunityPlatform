"""P8 (openspec add-databricks-account-plane task 8.2) — `DatabricksAccount`
PLATFORM model: NO tenant FK, NO RLS, admin-DB-only access.

No mocks: the model pins run against the real Postgres test database with
the REAL encryption chain (Fernet via ENCRYPTION_KEY); the at-rest
assertions read the raw column through a SQL cursor so no ORM masking can
hide plaintext (the test_credentials.py convention). The admin-DB
confinement is pinned on three legs:

1. THE MANAGER — ``DatabricksAccount.objects`` is an ``AdminDatabaseManager``
   whose every queryset carries ``_db="admin"`` (the CLAUDE.md
   management-command convention extended to the model surface: a
   tenant-scoped request can never reach the table through the default
   alias without an EXPLICIT ``.using()`` escape hatch).
2. THE EXEMPTION — the model docstring AND the CreateModel migration
   docstring document the no-RLS exemption (design D1: documented, not
   accidental); no migration ever creates a policy on the table.
3. THE RUNTIME PROBE — the 1.12 ``SET ROLE`` pre-flight convention: the
   table is deliberately NOT tenant-filtered (the exemption proven at
   runtime, the read surface unscoped by design — the boundary is the
   admin alias + the platform-admin RBAC gate, never RLS).
The suites use ``TransactionTestCase`` deliberately: a plain ``TestCase``
wraps EVERY alias in test atomics, so admin-alias writes stay uncommitted
and invisible to default-alias reads (and FK checks against default-committed
rows fail) — the cross-alias pins need the two committed connections the
production role split actually has (meshant_admin ↔ app role, one physical
DB). pytest-django ignores the ``transaction=True`` marker for
Django-unittest classes, so the base class is the only honest lever.
"""

import os
import uuid

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection
from django.test import TransactionTestCase

from hub.apps.databricks_admin.models import AdminDatabaseManager, DatabricksAccount
from hub.apps.databricks_admin.tests.test_uc_rls_isolation import (
    _RLS_PROBE_ROLE,
    _connection_bypasses_rls,
    _ensure_rls_probe_role,
)
from tests.factories import TenantFactory

pytestmark = pytest.mark.django_db(transaction=True)

_RAW_CONFIG = {"client_id": "acct-admin-app", "client_secret": "dose-account-secret-123"}
_ACCOUNT_TABLE = "databricks_accounts"


def _create_account(account_id=None, **kwargs):
    """Create a DatabricksAccount row through the default manager (which
    forces the admin alias — the only sanctioned ORM path)."""
    kwargs.setdefault("account_id", account_id or uuid.uuid4())
    kwargs.setdefault("display_name", f"acct-{uuid.uuid4().hex[:8]}")
    kwargs.setdefault("config", dict(_RAW_CONFIG))
    return DatabricksAccount.objects.create(**kwargs)


class DatabricksAccountPlatformShapeTests(TransactionTestCase):
    """The PLATFORM shape: no tenant FK anywhere, unique account link key."""

    def test_model_has_no_tenant_field(self):
        field_names = {f.name for f in DatabricksAccount._meta.fields}
        assert "tenant" not in field_names
        assert "tenant_id" not in field_names

    def test_no_field_relations_to_the_tenant_model(self):
        from hub.apps.tenants.models import Tenant

        for field in DatabricksAccount._meta.fields:
            assert not (field.is_relation and field.related_model is Tenant), (
                f"{field.name} relates to Tenant — the platform table must not"
            )

    def test_account_id_is_unique_and_the_link_key(self):
        first = _create_account()
        assert first.id is not None
        assert first.created_at is not None
        assert first.updated_at is not None
        with pytest.raises(IntegrityError):
            _create_account(account_id=first.account_id, display_name="duplicate-account")

    def test_db_table_and_app_label(self):
        assert DatabricksAccount._meta.db_table == _ACCOUNT_TABLE
        assert DatabricksAccount._meta.app_label == "databricks_admin"

    def test_str_representation(self):
        account = _create_account(display_name="meshant-prod-account")
        assert str(account) == (f"DatabricksAccount meshant-prod-account ({account.account_id})")


class DatabricksAccountRlsExemptionTests(TransactionTestCase):
    """The exemption is deliberate and documented — design D1/D8."""

    def setUp(self):
        self.tenant_a = TenantFactory.create_tenant()
        self.tenant_b = TenantFactory.create_tenant()
        self.account = _create_account()

    def _migration_files(self):
        import hub.apps.databricks_admin

        mig_dir = os.path.join(os.path.dirname(hub.apps.databricks_admin.__file__), "migrations")
        texts = {}
        for fname in sorted(os.listdir(mig_dir)):
            if fname.endswith(".py") and not fname.startswith("_"):
                with open(os.path.join(mig_dir, fname), encoding="utf-8") as fh:
                    texts[fname] = fh.read()
        return texts

    def test_no_rls_policy_exists_on_the_account_table(self):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT policyname FROM pg_policies WHERE tablename = %s",
                [_ACCOUNT_TABLE],
            )
            assert cursor.fetchall() == [], (
                "pg_policies must carry ZERO rows for the platform table"
            )

    def test_rls_is_not_enabled_on_the_account_table(self):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT relrowsecurity FROM pg_class WHERE relname = %s",
                [_ACCOUNT_TABLE],
            )
            row = cursor.fetchone()
        assert row is not None, "databricks_accounts table missing (migration not applied?)"
        assert row[0] is False, "the platform table must NOT have row-level security enabled"

    def test_no_migration_creates_a_policy_or_enables_rls_on_the_account_table(self):
        for fname, text in self._migration_files().items():
            mentions_table = "databricks_accounts" in text
            assert not (mentions_table and "CREATE POLICY" in text), fname
            assert not (mentions_table and "ENABLE ROW LEVEL SECURITY" in text), fname

    def test_the_account_migration_documents_the_no_rls_exemption(self):
        # The CreateModel migration for the table must carry the documented
        # exemption (design D1: documented on the migration, not accidental).
        for fname, text in self._migration_files().items():
            if "CreateModel" not in text or "databricks_accounts" not in text:
                continue
            doc = text.split('"""', 2)[1]
            assert "PLATFORM" in doc, fname
            assert "RLS" in doc, fname
            assert "admin" in doc, fname
            assert "exempt" in doc.lower(), fname
            return
        pytest.fail("no CreateModel migration for databricks_accounts found")

    def test_model_docstring_documents_the_no_rls_exemption(self):
        doc = DatabricksAccount.__doc__ or ""
        assert "PLATFORM" in doc
        assert "RLS" in doc
        assert "admin" in doc
        assert "tenant" in doc.lower()

    def _probe_role(self):
        if _connection_bypasses_rls():
            _ensure_rls_probe_role()
            with connection.cursor() as cursor:
                cursor.execute(f"GRANT SELECT ON {_ACCOUNT_TABLE} TO {_RLS_PROBE_ROLE}")
            return _RLS_PROBE_ROLE
        return None

    def _row_visible_count_as(self, role_or_none, tenant_id, row_id):
        """Count THIS row's visibility under *tenant_id*'s tenant GUC (the
        SET ROLE probe convention). Residue-proof: a suppressed flush on a
        shared/clone DB can leave OTHER rows behind — the exemption pin is
        about this row's visibility under foreign tenant contexts, never a
        global table count."""
        with connection.cursor() as cursor:
            try:
                if role_or_none:
                    cursor.execute(f"SET ROLE {role_or_none}")
                cursor.execute(
                    "SELECT set_config('app.current_tenant_id', %s, true)",
                    [str(tenant_id)],
                )
                cursor.execute(
                    f"SELECT count(*) FROM {_ACCOUNT_TABLE} WHERE id = %s",
                    [row_id],
                )
                count = cursor.fetchone()[0]
                cursor.execute("SELECT set_config('app.current_tenant_id', NULL, true)")
                return count
            finally:
                if role_or_none:
                    cursor.execute("RESET ROLE")

    def test_account_rows_are_deliberately_not_tenant_filtered(self):
        # The runtime pre-flight probe: the exemption is REAL — no policy
        # filters the table, so the row stays visible under ANY tenant GUC
        # (and under none). The boundary is the admin alias + RBAC, not RLS.
        probe = self._probe_role()
        row_id = self.account.id
        assert self._row_visible_count_as(probe, self.tenant_a.id, row_id) == 1
        assert self._row_visible_count_as(probe, self.tenant_b.id, row_id) == 1, (
            "a FOREIGN tenant GUC must not filter the platform table — "
            "the no-RLS exemption is the documented design (D1)"
        )
        assert self._row_visible_count_as(probe, None, row_id) == 1, (
            "an unset tenant GUC must not hide the platform row either"
        )


class DatabricksAccountCredentialEncryptionTests(TransactionTestCase):
    """The account-level admin credential is encrypted at rest (D1/D3)."""

    def _raw_config_column(self, account):
        """Read the raw `config` column straight from Postgres (no ORM layer)."""
        import json

        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT config FROM {_ACCOUNT_TABLE} WHERE id = %s",
                [account.id],
            )
            row = cursor.fetchone()
        assert row is not None
        raw = row[0]
        return json.loads(raw) if isinstance(raw, str) else raw

    def test_raw_config_is_encrypted_at_rest(self):
        account = _create_account()
        raw = self._raw_config_column(account)
        assert "_encrypted" in raw, "config must use the Fernet encrypted-wrapper shape"
        assert "dose-account-secret-123" not in str(raw), (
            "plaintext account credential leaked into the stored column"
        )

    def test_get_config_round_trips_through_the_real_encryption_chain(self):
        account = _create_account()
        assert account.get_config() == _RAW_CONFIG

    def test_set_config_rewrites_ciphertext(self):
        account = _create_account()
        account.set_config({"client_id": "rotated-app", "client_secret": "rotated-secret"})
        account.save()
        reloaded = DatabricksAccount.objects.get(pk=account.pk)
        assert reloaded.get_config() == {
            "client_id": "rotated-app",
            "client_secret": "rotated-secret",
        }
        raw = self._raw_config_column(reloaded)
        assert "rotated-secret" not in str(raw)

    def test_non_dict_config_is_rejected(self):
        with pytest.raises(ValidationError) as excinfo:
            _create_account(config="a bare string would bypass encryption")
        assert excinfo.value.code == "invalid_credential_config_shape"


class DatabricksAccountAdminDatabaseTests(TransactionTestCase):
    """The manager pins every query to DATABASES['admin'] (BYPASSRLS)."""

    def test_objects_is_the_forced_alias_manager(self):
        assert isinstance(DatabricksAccount.objects, AdminDatabaseManager)

    def test_every_queryset_carries_the_admin_alias(self):
        account = _create_account()
        assert DatabricksAccount.objects.all().db == "admin"
        assert DatabricksAccount.objects.filter(pk=account.pk).db == "admin"
        assert DatabricksAccount.objects.filter(pk=account.pk).exclude(pk=None).db == "admin"
        assert DatabricksAccount.objects.order_by("created_at").db == "admin"
        assert DatabricksAccount.objects.values("account_id").db == "admin"

    def test_create_and_read_round_trip_through_the_manager(self):
        account = _create_account(display_name="round-trip-account")
        fetched = DatabricksAccount.objects.get(pk=account.pk)
        assert fetched.display_name == "round-trip-account"
        assert str(fetched.account_id) == str(account.account_id)
        assert DatabricksAccount.objects.filter(account_id=account.account_id).count() == 1

    def test_get_or_create_writes_through_the_admin_alias(self):
        account_id = uuid.uuid4()
        created, was_created = DatabricksAccount.objects.get_or_create(
            account_id=account_id,
            defaults={"display_name": "get-or-create", "config": dict(_RAW_CONFIG)},
        )
        assert was_created is True
        again, was_created_again = DatabricksAccount.objects.get_or_create(
            account_id=account_id,
            defaults={"display_name": "get-or-create", "config": dict(_RAW_CONFIG)},
        )
        assert was_created_again is False
        assert again.pk == created.pk

    def test_the_default_alias_needs_an_explicit_escape_hatch(self):
        # The manager NEVER hands out a default-alias queryset; reaching the
        # tenant alias requires an EXPLICIT .using() — the sanctioned path is
        # admin-only, and this documents where the boundary sits.
        assert DatabricksAccount.objects.all().db != "default"
        assert DatabricksAccount.objects.all().using("default").db == "default"


class DatabricksAccountSignoffTests(TransactionTestCase):
    """The DPO/Legal provisioning signoff record (design D3)."""

    def setUp(self):
        self.account = _create_account()
        self.tenant = TenantFactory.create_tenant()
        self.user = self._make_user()

    def _make_user(self):
        from hub.apps.users.models import User, UserStatus

        return User.objects.create_user(
            email=f"{uuid.uuid4().hex[:8]}-signoff@test.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

    def test_record_provisioning_signoff_sets_and_persists_all_fields(self):
        self.account.record_provisioning_signoff(self.user, "https://tickets.example.com/DPO-8817")
        reloaded = DatabricksAccount.objects.get(pk=self.account.pk)
        assert reloaded.provisioning_signoff_by_id == self.user.id
        assert reloaded.provisioning_signoff_at is not None
        assert reloaded.provisioning_signoff_evidence_url == "https://tickets.example.com/DPO-8817"

    def test_record_provisioning_signoff_rejects_a_blank_evidence_url(self):
        # Fail-closed at RECORD time: a signoff without evidence is not a
        # signoff (D3 — creating external infrastructure is a legal act).
        with pytest.raises(ValueError, match="evidence"):
            self.account.record_provisioning_signoff(self.user, "   ")
        reloaded = DatabricksAccount.objects.get(pk=self.account.pk)
        assert reloaded.provisioning_signoff_at is None

    def test_has_provisioning_signoff_requires_the_complete_record(self):
        assert self.account.has_provisioning_signoff() is False
        self.account.record_provisioning_signoff(self.user, "https://tickets.example.com/DPO-8817")
        assert self.account.has_provisioning_signoff() is True

    def test_signoff_survives_user_deletion(self):
        # SET_NULL: the attribution user may go, the LEGAL RECORD (timestamp
        # + evidence URL) must not — a deleted user cannot erase a signoff.
        self.account.record_provisioning_signoff(self.user, "https://tickets.example.com/DPO-8817")
        signed_at = self.account.provisioning_signoff_at
        self.user.delete()
        reloaded = DatabricksAccount.objects.get(pk=self.account.pk)
        assert reloaded.provisioning_signoff_by_id is None
        assert reloaded.provisioning_signoff_at == signed_at
        assert reloaded.provisioning_signoff_evidence_url == "https://tickets.example.com/DPO-8817"
        assert reloaded.has_provisioning_signoff() is False, (
            "a user-less signoff is incomplete — the 8.3 refusal gate fails closed"
        )
