"""
112.K — Operator external setup tests.

Proves:
1. K.1: Operator setup checklist exists with required sections
2. K.2: Capability degradation guide exists and is linked from OPERATIONS.md
3. K.3: Helm values reference expected data-plane services
4. K.4: Prefect configuration present in helm values
5. K.5: Vault + ExternalSecret templates exist
"""
import os

import pytest
from django.test import TestCase


pytestmark = pytest.mark.django_db(transaction=True)

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


def _read(rel_path):
    path = os.path.join(_REPO_ROOT, rel_path)
    if not os.path.exists(path):
        pytest.skip(f"{rel_path} not found")
    with open(path) as f:
        return f.read()


def _exists(rel_path):
    return os.path.exists(os.path.join(_REPO_ROOT, rel_path))


class OperatorSetupChecklistTest(TestCase):
    """K.1 — Setup checklist with owner + verification."""

    def test_checklist_exists(self):
        self.assertTrue(
            _exists("docs/operator-external-setup-checklist.md"),
        )

    def test_has_postgresql_section(self):
        c = _read("docs/operator-external-setup-checklist.md")
        self.assertIn("PostgreSQL", c)
        self.assertIn("pg_isready", c)

    def test_has_redis_section(self):
        c = _read("docs/operator-external-setup-checklist.md")
        self.assertIn("Redis", c)
        self.assertIn("redis-cache", c)
        self.assertIn("redis-queue", c)

    def test_has_vault_section(self):
        c = _read("docs/operator-external-setup-checklist.md")
        self.assertIn("Vault", c)
        self.assertIn("ExternalSecret", c)

    def test_has_prefect_section(self):
        c = _read("docs/operator-external-setup-checklist.md")
        self.assertIn("Prefect", c)
        self.assertIn("prefect-integration", c)

    def test_has_verification_commands(self):
        c = _read("docs/operator-external-setup-checklist.md")
        self.assertIn("Verification", c)
        self.assertIn("kubectl", c)


class CapabilityDegradationTest(TestCase):
    """K.2 — Degradation guide exists and linked."""

    def test_degradation_guide_exists(self):
        self.assertTrue(
            _exists("docs/capability-degradation.md"),
        )

    def test_has_dependency_table(self):
        c = _read("docs/capability-degradation.md")
        self.assertIn("Dependency", c)
        self.assertIn("Impact When Down", c)

    def test_covers_all_critical_dependencies(self):
        c = _read("docs/capability-degradation.md")
        for dep in (
            "PostgreSQL", "Redis", "MinIO",
            "Fuseki", "Compliance Service",
            "Prefect",
        ):
            self.assertIn(dep, c, f"Must document {dep}")

    def test_has_circuit_breaker_reference(self):
        c = _read("docs/capability-degradation.md")
        self.assertIn("circuit breaker", c.lower())

    def test_linked_from_operations(self):
        c = _read("docs/OPERATIONS.md")
        self.assertIn(
            "capability-degradation.md", c,
            "OPERATIONS.md must link to degradation guide",
        )


class HelmDataPlaneTest(TestCase):
    """K.3 — Helm values match chart expectations."""

    def test_helm_values_exist(self):
        self.assertTrue(_exists("helm/values.yaml"))

    def test_helm_staging_values_exist(self):
        self.assertTrue(_exists("helm/values.staging.yaml"))

    def test_postgres_host_configured(self):
        v = _read("helm/values.yaml")
        self.assertIn("postgres", v.lower())

    def test_redis_queue_configured(self):
        v = _read("helm/values.yaml")
        self.assertIn("redis-queue", v)

    def test_external_secret_templates_exist(self):
        self.assertTrue(
            _exists(
                "helm/templates/externalsecrets/"
                "external-secret.yaml"
            ),
        )
        self.assertTrue(
            _exists(
                "helm/templates/externalsecrets/"
                "secret-store.yaml"
            ),
        )


class PrefectConfigTest(TestCase):
    """K.4 — Prefect configuration in helm values."""

    def test_prefect_worker_in_values(self):
        v = _read("helm/values.yaml")
        self.assertIn("prefect", v.lower())

    def test_prefect_integration_in_values(self):
        v = _read("helm/values.yaml")
        self.assertIn("prefectIntegration", v)

    def test_prefect_api_url_configured(self):
        v = _read("helm/values.yaml")
        self.assertIn("prefect-server", v)


class VaultESOTest(TestCase):
    """K.5 — Vault + ESO configuration."""

    def test_secret_store_template_has_aws_provider(self):
        """Phase 211: Vault replaced by AWS Secrets Manager provider.
        Verifies the SecretStore uses the AWS provider for Secrets Manager,
        not just a vague 'aws' substring match."""
        t = _read(
            "helm/templates/externalsecrets/secret-store.yaml",
        )
        self.assertIn("service: SecretsManager", t)

    def test_external_secret_syncs_django_secrets(self):
        t = _read(
            "helm/templates/externalsecrets/"
            "external-secret.yaml",
        )
        self.assertIn("SECRET_KEY", t)
        self.assertIn("JWT_SECRET_KEY", t)

    def test_external_secret_syncs_postgres(self):
        t = _read(
            "helm/templates/externalsecrets/"
            "external-secret.yaml",
        )
        self.assertIn("POSTGRES_PASSWORD", t)

    def test_deploy_workflow_references_oidc(self):
        """Phase 211: Vault removed. Deploy uses GitHub OIDC for AWS auth.
        Both the OIDC token permission and the AWS credentials action must
        be present for the OIDC→IRSA auth flow to function."""
        d = _read(".github/workflows/deploy.yml")
        self.assertIn("id-token: write", d)
        self.assertIn("configure-aws-credentials", d)
