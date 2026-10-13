"""P0 (openspec add-databricks-control-plane task 0.3) — DatabricksCredential model + RLS.

No mocks: the model tests run against the real Postgres test database with
the REAL encryption chain (Fernet via ENCRYPTION_KEY — the KMS fallback is
a supported production path); the at-rest assertions read the raw column
through a SQL cursor so no ORM masking can hide plaintext. The RLS coverage
tests scan the migration files — same 285.14.3.8 pattern as
``hub/apps/billing/tests/test_rls_policies.py``, extended for the
INDIRECT-FK policy shape (subquery through ``databricks_workspaces``).

NOTE on behavioral RLS asserts: the test role OWNS the tables, and Postgres
row-level security does not apply to the table owner unless FORCE ROW LEVEL
SECURITY is set (no repo table uses FORCE) — a cross-tenant "invisible"
assert through the ORM would prove nothing. The repo's enforcement stack is
the pairing lint + these coverage scans + the runtime app role separation.
"""

import json
import os
import re

import pytest
from django.core.exceptions import ValidationError
from django.db import connection
from django.test import TestCase

from hub.apps.databricks_admin.models import (
    DatabricksCloud,
    DatabricksCredential,
    DatabricksCredentialAuthMode,
    DatabricksWorkspace,
)
from hub.apps.databricks_admin.tests._fixtures import REAL_HOST, require_dns
from tests.factories import TenantFactory

pytestmark = pytest.mark.django_db(transaction=True)

_RAW_CONFIG = {"token": "dapi-secret-value-123", "comment": "test credential"}


class DatabricksCredentialModelTests(TestCase):
    def setUp(self):
        require_dns()
        self.tenant = TenantFactory.create_tenant()
        self.workspace = DatabricksWorkspace.objects.create(
            tenant=self.tenant,
            name="prod",
            host=REAL_HOST,
            cloud=DatabricksCloud.AWS,
            region="us-east-1",
        )

    def _create(self, **kwargs):
        kwargs.setdefault("workspace", self.workspace)
        kwargs.setdefault("auth_mode", DatabricksCredentialAuthMode.PAT)
        kwargs.setdefault("config", dict(_RAW_CONFIG))
        return DatabricksCredential.objects.create(**kwargs)

    def _raw_config_column(self, credential) -> str:
        """Read the raw `config` column straight from Postgres (no ORM layer)."""
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT config FROM databricks_credentials WHERE id = %s",
                [credential.id],
            )
            row = cursor.fetchone()
        assert row is not None
        return row[0]

    def test_raw_config_is_encrypted_at_rest(self):
        credential = self._create()
        raw = self._raw_config_column(credential)

        # psycopg2 returns the jsonb column as a parsed dict; either way the
        # wrapper shape must hold and the plaintext must be absent.
        if isinstance(raw, str):
            raw = json.loads(raw)
        assert "_encrypted" in raw, (
            "config must use the MarketplaceConnection encrypted-wrapper shape"
        )
        assert "dapi-secret-value-123" not in json.dumps(raw), (
            "plaintext token leaked into the stored column"
        )

    def test_get_config_round_trips_through_the_real_encryption_chain(self):
        credential = self._create()
        assert credential.get_config() == _RAW_CONFIG

    def test_set_config_rewrites_ciphertext(self):
        credential = self._create()
        first = self._raw_config_column(credential)

        credential.set_config({"token": "dapi-rotated-value-456"})
        credential.save(update_fields=["config"])

        second = self._raw_config_column(credential)
        assert first != second, "re-encryption must produce a fresh ciphertext"
        second_text = second if isinstance(second, str) else json.dumps(second)
        assert "dapi-rotated-value-456" not in second_text, "plaintext leaked on re-encryption"
        assert credential.get_config() == {"token": "dapi-rotated-value-456"}

    def test_auth_mode_choices_constrained(self):
        credential = DatabricksCredential(
            workspace=self.workspace,
            auth_mode="PASSWORD",
            config=dict(_RAW_CONFIG),
        )
        with pytest.raises(ValidationError):
            credential.full_clean()

    def test_expiry_and_rotation_fields_optional(self):
        credential = self._create()
        assert credential.expires_at is None
        assert credential.last_rotated_at is None

    def test_str_representation(self):
        credential = self._create()
        assert str(credential) == (
            f"DatabricksCredential {self.workspace.name} ({DatabricksCredentialAuthMode.PAT})"
        )

    def test_cascade_delete_with_workspace(self):
        credential = self._create()
        credential_id = credential.id
        self.workspace.delete()
        assert not DatabricksCredential.objects.filter(id=credential_id).exists()

    def test_encrypted_config_never_goes_through_full_clean_as_plaintext(self):
        # full_clean must not choke on the encrypted wrapper shape (a str
        # config is already-encrypted input, same guard as WarehouseConnection).
        credential = self._create()
        credential.full_clean()


