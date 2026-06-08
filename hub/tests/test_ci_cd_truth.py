"""
112.G — CI/CD truth tests.

Proves:
1. G.1: CI workflow has all Phase 97 jobs
2. G.2: Path filters + caching + OpenAPI contract test present
3. G.3: Makefile has canonical local=CI targets
"""
import os

import pytest
from django.test import TestCase


pytestmark = pytest.mark.django_db(transaction=True)

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


def _read_file(rel_path):
    path = os.path.join(_REPO_ROOT, rel_path)
    if not os.path.exists(path):
        pytest.skip(f"{rel_path} not found")
    with open(path) as f:
        return f.read()


class CIWorkflowPhase97Test(TestCase):
    """G.1 — CI workflow contains all Phase 97 jobs."""

    def test_test_backend_job_exists(self):
        ci = _read_file(".github/workflows/ci.yml")
        self.assertIn("test-backend:", ci)

    def test_test_frontend_unit_job_exists(self):
        ci = _read_file(".github/workflows/ci.yml")
        self.assertIn("test-frontend-unit:", ci)

    def test_test_microservices_job_exists(self):
        ci = _read_file(".github/workflows/ci.yml")
        self.assertIn("test-microservices:", ci)

    def test_helm_lint_job_exists(self):
        ci = _read_file(".github/workflows/ci.yml")
        self.assertIn("helm-lint:", ci)

    def test_docker_build_test_job_exists(self):
        ci = _read_file(".github/workflows/ci.yml")
        self.assertIn("docker-build-test:", ci)

    def test_backend_uses_pytest(self):
        """test-backend must run pytest hub/apps/."""
        ci = _read_file(".github/workflows/ci.yml")
        self.assertIn("python -m pytest hub/apps/", ci)

    def test_frontend_uses_vitest(self):
        """test-frontend-unit must run vitest."""
        ci = _read_file(".github/workflows/ci.yml")
        self.assertIn("npx vitest", ci)


class CIPathFiltersAndCachingTest(TestCase):
    """G.2 — Path filters, caching, and OpenAPI contract."""

    def test_pip_cache_exists(self):
        ci = _read_file(".github/workflows/ci.yml")
        self.assertIn("actions/cache@v4", ci)
        self.assertIn("hashFiles('requirements.txt')", ci)

    def test_node_cache_exists(self):
        ci = _read_file(".github/workflows/ci.yml")
        self.assertIn(
            "hashFiles('frontend/package-lock.json')", ci,
        )

    def test_openapi_contract_test_exists(self):
        """CI must have OpenAPI contract smoke test."""
        ci = _read_file(".github/workflows/ci.yml")
        self.assertIn("contract-test:", ci)
        self.assertIn("contract_test_openapi.py", ci)

    def test_reuse_db_for_speed(self):
        """Backend tests use --reuse-db for speed."""
        ci = _read_file(".github/workflows/ci.yml")
        self.assertIn("--reuse-db", ci)

    def test_artifact_upload_on_failure(self):
        """Test results uploaded on failure for debugging."""
        ci = _read_file(".github/workflows/ci.yml")
        self.assertIn("actions/upload-artifact@v4", ci)


class MakefileCIParityTest(TestCase):
    """G.3 — Makefile documents canonical local=CI commands."""

    def test_test_ci_target_exists(self):
        mk = _read_file("Makefile")
        self.assertIn("test-ci:", mk)

    def test_test_ci_backend_target_exists(self):
        mk = _read_file("Makefile")
        self.assertIn("test-ci-backend:", mk)

    def test_test_ci_frontend_target_exists(self):
        mk = _read_file("Makefile")
        self.assertIn("test-ci-frontend:", mk)

    def test_test_ci_lint_target_exists(self):
        mk = _read_file("Makefile")
        self.assertIn("test-ci-lint:", mk)

    def test_backend_mirrors_ci_command(self):
        """test-ci-backend must use same pytest command as CI."""
        mk = _read_file("Makefile")
        # Isolate the test-ci-backend target recipe to avoid matching
        # substrings from unrelated targets or comments.
        import re
        target_match = re.search(
            r"^test-ci-backend:.*?\n(?:^\t.*\n?)*", mk, re.MULTILINE
        )
        self.assertIsNotNone(target_match, "test-ci-backend target not found")
        target_recipe = target_match.group(0)
        # Both CI and Makefile must use the same core command.
        # The Makefile uses ``python -u -m pytest`` (with -u for unbuffered),
        # while CI may use ``python -m pytest``.  Match on the stable suffix.
        self.assertIn(
            "pytest hub/apps/", target_recipe,
            f"test-ci-backend must run pytest hub/apps/\nTarget:\n{target_recipe}",
        )
        self.assertIn(
            "--reuse-db", target_recipe,
            f"test-ci-backend must use --reuse-db\nTarget:\n{target_recipe}",
        )
        self.assertIn(
            "docker-compose.test.yml", target_recipe,
            f"test-ci-backend must use docker-compose.test.yml\nTarget:\n{target_recipe}",
        )

    def test_frontend_mirrors_ci_command(self):
        """test-ci-frontend must use same vitest command as CI."""
        mk = _read_file("Makefile")
        self.assertIn("npx vitest", mk)
