"""U.6 — invite_beta_cohort management command tests.

Real-service tests (no mocks): the command must go through
UserService.invite_user_to_tenant, set a hashed 7-day invitation token,
enqueue the invitation email, and stay idempotent across re-runs.
"""

import csv
import uuid
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from hub.apps.tenants.models import Tenant
from hub.apps.users.models import Role, User, UserStatus

pytestmark = pytest.mark.django_db


def _write_csv(tmp_path, rows):
    path = tmp_path / "cohort.csv"
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=["tenant_slug", "email", "display_name", "role_names"]
        )
        writer.writeheader()
        writer.writerows(rows)
    return str(path)


class TestInviteBetaCohortCommand:
    @pytest.fixture(autouse=True)
    def _setup(self):
        uid = str(uuid.uuid4())[:8]
        self.email = f"beta-{uuid.uuid4().hex[:8]}@example.com"
        self.tenant = Tenant.objects.create(name=f"Beta Tenant {uid}", slug=f"beta-tenant-{uid}")
        self.actor = User.objects.create_user(
            email=f"beta-admin-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            display_name="Beta Admin",
            status=UserStatus.ACTIVE,
        )
        self.admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant, name="TENANT_ADMIN", defaults={"description": "Tenant Admin"}
        )
        self.provider_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="DATA_PROVIDER",
            defaults={"description": "Data Provider"},
        )

    def _run(self, tmp_path, rows, **kwargs):
        out, err = StringIO(), StringIO()
        path = _write_csv(tmp_path, rows)
        call_command(
            "invite_beta_cohort",
            "--csv",
            path,
            stdout=out,
            stderr=err,
            **kwargs,
        )
        return out.getvalue(), err.getvalue()

    def test_invites_new_users_with_roles_and_hashed_token(self, tmp_path):
        out, _ = self._run(
            tmp_path,
            [
                {
                    "tenant_slug": self.tenant.slug,
                    "email": self.email,
                    "display_name": "Beta One",
                    "role_names": "TENANT_ADMIN,DATA_PROVIDER",
                },
            ],
        )
        user = User.objects.get(email=self.email, tenant=self.tenant)
        assert user.status == UserStatus.INVITED
        assert user.invitation_token is not None
        # Token at rest is a SHA-256 hex digest (11.3), not the plaintext UUID.
        assert len(user.invitation_token) == 64
        assert user.invitation_token_expires_at is not None
        role_names = set(user.user_roles.values_list("role__name", flat=True))
        assert role_names == {"TENANT_ADMIN", "DATA_PROVIDER"}
        assert "created=1" in out
        assert self.email in out

    def test_rerun_is_idempotent(self, tmp_path):
        rows = [
            {
                "tenant_slug": self.tenant.slug,
                "email": self.email,
                "display_name": "Beta One",
                "role_names": "",
            },
        ]
        self._run(tmp_path, rows)
        out2, _ = self._run(tmp_path, rows)
        assert User.objects.filter(email=self.email, tenant=self.tenant).count() == 1
        assert "skipped=1" in out2

    def test_dry_run_writes_nothing(self, tmp_path):
        out, _ = self._run(
            tmp_path,
            [
                {
                    "tenant_slug": self.tenant.slug,
                    "email": self.email,
                    "display_name": "Beta One",
                    "role_names": "",
                },
            ],
            dry_run=True,
        )
        assert not User.objects.filter(email=self.email, tenant=self.tenant).exists()
        assert "[DRY-RUN]" in out

    def test_unknown_tenant_fails_row_and_exits_nonzero(self, tmp_path):
        with pytest.raises(CommandError):
            self._run(
                tmp_path,
                [
                    {
                        "tenant_slug": "no-such-tenant",
                        "email": self.email,
                        "display_name": "",
                        "role_names": "",
                    },
                ],
            )
        assert not User.objects.filter(email=self.email).exists()

    def test_unknown_role_names_reported_but_invite_proceeds(self, tmp_path):
        out, _ = self._run(
            tmp_path,
            [
                {
                    "tenant_slug": self.tenant.slug,
                    "email": self.email,
                    "display_name": "Beta One",
                    "role_names": "NOPE_ROLE",
                },
            ],
        )
        assert "NOPE_ROLE" in out
        assert User.objects.filter(email=self.email).exists()

    def test_missing_columns_rejected(self, tmp_path):
        path = tmp_path / "bad.csv"
        path.write_text("tenant_slug,email\nx,y\n")
        with pytest.raises(CommandError):
            call_command("invite_beta_cohort", "--csv", str(path), stdout=StringIO())
