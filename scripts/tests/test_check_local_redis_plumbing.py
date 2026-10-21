"""TDD pins for ``check_local_redis_plumbing.py`` — the local-run Redis
plumbing gate (close-test-coverage-gaps 0.5).

The gate exists because the contracts Redis-touching tests skip on
host-side runs: the recipes never set ``REDIS_CACHE_URL``, the settings
default resolves to the wrong instance, and the tests connection-refuse.
The plumbing is ``REDIS_CACHE_URL=redis://localhost:6479/0`` (the test
stack's cache Redis published on the host).

Every parse decision is drilled both ways against minimal fixtures (real
text through the real parser — no mocks), plus live-repo drift pins: a
recipe doc that drops the line, or a Makefile recipe that runs a
contracts Redis test locally without the env var, must fail here.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

import check_local_redis_plumbing as gate  # type: ignore[import-not-found]  # runtime sys.path injection, scripts/ is not a package

MAKEFILE = gate.MAKEFILE
RECIPE_DOCS = gate.RECIPE_DOCS
PLUMBING = gate.PLUMBING
check_docs = gate.check_docs
check_makefile_local_recipes = gate.check_makefile_local_recipes

REDIS_TESTS = {
    "hub/apps/contracts/tests/test_odps_rate_limiting.py",
    "hub/apps/contracts/tests/test_ref_resolver_caching.py",
}


class TestCheckDocs:
    def test_missing_line_is_reported(self, tmp_path):
        doc = tmp_path / "recipe.md"
        doc.write_text("```bash\nexport REDIS_URL=redis://127.0.0.1:63799/0\n```\n")
        assert check_docs((doc,)) == [str(doc)]

    def test_correct_line_passes(self, tmp_path):
        doc = tmp_path / "recipe.md"
        doc.write_text(
            f"```bash\nexport REDIS_URL=redis://127.0.0.1:63799/0\nexport {PLUMBING}\n```\n"
        )
        assert check_docs((doc,)) == []

    def test_wrong_value_is_reported(self, tmp_path):
        # A different instance/db (e.g. the old 63799/13 drift) is NOT the
        # canonical plumbing and must fail.
        doc = tmp_path / "recipe.md"
        doc.write_text("export REDIS_CACHE_URL=redis://127.0.0.1:63799/13\n")
        assert check_docs((doc,)) == [str(doc)]

    def test_unreadable_doc_is_reported(self, tmp_path):
        assert check_docs((tmp_path / "nope.md",)) != []


class TestCheckMakefileLocalRecipes:
    def test_local_recipe_without_plumbing_is_reported(self):
        text = (
            "test-batch-2-3:\n"
            "\tpython3 -m pytest \\\n"
            "\t\thub/apps/contracts/tests/test_odps_rate_limiting.py \\\n"
            "\t\t-q\n"
        )
        assert check_makefile_local_recipes(text, REDIS_TESTS) == ["test-batch-2-3"]

    def test_local_recipe_with_plumbing_passes(self):
        text = (
            "test-local-contracts-redis:\n"
            f"\t{PLUMBING} python3 -m pytest "
            "hub/apps/contracts/tests/test_odps_rate_limiting.py -q\n"
        )
        assert check_makefile_local_recipes(text, REDIS_TESTS) == []

    def test_in_container_recipes_are_exempt(self):
        # docker exec recipes inherit the compose env — no plumbing needed.
        text = (
            "test-batch-2-3:\n"
            "\tdocker compose -f docker-compose.test.yml exec -T api-service-test \\\n"
            "\t\tpython -u -m pytest \\\n"
            "\t\thub/apps/contracts/tests/test_odps_rate_limiting.py \\\n"
            "\t\t--reuse-db -q\n"
        )
        assert check_makefile_local_recipes(text, REDIS_TESTS) == []

    def test_recipes_without_redis_tests_are_ignored(self):
        text = "test-other:\n\tpython3 -m pytest hub/apps/other/tests/test_x.py -q\n"
        assert check_makefile_local_recipes(text, REDIS_TESTS) == []

    def test_precedent_12_4_shape_passes(self):
        text = (
            "test-batch-12-4: ## Datacontract-service tests\n"
            "\t-(cd services/datacontract-service && "
            f"{PLUMBING} python3 -m pytest tests/ -q)\n"
        )
        assert check_makefile_local_recipes(text, REDIS_TESTS) == []


class TestLiveRepo:
    def test_recipe_docs_carry_the_plumbing(self):
        # Drift pin: removing the line from any canonical recipe doc must
        # fail here.
        assert check_docs() == [], f"docs missing {PLUMBING}"

    def test_makefile_has_no_unplumbed_local_contracts_redis_recipes(self):
        # Drift pin: a future local-run recipe listing a contracts Redis
        # test must carry the env var.
        redis_tests = gate.redis_touching_contracts_tests()
        assert redis_tests, "contracts Redis tests must be discoverable"
        offenders = check_makefile_local_recipes(MAKEFILE.read_text(), redis_tests)
        assert offenders == [], f"unplumbed local recipes: {offenders}"
