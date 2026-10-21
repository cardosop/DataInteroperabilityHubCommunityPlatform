"""TDD suite for check_core_test_scope.py (Phase T.2 / W14).

The merge-gate coverage truth: ``make test-core`` (and the ci.yml
``test-core`` job) run the backend with ``-m "not e2e and not integration
and not requires_* ..."`` — what they deselect IS the published scope.
This checker makes that scope machine-checked, in BOTH directions:

1. every deselection-family marker actually IN USE in hub/apps test files
   must appear in the expression (a new service-dependent test class must
   never silently RUN in core mode — the drift found in T.2: six
   ``requires_*``/``odh_inference`` markers were missing from the
   expression while 9 files used them);
2. every ``not X`` term in the expression must correspond to a family
   marker actually in use (dead terms — ``requires_fuseki``/
   ``requires_stripe`` at T.2 time — publish stale scope);
3. the Makefile.core target and the ci.yml job must deselect the SAME
   set (two sources of truth drift, W2.1 class).

No mocks: synthetic expressions/trees are evaluated by the REAL checker
functions; the final test runs the checker against the real repo.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from check_core_test_scope import (
    DESELECTION_FAMILY,
    collect_scope_violations,
    markers_in_use,
    parse_deselected_terms,
)

MAKEFILE_STUB = (
    "test-core: test-core-stack-up ## Core-only backend suite\n"
    "\tdocker compose $(CORE_COMPOSE) exec -T \\\n"
    "\t\t-e HUB_CORE_ONLY=1 \\\n"
    "\t\tapi-service-test \\\n"
    "\t\tpython -m pytest hub/apps/ hub/tests/test_mvp_mode.py --reuse-db -x -q \\\n"
    "\t\t-m {expression}\n"
)

WORKFLOW_STUB = (
    "  test-core:\n"
    "    name: Core-Only Backend Tests\n"
    "    steps:\n"
    "      - name: Run core-only backend tests\n"
    "        run: |\n"
    "          python -m pytest hub/apps/ hub/tests/test_mvp_mode.py \\\n"
    "            --reuse-db -x -q --timeout=300 \\\n"
    "            -m {expression}\n"
)


def _sources(expression: str) -> dict[str, str]:
    return {
        "Makefile.core": MAKEFILE_STUB.format(expression=expression),
        "ci.yml": WORKFLOW_STUB.format(expression=expression),
        "public ci-core.yml": WORKFLOW_STUB.format(expression=expression),
    }


class TestExpressionParsing:
    def test_parses_not_terms(self):
        terms = parse_deselected_terms('-m "not e2e and not integration and not network"')
        assert terms == {"e2e", "integration", "network"}

    def test_parses_term_used_as_marker(self):
        terms = parse_deselected_terms("not requires_fuseki and not requires_prefect")
        assert terms == {"requires_fuseki", "requires_prefect"}


def _clean_files() -> dict[str, str]:
    """One synthetic test file USING each deselection-family marker — the
    expression can only be clean when every term has a user."""
    return {
        f"hub/apps/x/tests/test_{i}.py": f"@pytest.mark.{marker}\n"
        for i, marker in enumerate(sorted(DESELECTION_FAMILY))
    }


def _clean_expression() -> str:
    terms = " and ".join(f"not {m}" for m in sorted(DESELECTION_FAMILY))
    return f'"{terms}"'


class TestScopeViolations:
    def test_clean_sources_have_no_violations(self):
        violations = collect_scope_violations(_sources(_clean_expression()), _clean_files())
        assert violations == [], violations

    def test_marker_in_use_but_absent_from_expression_is_a_violation(self):
        """The T.2 drift class: requires_aws-marked tests silently RAN in
        core mode because the expression never named them."""
        files = {"hub/apps/x/tests/test_a.py": "pytest.mark.requires_aws\n"}
        violations = collect_scope_violations(_sources('"not e2e and not integration"'), files)
        assert any("requires_aws" in v for v in violations), violations

    def test_dead_expression_term_is_a_violation(self):
        """A term with zero users publishes stale scope — the published
        numbers must match reality in both directions."""
        files = {"hub/apps/x/tests/test_a.py": "pytest.mark.integration\n"}
        violations = collect_scope_violations(
            _sources('"not e2e and not integration and not requires_fuseki"'), files
        )
        assert any("requires_fuseki" in v and "no test" in v for v in violations), violations

    def test_makefile_and_workflow_must_deselect_the_same_set(self):
        files = {"hub/apps/x/tests/test_a.py": "pytest.mark.integration\n"}
        sources = {
            "Makefile.core": MAKEFILE_STUB.format(
                expression='"not e2e and not integration and not network"'
            ),
            "ci.yml": WORKFLOW_STUB.format(expression='"not e2e and not integration"'),
        }
        violations = collect_scope_violations(sources, files)
        assert any("DIFFERENT" in v for v in violations), violations

    def test_family_markers_are_detected_in_pytestmark_lists(self):
        files = {
            "hub/apps/x/tests/test_a.py": (
                "pytestmark = [pytest.mark.django_db, pytest.mark.integration]\n"
            )
        }
        assert "integration" in markers_in_use(files)

    def test_e2e_with_digits_is_detected(self):
        files = {"hub/apps/x/tests/test_a.py": "@pytest.mark.e2e\n"}
        assert "e2e" in markers_in_use(files)

    def test_public_overlay_workflow_must_agree_too(self):
        """The public tree's ci-core.yml is a THIRD copy of the -m scope —
        it drifted to the old expression once already; parity must cover
        all three sources."""
        files = {"hub/apps/x/tests/test_a.py": "pytest.mark.integration\n"}
        sources = {
            "Makefile.core": MAKEFILE_STUB.format(expression='"not e2e and not integration"'),
            "ci.yml": WORKFLOW_STUB.format(expression='"not e2e and not integration"'),
            "public ci-core.yml": WORKFLOW_STUB.format(
                expression='"not e2e and not integration and not requires_fuseki"'
            ),
        }
        violations = collect_scope_violations(sources, files)
        assert any("DIFFERENT" in v for v in violations), violations


class TestRealRepo:
    def test_real_repo_is_scope_clean(self):
        """The RED→GREEN driver: after the expression fix, the real
        Makefile.core + ci.yml must agree with the real marker inventory."""
        from check_core_test_scope import load_real_sources, real_marker_files

        violations = collect_scope_violations(load_real_sources(), real_marker_files())
        assert violations == [], "\n".join(violations)