class DatabricksCredentialRLSPolicyTests(TestCase):
    def setUp(self):
        import hub.apps.databricks_admin

        app_dir = os.path.dirname(hub.apps.databricks_admin.__file__)
        mig_dir = os.path.join(app_dir, "migrations")
        texts = []
        for fname in sorted(os.listdir(mig_dir)):
            if not fname.endswith(".py") or fname.startswith("_"):
                continue
            with open(os.path.join(mig_dir, fname), encoding="utf-8") as fh:
                texts.append(fh.read())
        self.migration_text = "\n".join(texts)

    def test_rls_policy_created_for_databricks_credentials(self):
        assert re.search(
            r"CREATE\s+POLICY\s+\S+\s+ON\s+databricks_credentials",
            self.migration_text,
            re.IGNORECASE,
        ), "databricks_credentials must ship a paired RLS policy (CLAUDE.md contract)"

    def test_policy_is_indirect_fk_through_workspaces(self):
        # Indirect-FK template: the child table has NO tenant_id column —
        # the policy must resolve the tenant through the workspace parent.
        # Whitespace-normalised so the check is robust to SQL line breaks.
        normalized = re.sub(r"\s+", " ", self.migration_text)
        assert "workspace_id IN ( SELECT id FROM databricks_workspaces" in normalized, (
            "indirect-FK policy must subquery databricks_workspaces for the tenant chain"
        )
        assert "app.current_tenant_id" in self.migration_text

    def test_rls_kill_switch_present(self):
        assert "current_setting('app.rls_databricks_credentials_enabled'" in self.migration_text

    def test_reverse_sql_drops_policy_and_disables_rls(self):
        assert (
            "DROP POLICY IF EXISTS tenant_isolation ON databricks_credentials"
            in self.migration_text
        )
        assert (
            "ALTER TABLE databricks_credentials DISABLE ROW LEVEL SECURITY" in self.migration_text
        )


class DatabricksCredentialConfigShapeTests(TestCase):
    """0.9 review — non-dict config must never bypass encryption at rest."""

    def setUp(self):
        require_dns()
        self.tenant = TenantFactory.create_tenant()
        self.workspace = DatabricksWorkspace.objects.create(
            tenant=self.tenant,
            name="shape-guard",
            host=REAL_HOST,
            cloud=DatabricksCloud.AWS,
            region="us-east-1",
        )

    def test_save_rejects_non_dict_config(self):
        # A bare string would be stored in PLAINTEXT by the wrapper-shape
        # branch (dicts are encrypted; everything else fell through). The
        # model must refuse — defense in depth for non-API writers.
        credential = DatabricksCredential(
            workspace=self.workspace,
            auth_mode=DatabricksCredentialAuthMode.PAT,
            config="dapi-plaintext-string",
        )
        with pytest.raises(ValidationError):
            credential.save()
        assert not DatabricksCredential.objects.filter(workspace=self.workspace).exists()

    def test_save_accepts_arbitrary_dict_shape(self):
        # The model does NOT police auth-mode key sets (that is API-boundary
        # policy in the serializer) — any dict is encrypted.
        credential = DatabricksCredential.objects.create(
            workspace=self.workspace,
            auth_mode=DatabricksCredentialAuthMode.PAT,
            config={"token": "dapi-ok"},
        )
        raw = json.dumps(credential.config)
        assert "_encrypted" in raw
        assert "dapi-ok" not in raw
