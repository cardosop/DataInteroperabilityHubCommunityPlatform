from tests.pytest_mvp_skip import skip_if_mvp_mode

pytestmark = skip_if_mvp_mode

"""
End-to-end tests for BaaS API key management workflows.

Tests complete workflows for API key lifecycle management:
- Create → List → Get → Update → Revoke
- Multiple keys with different tiers
- Error scenarios and edge cases
"""
import pytest

# Phase 215.4 review fix: this module imports from django/hub which are
# not on the CLI test PYTHONPATH (CLI pytest.ini sets ``-p no:django``).
# Skip the entire module gracefully when those packages are unavailable
# instead of crashing pytest collection.
django = pytest.importorskip("django")
hub = pytest.importorskip("hub")
import json
import uuid
from datetime import timedelta

from click.testing import CliRunner
from datahub_cli.config import config
from datahub_cli.main import cli
from django.contrib.auth import get_user_model
from django.test import LiveServerTestCase
from django.utils import timezone

from hub.apps.baas.models import APIKey, APITierModel
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import Role, UserRole, UserStatus

User = get_user_model()


@pytest.mark.django_db(transaction=True)
class TestBaaSAPIKeysE2E(LiveServerTestCase):
    """
    End-to-end tests for BaaS API key management workflows.

    Tests complete user workflows from start to finish.
    """

    @classmethod
    def _fixture_teardown(cls):
        """Override to skip database flush for E2E tests.

        LiveServerTestCase tries to flush the database between tests, but this
        fails with foreign key constraints. We use manual cleanup instead.
        """
        # Don't flush - we clean up manually in tearDown

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        self.runner = CliRunner()

        # Generate unique identifiers for this test to avoid conflicts
        unique_id = uuid.uuid4().hex[:8]

        # Create tenant with unique name
        self.tenant = Tenant.objects.create(
            name=f"BaaS E2E Test Tenant {unique_id}", slug=f"baas-e2e-test-tenant-{unique_id}"
        )

        # Create user with ACTIVE status and unique email
        self.user = User.objects.create_user(
            email=f"baas-e2e-test-{unique_id}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        # Create and assign TENANT_ADMIN role (required for API key creation)
        tenant_admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant Administrator"},
        )
        UserRole.objects.create(user=self.user, role=tenant_admin_role)

        # Set API base URL to live test server
        self.api_base_url = f"{self.live_server_url}/api/v1"
        config.set_api_base_url(self.api_base_url)

        # Create API tiers
        self.free_tier, _ = APITierModel.objects.get_or_create(
            name="FREE",
            defaults={
                "rate_limit_per_hour": 1000,
                "rate_limit_per_day": 10000,
                "max_requests_per_month": 10000,
            },
        )
        self.pro_tier, _ = APITierModel.objects.get_or_create(
            name="PRO",
            defaults={
                "rate_limit_per_hour": 10000,
                "rate_limit_per_day": 100000,
                "max_requests_per_month": 100000,
            },
        )

        # Create API key for authentication
        from hub.apps.auth.models import APIKey as AuthAPIKey

        plaintext_key = AuthAPIKey.generate_key()
        key_hash = AuthAPIKey.hash_key(plaintext_key)
        AuthAPIKey.objects.create(
            user=self.user, tenant=self.tenant, name="CLI Test Key", key_hash=key_hash
        )
        config.set_api_key(plaintext_key)
        self.api_key = plaintext_key

    def tearDown(self):
        """Clean up after tests"""
        config.clear_auth()
        # Clean up test data in reverse order of dependencies
        try:
            # Delete API keys first
            APIKey.objects.filter(tenant=self.tenant).delete()
            # Delete auth API keys
            from hub.apps.auth.models import APIKey as AuthAPIKey

            AuthAPIKey.objects.filter(tenant=self.tenant).delete()
            # Delete user roles
            if hasattr(self, "user"):
                UserRole.objects.filter(user=self.user).delete()
            # Delete user
            if hasattr(self, "user"):
                User.objects.filter(id=self.user.id).delete()
            # Delete tenant
            if hasattr(self, "tenant"):
                Tenant.objects.filter(id=self.tenant.id).delete()
        except Exception:
            pass  # Ignore errors during cleanup
        # Note: super().tearDown() is skipped because _fixture_teardown is overridden
        # This prevents database flush errors with foreign key constraints

    def test_complete_api_key_lifecycle_workflow(self):
        """
        Test complete API key lifecycle: create → list → get → update → revoke
        """
        # Step 1: Create API key
        create_result = self.runner.invoke(
            cli,
            [
                "baas",
                "api-keys",
                "create",
                "--name",
                "E2E Test Key",
                "--tier",
                "FREE",
                "--format",
                "json",
            ],
        )

        assert create_result.exit_code == 0
        create_data = json.loads(create_result.output)
        api_key_id = create_data["id"]
        created_api_key_value = create_data["api_key"]
        assert created_api_key_value is not None
        assert len(created_api_key_value) > 0

        # Step 2: List API keys (should include the new key)
        list_result = self.runner.invoke(cli, ["baas", "api-keys", "list", "--format", "json"])

        assert list_result.exit_code == 0
        list_data = json.loads(list_result.output)
        assert any(key["id"] == api_key_id for key in list_data)
        found_key = next(key for key in list_data if key["id"] == api_key_id)
        assert found_key["name"] == "E2E Test Key"
        assert found_key["tier"] == "FREE"

        # Step 3: Get API key details (should NOT include key value)
        get_result = self.runner.invoke(
            cli, ["baas", "api-keys", "get", api_key_id, "--format", "json"]
        )

        assert get_result.exit_code == 0
        get_data = json.loads(get_result.output)
        assert get_data["id"] == api_key_id
        assert get_data["name"] == "E2E Test Key"
        # Security: API key value must NOT be in response
        assert "api_key" not in get_data

        # Step 4: Update API key
        # Note: API endpoint only supports updating name and expires_at, not tier
        update_result = self.runner.invoke(
            cli,
            [
                "baas",
                "api-keys",
                "update",
                api_key_id,
                "--name",
                "Updated E2E Key",
                "--format",
                "json",
            ],
        )

        assert update_result.exit_code == 0
        update_data = json.loads(update_result.output)
        assert update_data["name"] == "Updated E2E Key"
        # Tier remains unchanged (API doesn't support tier updates)
        assert update_data["tier"] == "FREE"

        # Step 5: Verify update by getting again
        get_updated_result = self.runner.invoke(
            cli, ["baas", "api-keys", "get", api_key_id, "--format", "json"]
        )

        assert get_updated_result.exit_code == 0
        get_updated_data = json.loads(get_updated_result.output)
        assert get_updated_data["name"] == "Updated E2E Key"
        # Tier remains unchanged (API doesn't support tier updates)
        assert get_updated_data["tier"] == "FREE"

        # Step 6: Revoke API key
        revoke_result = self.runner.invoke(cli, ["baas", "api-keys", "revoke", api_key_id])

        assert revoke_result.exit_code == 0
        assert "revoked successfully" in revoke_result.output.lower()

        # Step 7: Verify revocation by getting again (should show inactive)
        get_revoked_result = self.runner.invoke(
            cli, ["baas", "api-keys", "get", api_key_id, "--format", "json"]
        )

        assert get_revoked_result.exit_code == 0
        get_revoked_data = json.loads(get_revoked_result.output)
        assert get_revoked_data["is_active"] is False
        assert get_revoked_data["revoked_at"] is not None

    def test_multiple_api_keys_workflow(self):
        """
        Test managing multiple API keys with different tiers
        """
        # Create multiple API keys
        keys = []
        for i, tier in enumerate(["FREE", "PRO"], 1):
            create_result = self.runner.invoke(
                cli,
                [
                    "baas",
                    "api-keys",
                    "create",
                    "--name",
                    f"Key {i} - {tier}",
                    "--tier",
                    tier,
                    "--format",
                    "json",
                ],
            )
            assert create_result.exit_code == 0
            key_data = json.loads(create_result.output)
            keys.append(key_data)

        # List all keys
        list_result = self.runner.invoke(cli, ["baas", "api-keys", "list", "--format", "json"])

        assert list_result.exit_code == 0
        list_data = json.loads(list_result.output)
        assert len(list_data) >= 2

        # Verify all keys are present
        key_ids = {key["id"] for key in keys}
        list_key_ids = {key["id"] for key in list_data}
        assert key_ids.issubset(list_key_ids)

        # Filter by tier
        free_list_result = self.runner.invoke(
            cli, ["baas", "api-keys", "list", "--tier", "FREE", "--format", "json"]
        )

        assert free_list_result.exit_code == 0
        free_list_data = json.loads(free_list_result.output)
        free_keys = [key for key in free_list_data if key["tier"] == "FREE"]
        assert len(free_keys) >= 1

    def test_api_key_security_workflow(self):
        """
        Test security aspects: API key value only shown once, never in get command
        """
        # Create API key and capture the value
        create_result = self.runner.invoke(
            cli, ["baas", "api-keys", "create", "--name", "Security Test Key", "--format", "json"]
        )

        assert create_result.exit_code == 0
        create_data = json.loads(create_result.output)
        api_key_id = create_data["id"]
        api_key_value = create_data["api_key"]
        assert api_key_value is not None

        # Try to get the key - value should NOT be present
        get_result = self.runner.invoke(
            cli, ["baas", "api-keys", "get", api_key_id, "--format", "json"]
        )

        assert get_result.exit_code == 0
        get_data = json.loads(get_result.output)
        assert "api_key" not in get_data
        assert api_key_value not in get_result.output

        # Try to get in table format - value should NOT be present
        get_table_result = self.runner.invoke(cli, ["baas", "api-keys", "get", api_key_id])

        assert get_table_result.exit_code == 0
        assert api_key_value not in get_table_result.output
        assert (
            "not displayed" in get_table_result.output.lower()
            or "security" in get_table_result.output.lower()
        )

    def test_api_key_validation_workflow(self):
        """
        Test validation scenarios: empty name, invalid expiration, etc.
        """
        # Test empty name
        result = self.runner.invoke(cli, ["baas", "api-keys", "create", "--name", ""])

        assert result.exit_code != 0
        assert "cannot be empty" in result.output.lower()

        # Test past expiration date
        past_date = (timezone.now() - timedelta(days=1)).isoformat()
        result = self.runner.invoke(
            cli, ["baas", "api-keys", "create", "--name", "Test Key", "--expires-at", past_date]
        )

        assert result.exit_code != 0
        assert "future" in result.output.lower()

        # Test invalid expiration format
        result = self.runner.invoke(
            cli,
            ["baas", "api-keys", "create", "--name", "Test Key", "--expires-at", "invalid-date"],
        )

        assert result.exit_code != 0
        assert "format" in result.output.lower() or "invalid" in result.output.lower()

    def test_api_key_error_handling_workflow(self):
        """
        Test error handling: not found, invalid operations, etc.
        """
        fake_id = "123e4567-e89b-12d3-a456-426614174000"

        # Test getting non-existent key
        result = self.runner.invoke(cli, ["baas", "api-keys", "get", fake_id])

        assert result.exit_code != 0
        assert "not found" in result.output.lower() or "404" in result.output

        # Test updating non-existent key
        result = self.runner.invoke(
            cli, ["baas", "api-keys", "update", fake_id, "--name", "Updated Name"]
        )

        assert result.exit_code != 0
        assert "not found" in result.output.lower() or "404" in result.output

        # Test revoking non-existent key
        result = self.runner.invoke(cli, ["baas", "api-keys", "revoke", fake_id])

        assert result.exit_code != 0
        assert "not found" in result.output.lower() or "404" in result.output

        # Test updating without providing any fields
        # First create a real key
        create_result = self.runner.invoke(
            cli, ["baas", "api-keys", "create", "--name", "Test Key", "--format", "json"]
        )
        assert create_result.exit_code == 0
        real_key_id = json.loads(create_result.output)["id"]

        # Try to update without fields
        result = self.runner.invoke(cli, ["baas", "api-keys", "update", real_key_id])

        assert result.exit_code != 0
        assert "at least one field" in result.output.lower()
