"""
Tests for Phase 18 — PostgreSQL Full-Text Search (FTS).

Covers:
  test_fts_search_returns_ranked_results   — GET /api/search/?q=<term> returns hits
  test_fts_search_tenant_scoped            — results are isolated per tenant
  test_fts_index_updated_on_save           — post_save signal enqueues RQ task
  test_s3_module_bucket_policy_blocks_public_access  — Terraform HCL sanity
  test_migration_script_idempotent         — script skips already-present objects
"""

import os
from unittest.mock import patch

import pytest
from django.contrib.postgres.search import SearchVector
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.contracts.models import Contract
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _disconnect_semantic_signals():
    """Disconnect heavy signals that cause external HTTP calls during tests."""
    from django.db.models.signals import post_save
    import importlib

    for dotted in (
        "hub.apps.semantic.signals.asset_saved",
        "hub.apps.semantic.signals.contract_saved",
        "hub.apps.assets.signals.rebuild_asset_search_vector",
        "hub.apps.contracts.signals.rebuild_contract_search_vector",
    ):
        try:
            module_path, func_name = dotted.rsplit(".", 1)
            mod = importlib.import_module(module_path)
            handler = getattr(mod, func_name)
            sender_map = {
                "asset_saved": Asset,
                "rebuild_asset_search_vector": Asset,
                "contract_saved": Contract,
                "rebuild_contract_search_vector": Contract,
            }
            sender = sender_map.get(func_name)
            post_save.disconnect(handler, sender=sender)
        except (ImportError, AttributeError):
            pass


def _create_tenant(slug):
    return Tenant.objects.create(
        name=f"Tenant {slug}",
        slug=slug,
        status="ACTIVE",
        kyc_status="UNVERIFIED",
    )


def _create_user(tenant, email="user@test.com"):
    return User.objects.create_user(
        email=email,
        password="testpass123",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )


def _create_asset(tenant, user, *, name, description="", domain=""):
    return Asset.objects.create(
        tenant=tenant,
        key=name.lower().replace(" ", "-"),
        name=name,
        description=description,
        domain=domain,
        status=AssetStatus.ACTIVE,
        created_by=user,
    )


def _create_contract(tenant, user, *, original_spec_type="datacontract"):
    return Contract.objects.create(
        tenant=tenant,
        original_spec_type=original_spec_type,
        status="ACTIVE",
        created_by=user,
    )


# ---------------------------------------------------------------------------
# 1. Ranked results
# ---------------------------------------------------------------------------

