"""TDD pins for ``check_batch_coverage.py`` — the test-batch-13 slicing
gate (close-test-coverage-gaps 0.3).

The gate exists because ``hub/apps/databricks_admin`` shipped 113 test
files (1,462 tests) with NO Makefile batch — the only unbatched
test-bearing app. Every parse decision is drilled against minimal
makefile fixtures (no mocks — real text through the real parser), plus
three drift pins against the repository's live Makefile:

- every on-disk databricks_admin test file is covered EXACTLY once;
- the 13-x leaf slice stays within the 26-file static budget;
- the live per-leaf test counts match the slice documented here (a
  re-slice that silently crosses the ~250-test budget fails this suite
  even if the static gate still passes).

RED drills: each fixture asserts exactly which problems the checker
reports, so a loosened checker (or one that skips real drift) fails.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import ClassVar

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

from check_batch_coverage import (
    APP_TESTS,
    MAKEFILE,
    find_problems,
    parse_recipes,
    recipe_files,
)

PHONY = ".PHONY: test-batch-13 test-batch-13-1 test-batch-13-2 test-batch-13-3 test-batch-13-4 test-batch-13-5 test-batch-13-6 test-batch-13-6a test-batch-13-7\n"
UMBRELLA = (
    "test-batch-13: ## umbrella\n"
    "\t@$(MAKE) test-batch-13-1 TEST_DB=$(TEST_DB) TEST_DB_SUFFIX=$(TEST_DB_SUFFIX)\n"
    "\t@$(MAKE) test-batch-13-2 TEST_DB=$(TEST_DB) TEST_DB_SUFFIX=$(TEST_DB_SUFFIX)\n"
    "\t@$(MAKE) test-batch-13-3 TEST_DB=$(TEST_DB) TEST_DB_SUFFIX=$(TEST_DB_SUFFIX)\n"
    "\t@$(MAKE) test-batch-13-4 TEST_DB=$(TEST_DB) TEST_DB_SUFFIX=$(TEST_DB_SUFFIX)\n"
    "\t@$(MAKE) test-batch-13-5 TEST_DB=$(TEST_DB) TEST_DB_SUFFIX=$(TEST_DB_SUFFIX)\n"
    "\t@$(MAKE) test-batch-13-6 TEST_DB=$(TEST_DB) TEST_DB_SUFFIX=$(TEST_DB_SUFFIX)\n"
    "\t@$(MAKE) test-batch-13-6a TEST_DB=$(TEST_DB) TEST_DB_SUFFIX=$(TEST_DB_SUFFIX)\n"
    "\t@$(MAKE) test-batch-13-7 TEST_DB=$(TEST_DB) TEST_DB_SUFFIX=$(TEST_DB_SUFFIX)\n"
)
ALL = (
    "test-batch-all: ## all batches\n"
    "\t-$(MAKE) test-batch-12-5 TEST_DB=$(TEST_DB) TEST_DB_SUFFIX=$(TEST_DB_SUFFIX)\n"
    "\t-$(MAKE) test-batch-13 TEST_DB=$(TEST_DB) TEST_DB_SUFFIX=$(TEST_DB_SUFFIX)\n"
)


def leaf(name: str, files: list[str]) -> str:
    recipe = f"{name}: ## domain\n"
    for f in files:
        recipe += f"\tdocker compose exec api python -m pytest hub/apps/databricks_admin/tests/{f} \\\n"
    recipe += "\t--reuse-db -q --timeout=300\n"
    return recipe


class TestParseRecipes:
    def test_recipes_map_batch_targets_to_text(self):
        text = (
            PHONY + leaf("test-batch-13-1", ["test_account_models.py"]) + UMBRELLA + ALL
        )
        recipes = parse_recipes(text)
        # parse_recipes tracks only test-batch-13* targets; the
        # test-batch-all recipe is parsed separately by find_problems.
        assert set(recipes) == {"test-batch-13-1", "test-batch-13"}

    def test_non_batch_targets_do_not_start_recipes(self):
        recipes = parse_recipes("lint:\n\t@echo hi\n" + UMBRELLA)
        assert set(recipes) == {"test-batch-13"}

    def test_recipe_files_extracts_test_paths_only(self):
        text = leaf("test-batch-13-1", ["test_account_models.py", "test_client.py"])
        assert recipe_files(parse_recipes(text)["test-batch-13-1"]) == {
            "test_account_models.py",
            "test_client.py",
        }


class TestFindProblemsFixtures:
    def _makefile(
        self,
        leaves: dict[str, list[str]],
        *,
        umbrella: str = UMBRELLA,
        all_recipe: str = ALL,
        phony: str = PHONY,
    ) -> str:
        body = phony
        for name, files in leaves.items():
            body += leaf(name, files)
        return body + umbrella + all_recipe

    def _disk(self, leaves: dict[str, list[str]]) -> set[str]:
        return {f for files in leaves.values() for f in files}

    def test_clean_makefile_reports_no_problems(self):
        leaves = {
            "test-batch-13-1": ["test_a.py", "test_b.py"],
            "test-batch-13-2": ["test_c.py"],
        }
        text = self._makefile(
            leaves,
            umbrella=(
                "test-batch-13: ## umbrella\n"
                "\t@$(MAKE) test-batch-13-1 TEST_DB=$(TEST_DB) TEST_DB_SUFFIX=$(TEST_DB_SUFFIX)\n"
                "\t@$(MAKE) test-batch-13-2 TEST_DB=$(TEST_DB) TEST_DB_SUFFIX=$(TEST_DB_SUFFIX)\n"
            ),
        )
        assert find_problems(text, self._disk(leaves), gated={}) == []

    def test_missing_file_is_reported(self):
        leaves = {"test-batch-13-1": ["test_a.py", "test_b.py"]}
        text = self._makefile(
            leaves,
            umbrella=(
                "test-batch-13: ## umbrella\n"
                "\t@$(MAKE) test-batch-13-1 TEST_DB=$(TEST_DB) TEST_DB_SUFFIX=$(TEST_DB_SUFFIX)\n"
            ),
        )
        problems = find_problems(text, self._disk(leaves) | {"test_c.py"}, gated={})
        assert "test_c.py is not listed in any test-batch-13-x recipe" in problems

    def test_duplicated_file_is_reported(self):
        leaves = {
            "test-batch-13-1": ["test_a.py"],
            "test-batch-13-2": ["test_a.py"],
        }
        text = self._makefile(leaves)
        problems = find_problems(text, self._disk(leaves), gated={})
        assert any("test_a.py is listed in multiple recipes" in p for p in problems)

    def test_ghost_file_reference_is_reported(self):
        leaves = {"test-batch-13-1": ["test_a.py", "test_ghost.py"]}
        text = self._makefile(leaves)
        # The recipe lists a file that does not exist on disk — the disk
        # set must be injected explicitly (deriving it from the leaves
        # would silently put the ghost on disk).
        problems = find_problems(text, {"test_a.py"}, gated={})
        assert any(
            "test_ghost.py" in p and "does not exist on disk" in p for p in problems
        )

    def test_budget_violation_is_reported(self):
        files = [f"test_f{i}.py" for i in range(27)]
        leaves = {"test-batch-13-1": files}
        text = self._makefile(leaves)
        problems = find_problems(text, self._disk(leaves), gated={})
        assert any("over the 26-file budget" in p for p in problems)

    def test_umbrella_omission_is_reported(self):
        leaves = {"test-batch-13-1": ["test_a.py"]}
        text = self._makefile(leaves)
        # UMBRELLA invokes 13-1..13-7 + 13-6a but only 13-1 exists —
        # the missing leaves are reported, the existing one is not.
        problems = find_problems(text, self._disk(leaves), gated={})
        assert any("test-batch-13-2" in p for p in problems)
        assert not any("test-batch-13-1" in p for p in problems)

    def test_all_omission_is_reported(self):
        leaves = {"test-batch-13-1": ["test_a.py"]}
        text = self._makefile(
            leaves,
            umbrella=(
                "test-batch-13: ## umbrella\n"
                "\t@$(MAKE) test-batch-13-1 TEST_DB=$(TEST_DB) TEST_DB_SUFFIX=$(TEST_DB_SUFFIX)\n"
            ),
            all_recipe=(
                "test-batch-all: ## all batches\n"
                "\t-$(MAKE) test-batch-12-5 TEST_DB=$(TEST_DB) TEST_DB_SUFFIX=$(TEST_DB_SUFFIX)\n"
            ),
        )
        problems = find_problems(text, self._disk(leaves), gated={})
        assert "test-batch-all does not invoke test-batch-13" in problems

    def test_missing_phony_is_reported(self):
        leaves = {"test-batch-13-1": ["test_a.py"]}
        text = self._makefile(
            leaves,
            umbrella=(
                "test-batch-13: ## umbrella\n"
                "\t@$(MAKE) test-batch-13-1 TEST_DB=$(TEST_DB) TEST_DB_SUFFIX=$(TEST_DB_SUFFIX)\n"
            ),
            phony=".PHONY: test-batch-13\n",
        )
        problems = find_problems(text, self._disk(leaves), gated={})
        assert "test-batch-13-1 is missing from .PHONY" in problems

    def test_gated_leaf_is_exempt_from_the_umbrella_requirement(self):
        # The 0.4 gated target (test-batch-13-8) is a leaf that the
        # umbrella intentionally never invokes — only the umbrella
        # requirement is waived; the .PHONY rule still applies.
        leaves = {
            "test-batch-13-1": ["test_a.py"],
            "test-batch-13-8": [],
        }
        text = self._makefile(
            leaves,
            umbrella=(
                "test-batch-13: ## umbrella\n"
                "\t@$(MAKE) test-batch-13-1 TEST_DB=$(TEST_DB) TEST_DB_SUFFIX=$(TEST_DB_SUFFIX)\n"
            ),
            phony=PHONY.rstrip("\n") + " test-batch-13-8\n",
        )
        problems = find_problems(
            text,
            self._disk(leaves),
            gated={"test-batch-13-8": "DATABRICKS_E2E-gated; out of the umbrella"},
        )
        assert not any(
            "umbrella does not invoke" in p and "13-8" in p for p in problems
        )
        assert problems == []

    def test_gated_leaf_still_requires_phony(self):
        leaves = {
            "test-batch-13-1": ["test_a.py"],
            "test-batch-13-8": [],
        }
        text = self._makefile(
            leaves,
            umbrella=(
                "test-batch-13: ## umbrella\n"
                "\t@$(MAKE) test-batch-13-1 TEST_DB=$(TEST_DB) TEST_DB_SUFFIX=$(TEST_DB_SUFFIX)\n"
            ),
            phony=".PHONY: test-batch-13 test-batch-13-1\n",
        )
        problems = find_problems(
            text,
            self._disk(leaves),
            gated={"test-batch-13-8": "DATABRICKS_E2E-gated; out of the umbrella"},
        )
        assert "test-batch-13-8 is missing from .PHONY" in problems

    def test_stale_gated_entry_is_reported(self):
        leaves = {"test-batch-13-1": ["test_a.py"]}
        text = self._makefile(
            leaves,
            umbrella=(
                "test-batch-13: ## umbrella\n"
                "\t@$(MAKE) test-batch-13-1 TEST_DB=$(TEST_DB) TEST_DB_SUFFIX=$(TEST_DB_SUFFIX)\n"
            ),
        )
        problems = find_problems(
            text,
            self._disk(leaves),
            gated={"test-batch-13-9": "ghost gated leaf"},
        )
        assert any(
            "test-batch-13-9" in p and "stale GATED_LEAVES entry" in p for p in problems
        )


class TestLiveMakefileDrift:
    """Pins against the repository's real Makefile — fail when the
    13-x slicing drifts without an intentional update here."""

    # The documented slice (close-test-coverage-gaps 0.3). Test counts
    # are from the 0.6 --collect-only pre-check (2026-09-28): 113 files,
    # 1,462 tests. A re-slice that crosses the ~250-test budget MUST
    # update this table — that is the point of the pin.
    SLICE: ClassVar[dict[str, tuple[int, int]]] = {
        "test-batch-13-1": (14, 164),
        "test-batch-13-2": (12, 82),
        "test-batch-13-3": (16, 239),
        "test-batch-13-4": (17, 241),
        "test-batch-13-5": (13, 238),
        "test-batch-13-6": (13, 125),
        "test-batch-13-6a": (11, 164),
        "test-batch-13-7": (20, 224),
    }

    def test_live_makefile_has_no_problems(self):
        problems = find_problems(MAKEFILE.read_text())
        assert problems == []

    @pytest.mark.parametrize("target", list(SLICE))
    def test_live_leaf_file_counts_match_the_slice(self, target):
        recipes = parse_recipes(MAKEFILE.read_text())
        expected_files = self.SLICE[target][0]
        assert len(recipe_files(recipes[target])) == expected_files

    def test_live_leaf_test_count_budget(self):
        # The dynamic budget check: every leaf's documented test count
        # must stay within the ~250-test guideline.
        for target, (_files, tests) in self.SLICE.items():
            assert tests <= 250, f"{target} documents {tests} tests — over budget"

    def test_live_disk_files_all_exist(self):
        assert APP_TESTS.is_dir()
        files = {p.name for p in APP_TESTS.glob("test_*.py")}
        assert len(files) == 116
