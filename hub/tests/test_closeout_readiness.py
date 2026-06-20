"""
112.M — OpenSpec closeout & first cloud readiness tests.

Proves:
1. M.1: OpenSpec change directory exists with required files
2. M.2: Test execution plan + full suite definition exist
3. M.3: Staging helm values exist with required sections
4. M.4: Post-deploy test strategy documented
5. M.5: Smoke tests exist for post-deploy verification
6. M.6: OpenSpec archive workflow documented
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


class OpenSpecChangeTest(TestCase):
    """M.1 — OpenSpec preprod01 change exists."""

    def test_preprod01_tasks_exists(self):
        self.assertTrue(
            _exists("openspec/changes/preprod01/tasks.md"),
        )

    def test_preprod01_has_design(self):
        self.assertTrue(
            _exists("openspec/changes/preprod01/design.md"),
        )

    def test_preprod01_has_specs(self):
        specs_dir = os.path.join(
            _REPO_ROOT,
            "openspec/changes/preprod01/specs",
        )
        self.assertTrue(
            os.path.isdir(specs_dir),
            "preprod01/specs/ directory must exist",
        )


class TestTiersDefinedTest(TestCase):
    """M.2 — Test execution plan + suite definition exist."""

    def test_test_execution_plan_exists(self):
        self.assertTrue(
            _exists("docs/TEST_EXECUTION_PLAN.md"),
        )

    def test_full_suite_definition_exists(self):
        self.assertTrue(
            _exists("docs/FULL_TEST_SUITE_DEFINITION.md"),
        )

    def test_evidence_collection_plan_exists(self):
        self.assertTrue(
            _exists("docs/EVIDENCE_COLLECTION_PLAN.md"),
        )

    def test_execution_plan_covers_smoke(self):
        c = _read("docs/TEST_EXECUTION_PLAN.md")
        self.assertIn("smoke", c.lower())

    def test_execution_plan_covers_security(self):
        c = _read("docs/TEST_EXECUTION_PLAN.md")
        self.assertIn("security", c.lower())


class StagingHelmTest(TestCase):
    """M.3 — Staging values exist with required config."""

    def test_staging_values_exist(self):
        self.assertTrue(_exists("helm/values.staging.yaml"))

    def test_staging_has_ingress(self):
        c = _read("helm/values.staging.yaml")
        self.assertIn("ingress", c)

    def test_staging_has_tls(self):
        c = _read("helm/values.staging.yaml")
        self.assertIn("tls", c.lower())

    def test_staging_has_aws_secrets_manager(self):
        """Phase 211: Vault replaced by AWS Secrets Manager + IRSA."""
        c = _read("helm/values.staging.yaml")
        self.assertIn("awsSecretsManager", c)

    def test_staging_has_external_secrets(self):
        c = _read("helm/values.staging.yaml")
        self.assertIn("externalSecrets", c)


class PostDeployStrategyTest(TestCase):
    """M.4 — Post-deploy test strategy documented."""

    def test_strategy_doc_exists(self):
        self.assertTrue(
            _exists("docs/POST_DEPLOY_TEST_STRATEGY.md"),
        )

    def test_has_smoke_section(self):
        c = _read("docs/POST_DEPLOY_TEST_STRATEGY.md")
        self.assertIn("Smoke", c)

    def test_has_rollback_strategy(self):
        c = _read("docs/POST_DEPLOY_TEST_STRATEGY.md")
        self.assertIn("rollback", c.lower())

    def test_has_evidence_bundle(self):
        c = _read("docs/POST_DEPLOY_TEST_STRATEGY.md")
        self.assertIn("Evidence", c)

    def test_has_staging_checklist(self):
        c = _read("docs/POST_DEPLOY_TEST_STRATEGY.md")
        self.assertIn("Staging Checklist", c)


class SmokeTestSuiteTest(TestCase):
    """M.5 — Smoke tests exist for post-deploy."""

    def test_smoke_directory_exists(self):
        self.assertTrue(
            os.path.isdir(
                os.path.join(_REPO_ROOT, "tests/smoke"),
            ),
        )

    def test_smoke_has_health_test(self):
        self.assertTrue(
            _exists("tests/smoke/test_api_health.py") or _exists("tests/smoke/test_health.py"),
        )

    def test_smoke_has_auth_test(self):
        self.assertTrue(_exists("tests/smoke/test_auth.py"))

    def test_deploy_workflow_runs_smoke(self):
        c = _read(".github/workflows/deploy.yml")
        self.assertIn("tests/smoke", c)


class ArchiveWorkflowTest(TestCase):
    """M.6 — OpenSpec archive workflow documented."""

    def test_archive_command_documented(self):
        """Archive command must be documented somewhere."""
        self.assertTrue(
            _exists(".cursor/commands/openspec-archive.md") or _exists("docs/OPENSPEC_ARCHIVE.md"),
            "OpenSpec archive workflow must be documented",
        )

    def test_openspec_project_exists(self):
        self.assertTrue(_exists("openspec/project.md"))
