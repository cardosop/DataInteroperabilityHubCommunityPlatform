"""285.14.3.9 — Verify RLS policy coverage for notifications app."""
import pytest
import os
import re

from django.test import TestCase

pytestmark = pytest.mark.django_db(transaction=True)

_NOTIF_MODELS = {
    "email_deliveries": "EmailDelivery",
    "user_notifications": "UserNotification",
}


def _migration_texts(app_dir):
    mig_dir = os.path.join(app_dir, "migrations")
    texts = {}
    if not os.path.isdir(mig_dir):
        return texts
    for fname in sorted(os.listdir(mig_dir)):
        if fname.startswith("_") or not fname.endswith(".py"):
            continue
        with open(os.path.join(mig_dir, fname), encoding="utf-8", errors="ignore") as f:
            texts[fname] = f.read()
    return texts


class NotificationsRLSPolicyTests(TestCase):
    def setUp(self):
        import hub.apps.notifications
        app_dir = os.path.dirname(hub.apps.notifications.__file__)
        self.migrations = _migration_texts(app_dir)

    @pytest.mark.integration
    def test_all_tenant_scoped_models_have_rls(self):
        all_content = "\n".join(self.migrations.values())
        missing = []
        for table, model_name in _NOTIF_MODELS.items():
            if not re.search(
                rf"CREATE\s+POLICY\s+\S+\s+ON\s+{table}",
                all_content, re.IGNORECASE,
            ):
                missing.append(f"{model_name} ({table})")
        assert not missing, (
            f"Notification models missing RLS policies: {missing}"
        )

    @pytest.mark.integration
    def test_known_covered_tables(self):
        all_content = "\n".join(self.migrations.values())
        assert re.search(
            r"CREATE\s+POLICY\s+\S+\s+ON\s+email_deliveries",
            all_content, re.IGNORECASE,
        ), "email_deliveries RLS policy not found"
        assert re.search(
            r"CREATE\s+POLICY\s+\S+\s+ON\s+user_notifications",
            all_content, re.IGNORECASE,
        ), "user_notifications RLS policy not found"

    @pytest.mark.integration
    def test_rls_kill_switch_present(self):
        all_content = "\n".join(self.migrations.values())
        assert "current_setting('app.rls_" in all_content
        assert "app.current_tenant_id" in all_content