@pytest.mark.django_db(transaction=True)
class TestFTSSearchRankedResults(TestCase):
    def setUp(self):
        _disconnect_semantic_signals()
        self.client = APIClient()
        self.tenant = _create_tenant("rank-tenant")
        self.user = _create_user(self.tenant)

        self.asset_alpha = _create_asset(
            self.tenant,
            self.user,
            name="Alpha Dataset",
            description="alpha data",
        )
        self.asset_beta = _create_asset(
            self.tenant,
            self.user,
            name="Beta Resource",
            description="unrelated",
        )

        # Set search vectors directly (bypass RQ)
        for asset in (self.asset_alpha, self.asset_beta):
            Asset.objects.filter(pk=asset.pk).update(
                search_vector=(
                    SearchVector("name", weight="A")
                    + SearchVector("description", weight="B")
                )
            )

        self.client.force_authenticate(user=self.user)

    def test_returns_matching_asset(self):
        resp = self.client.get("/api/search/", {"q": "alpha"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        ids = [item["id"] for item in resp.data.get("results", resp.data)]
        self.assertIn(str(self.asset_alpha.pk), ids)

    def test_non_matching_term_not_returned(self):
        resp = self.client.get("/api/search/", {"q": "zzznomatch"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = resp.data.get("results", resp.data)
        self.assertEqual(len(results), 0)

    def test_missing_q_returns_200_filter_only(self):
        """Empty/missing q returns 200 with valid response structure."""
        resp = self.client.get("/api/search/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("results", resp.data)
        self.assertIsInstance(resp.data["results"], list)

    def test_unauthenticated_returns_401(self):
        self.client.logout()
        resp = self.client.get("/api/search/", {"q": "alpha"})
        self.assertIn(
            resp.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    def test_results_include_rank_field(self):
        resp = self.client.get("/api/search/", {"q": "alpha", "types": "assets"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = resp.data.get("results", resp.data)
        if results:
            self.assertIn("rank", results[0])


# ---------------------------------------------------------------------------
# 2. Tenant isolation
# ---------------------------------------------------------------------------

@pytest.mark.django_db(transaction=True)
class TestFTSSearchTenantScoped(TestCase):
    def setUp(self):
        _disconnect_semantic_signals()
        self.client = APIClient()

        self.tenant_a = _create_tenant("tenant-a")
        self.tenant_b = _create_tenant("tenant-b")
        self.user_a = _create_user(self.tenant_a, email="a@test.com")
        self.user_b = _create_user(self.tenant_b, email="b@test.com")

        self.asset_a = _create_asset(
            self.tenant_a, self.user_a, name="Confidential Report A"
        )
        self.asset_b = _create_asset(
            self.tenant_b, self.user_b, name="Confidential Report B"
        )

        for asset in (self.asset_a, self.asset_b):
            Asset.objects.filter(pk=asset.pk).update(
                search_vector=SearchVector("name", weight="A")
            )

    def test_tenant_a_sees_only_own_assets(self):
        self.client.force_authenticate(user=self.user_a)
        resp = self.client.get("/api/search/", {"q": "confidential"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        ids = [item["id"] for item in resp.data.get("results", resp.data)]
        self.assertIn(str(self.asset_a.pk), ids)
        self.assertNotIn(str(self.asset_b.pk), ids)

    def test_tenant_b_does_not_see_tenant_a_assets(self):
        self.client.force_authenticate(user=self.user_b)
        resp = self.client.get("/api/search/", {"q": "confidential"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        ids = [item["id"] for item in resp.data.get("results", resp.data)]
        self.assertNotIn(str(self.asset_a.pk), ids)
        self.assertIn(str(self.asset_b.pk), ids)


# ---------------------------------------------------------------------------
# 3. post_save signal enqueues RQ task
# ---------------------------------------------------------------------------

@pytest.mark.django_db(transaction=True)
class TestFTSIndexUpdatedOnSave(TestCase):
    """Verify that saving an Asset/Contract triggers the RQ enqueue function."""

    def setUp(self):
        from django.db.models.signals import post_save
        from hub.apps.assets.signals import rebuild_asset_search_vector
        from hub.apps.contracts.signals import rebuild_contract_search_vector

        # Disconnect first so this class is re-entrant (survives being run
        # after a prior class that left them disconnected).
        post_save.disconnect(rebuild_asset_search_vector, sender=Asset)
        post_save.disconnect(rebuild_contract_search_vector, sender=Contract)
        post_save.connect(rebuild_asset_search_vector, sender=Asset)
        post_save.connect(rebuild_contract_search_vector, sender=Contract)
        self.tenant = _create_tenant("signal-tenant")
        self.user = _create_user(self.tenant, email="signal@test.com")

    def tearDown(self):
        """Clean up signal connections to leave state clean for subsequent tests."""
        from django.db.models.signals import post_save
        from hub.apps.assets.signals import rebuild_asset_search_vector
        from hub.apps.contracts.signals import rebuild_contract_search_vector
        post_save.disconnect(rebuild_asset_search_vector, sender=Asset)
        post_save.disconnect(rebuild_contract_search_vector, sender=Contract)
        super().tearDown()

    @patch("hub.apps.search.tasks.enqueue_asset_search_vector_update")
    def test_asset_save_calls_enqueue(self, mock_enqueue):
        with self.captureOnCommitCallbacks(execute=True):
            asset = _create_asset(self.tenant, self.user, name="Signal Test Asset")
        mock_enqueue.assert_called_once_with(str(asset.pk))

    @patch("hub.apps.search.tasks.enqueue_contract_search_vector_update")
    def test_contract_save_calls_enqueue(self, mock_enqueue):
        with self.captureOnCommitCallbacks(execute=True):
            contract = _create_contract(self.tenant, self.user)
        mock_enqueue.assert_called_once_with(str(contract.pk))

    @patch(
        "hub.apps.search.tasks.enqueue_asset_search_vector_update",
        side_effect=Exception("rq down"),
    )
    def test_enqueue_failure_does_not_raise(self, _mock):
        """Signal must swallow enqueue errors so saves never fail."""
        try:
            with self.captureOnCommitCallbacks(execute=True):
                _create_asset(self.tenant, self.user, name="Safe Even If RQ Down")
        except Exception as exc:
            self.fail(f"Asset save raised unexpectedly: {exc}")


# ---------------------------------------------------------------------------
# 4. Terraform S3 module — public access block sanity
# ---------------------------------------------------------------------------

class TestS3ModuleBucketPolicyBlocksPublicAccess(TestCase):
    """
    Read-only check that the Terraform S3 module HCL blocks all public access
    and sets AES-256 encryption.  No Terraform binary required.
    """

    # From tests/ → apps/search/ → apps/ → hub/ → repo-root
    MAIN_TF = os.path.normpath(os.path.join(
        os.path.dirname(__file__),
        "../../../..",
        "infrastructure/terraform/s3/main.tf",
    ))

    def _read_tf(self):
        with open(self.MAIN_TF) as fh:
            return fh.read()

    def test_public_access_block_all_true(self):
        tf = self._read_tf()
        self.assertIn("block_public_acls       = true", tf)
        self.assertIn("block_public_policy     = true", tf)
        self.assertIn("ignore_public_acls      = true", tf)
        self.assertIn("restrict_public_buckets = true", tf)

    def test_kms_encryption(self):
        """Phase 51: SSE-KMS replaces SSE-S3 (AES256)."""
        tf = self._read_tf()
        self.assertIn('sse_algorithm     = "aws:kms"', tf)

    def test_versioning_enabled(self):
        tf = self._read_tf()
        self.assertIn('status = "Enabled"', tf)

    def test_deny_http_policy(self):
        tf = self._read_tf()
        self.assertIn('"aws:SecureTransport"', tf)

    def test_irsa_role_defined(self):
        tf = self._read_tf()
        self.assertIn("aws_iam_role", tf)
        self.assertIn("AssumeRoleWithWebIdentity", tf)


# ---------------------------------------------------------------------------
# 5. Migration script idempotency
# ---------------------------------------------------------------------------

class TestMigrationScriptIdempotent(TestCase):
    """
    Unit-test the idempotency logic of migrate-minio-to-s3.sh without running
    actual AWS/MinIO commands.
    """

    SCRIPT = os.path.normpath(os.path.join(
        os.path.dirname(__file__),
        "../../../..",
        "scripts/migrate-minio-to-s3.sh",
    ))

    def _read_script(self):
        with open(self.SCRIPT) as fh:
            return fh.read()

    def test_script_is_executable(self):
        self.assertTrue(os.path.isfile(self.SCRIPT), f"Not found: {self.SCRIPT}")
        self.assertTrue(os.access(self.SCRIPT, os.X_OK), "Not executable")

    def test_script_has_set_euo_pipefail(self):
        self.assertIn("set -euo pipefail", self._read_script())

    def test_script_contains_etag_idempotency_check(self):
        content = self._read_script()
        self.assertIn("minio_etag", content)
        self.assertIn("s3_etag", content)
        self.assertIn("already_exists", content)

    def test_script_uses_stdin_streaming(self):
        content = self._read_script()
        self.assertIn("mc cat", content)
        self.assertIn("aws s3 cp -", content)

    def test_script_logs_jsonl(self):
        content = self._read_script()
        self.assertIn('"status":"ok"', content)
        self.assertIn('"status":"skipped"', content)
        self.assertIn('"status":"error"', content)

    def test_script_exits_nonzero_on_errors(self):
        self.assertIn("exit 1", self._read_script())
