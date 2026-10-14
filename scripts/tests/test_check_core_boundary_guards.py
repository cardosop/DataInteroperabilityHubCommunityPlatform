"""Tests for the guard classification layer of check_core_boundary.py (313.H.1).

Every allowlisted core-site paid import must survive BOTH core failure
modes: ``RuntimeError`` (private repo, app uninstalled) and
``ModuleNotFoundError`` (public tree, module absent). The guard checker
classifies each site as:

  try-covered-BROKEN — an enclosing try whose handler covers BOTH failure
                     modes (incl. ``except Exception``)
  try-not-covered  — enclosing try, but handlers miss one failure mode
  branch-guarded   — import sits in a branch that only runs in FULL mode
                     (``if not HUB_CORE_ONLY`` / ``else`` of a core branch)
  annotated        — ``# core-guard: full-mode-only — <proof>`` with a
                     non-empty caller-chain proof
  unguarded        — none of the above (fails the gate unless baselined)

No mocks: synthetic sources are parsed with the real ast module and run
through the real classifier; integration cases scan real temp trees with
a minimal manifest.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import ClassVar

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from check_core_boundary import (
    _build_parent_map,
    classify_import_guard,
    guard_check,
)


def _classify(source: str) -> str:
    """Parse a snippet and classify its FIRST paid import node."""
    tree = ast.parse(source)
    node = next(
        n
        for n in ast.walk(tree)
        if (isinstance(n, ast.ImportFrom) and "semantic" in (n.module or ""))
        or (isinstance(n, ast.Import) and any("semantic" in a.name for a in n.names))
    )
    return classify_import_guard(tree, node, source.splitlines())


# ── Unit: try-handler coverage ────────────────────────────────────────────────


class TestTryHandlerCoverage:
    def test_guarded_both_exceptions(self):
        src = """
def f():
    try:
        from hub.apps.semantic.models import Thing
    except (RuntimeError, ModuleNotFoundError):
        Thing = None
"""
        assert _classify(src) == "try-covered-BROKEN"

    def test_except_exception_is_covering(self):
        src = """
def f():
    try:
        from hub.apps.semantic.models import Thing
    except Exception:
        Thing = None
"""
        assert _classify(src) == "try-covered-BROKEN"

    def test_import_error_only_is_not_covering(self):
        # ModuleNotFoundError IS an ImportError — but RuntimeError is not,
        # so this guard misses the private-repo core-mode failure.
        src = """
def f():
    try:
        from hub.apps.semantic.models import Thing
    except ImportError:
        Thing = None
"""
        assert _classify(src) == "try-not-covered"

    def test_runtime_error_only_is_not_covering(self):
        # The round-5/6 class of public-crash latents.
        src = """
def f():
    try:
        from hub.apps.semantic.models import Thing
    except RuntimeError:
        Thing = None
"""
        assert _classify(src) == "try-not-covered"

    def test_import_error_plus_runtime_error_covers(self):
        src = """
def f():
    try:
        from hub.apps.semantic.models import Thing
    except (ImportError, RuntimeError):
        Thing = None
"""
        assert _classify(src) == "try-covered-BROKEN"

    def test_bare_except_covers(self):
        src = """
def f():
    try:
        from hub.apps.semantic.models import Thing
    except:
        Thing = None
"""
        assert _classify(src) == "try-covered-BROKEN"

    def test_try_without_handlers_is_not_covered(self):
        src = """
def f():
    try:
        from hub.apps.semantic.models import Thing
    finally:
        pass
"""
        assert _classify(src) == "try-no-except"

    def test_outer_covering_try_beats_inner_non_covering(self):
        # An inner business-logic try (except ValueError) must not mask an
        # outer try/except covering both core failure modes.
        src = """
def f():
    try:
        try:
            from hub.apps.semantic.models import Thing
        except ValueError:
            pass
    except (RuntimeError, ModuleNotFoundError):
        Thing = None
"""
        assert _classify(src) == "try-covered-BROKEN"


# ── Unit: branch guards ───────────────────────────────────────────────────────


class TestBranchGuards:
    def test_if_not_hub_core_only_is_guarded(self):
        src = """
def f():
    if not settings.HUB_CORE_ONLY:
        from hub.apps.semantic.models import Thing
    return 1
"""
        assert _classify(src) == "branch-guarded"

    def test_if_not_is_core_only_is_guarded(self):
        src = """
def f():
    if not is_core_only():
        from hub.apps.semantic.models import Thing
"""
        assert _classify(src) == "branch-guarded"

    def test_else_branch_of_core_if_is_guarded(self):
        src = """
def f():
    if settings.HUB_CORE_ONLY:
        return None
    else:
        from hub.apps.semantic.models import Thing
"""
        assert _classify(src) == "branch-guarded"

    def test_body_of_core_if_is_unguarded(self):
        # The import RUNS in core mode — the wrong branch.
        src = """
def f():
    if settings.HUB_CORE_ONLY:
        from hub.apps.semantic.models import Thing
"""
        assert _classify(src) == "unguarded"

    def test_else_branch_of_not_core_if_is_unguarded(self):
        src = """
def f():
    if not settings.HUB_CORE_ONLY:
        return None
    else:
        from hub.apps.semantic.models import Thing
"""
        assert _classify(src) == "unguarded"

    def test_outer_core_branch_beats_inner_guard(self):
        # Fail-safe: if ANY enclosing flagged branch runs in core mode,
        # the site is unguarded even when an inner branch is full-mode-only.
        src = """
def f():
    if settings.HUB_CORE_ONLY:
        if not settings.HUB_CORE_ONLY:
            from hub.apps.semantic.models import Thing
"""
        assert _classify(src) == "unguarded"

    def test_else_of_truthy_comparison_is_guarded(self):
        # `HUB_CORE_ONLY == "1"` is a core-true test — its else branch is
        # full-mode-only.
        src = """
def f():
    if settings.HUB_CORE_ONLY == "1":
        return None
    else:
        from hub.apps.semantic.models import Thing
"""
        assert _classify(src) == "branch-guarded"

    def test_body_of_truthy_comparison_is_unguarded(self):
        src = """
def f():
    if settings.HUB_CORE_ONLY == "1":
        from hub.apps.semantic.models import Thing
"""
        assert _classify(src) == "unguarded"

    def test_environ_get_pattern_is_guarded(self):
        # os.environ.get("HUB_CORE_ONLY") != "1" is the root conftest's own
        # core-off test.
        src = """
def f():
    if os.environ.get("HUB_CORE_ONLY") != "1":
        from hub.apps.semantic.models import Thing
"""
        assert _classify(src) == "branch-guarded"


# ── Unit: annotations ─────────────────────────────────────────────────────────


class TestAnnotations:
    def test_annotated_with_proof(self):
        src = """
def f():
    # core-guard: full-mode-only — called only from paid views (see caller audit)
    from hub.apps.semantic.models import Thing
"""
        assert _classify(src) == "annotated"

    def test_annotated_without_proof_is_unguarded(self):
        src = """
def f():
    # core-guard: full-mode-only —
    from hub.apps.semantic.models import Thing
"""
        assert _classify(src) == "unguarded"

    def test_no_annotation_is_unguarded(self):
        src = """
def f():
    from hub.apps.semantic.models import Thing
"""
        assert _classify(src) == "unguarded"


# ── Unit: both import forms ───────────────────────────────────────────────────


class TestImportForms:
    def test_import_statement_form(self):
        src = """
def f():
    try:
        import hub.apps.semantic.models
    except (RuntimeError, ModuleNotFoundError):
        pass
"""
        assert _classify(src) == "try-covered-BROKEN"

    def test_import_statement_unguarded(self):
        src = """
def f():
    import hub.apps.semantic.models
"""
        assert _classify(src) == "unguarded"


# ── Integration: gate layer over a real temp tree ─────────────────────────────


MANIFEST_SRC = """
_PAID_MODULES = frozenset(
    {
        "hub.apps.semantic",
        "hub.apps.billing",
    }
)
ALL_HUB_APPS = (
    "hub.apps.core",
    "hub.apps.tenants",
)
"""


def _build_tree(tmp_path: Path) -> Path:
    """Minimal core tree: manifest + core files with paid imports."""
    (tmp_path / "hub" / "apps").mkdir(parents=True)
    (tmp_path / "hub" / "apps" / "manifest.py").write_text(MANIFEST_SRC)
    core = tmp_path / "hub" / "apps" / "core"
    core.mkdir(parents=True)
    (core / "__init__.py").write_text("")
    return tmp_path


class TestGateLayer:
    def test_guarded_site_passes(self, tmp_path):
        root = _build_tree(tmp_path)
        (root / "hub" / "apps" / "core" / "guarded_mod.py").write_text(
            """
def f():
    try:
        from hub.apps.semantic.models import Thing
    except (RuntimeError, ModuleNotFoundError):
        Thing = None
"""
        )
        allowlist = {"hub/apps/core/guarded_mod.py:4"}
        violations, implicit = guard_check(root, allowlist, set())
        assert violations == []
        assert implicit == []

    def test_unguarded_allowlisted_site_fails(self, tmp_path):
        root = _build_tree(tmp_path)
        (root / "hub" / "apps" / "core" / "bad.py").write_text(
            "from hub.apps.semantic.models import Thing\n"
        )
        allowlist = {"hub/apps/core/bad.py:1"}
        violations, _ = guard_check(root, allowlist, set())
        assert any("bad.py:1" in v for v in violations)

    def test_unguarded_but_baselined_passes(self, tmp_path):
        root = _build_tree(tmp_path)
        (root / "hub" / "apps" / "core" / "bad.py").write_text(
            "from hub.apps.semantic.models import Thing\n"
        )
        allowlist = {"hub/apps/core/bad.py:1"}
        baseline = {"hub/apps/core/bad.py:1"}
        violations, _ = guard_check(root, allowlist, baseline)
        assert violations == []

    def test_test_module_is_exempt(self, tmp_path):
        root = _build_tree(tmp_path)
        (root / "hub" / "apps" / "core" / "test_semantic.py").write_text(
            "from hub.apps.semantic.models import Thing\n"
        )
        allowlist = {"hub/apps/core/test_semantic.py:1"}
        violations, _ = guard_check(root, allowlist, set())
        assert violations == []

    def test_conftest_is_not_exempt(self, tmp_path):
        root = _build_tree(tmp_path)
        (root / "hub" / "apps" / "core" / "conftest.py").write_text(
            "from hub.apps.semantic.models import Thing\n"
        )
        allowlist = {"hub/apps/core/conftest.py:1"}
        violations, _ = guard_check(root, allowlist, set())
        assert any("conftest.py:1" in v for v in violations)

    def test_paid_dir_file_is_never_scanned(self, tmp_path):
        root = _build_tree(tmp_path)
        (root / "hub" / "apps" / "semantic").mkdir(parents=True)
        (root / "hub" / "apps" / "semantic" / "models.py").write_text(
            "from hub.apps.billing.models import Sub\n"
        )
        (root / "hub" / "apps" / "core" / "clean.py").write_text("x = 1\n")
        allowlist = {"hub/apps/core/clean.py:1"}
        violations, _ = guard_check(root, allowlist, set())
        assert violations == []

    def test_publish_excluded_file_is_skipped(self, tmp_path):
        # Private-only tooling (publish_paths_exclude.txt) never ships —
        # the guard gate must not govern it (313.H.2.3).
        root = _build_tree(tmp_path)
        (root / "scripts").mkdir(parents=True)
        (root / "scripts" / "publish_paths_exclude.txt").write_text(
            "# generated\nscripts/private_tool.py\n"
        )
        (root / "scripts" / "private_tool.py").write_text(
            "from hub.apps.semantic.models import Thing\n"
        )
        allowlist = {"scripts/private_tool.py:1"}
        violations, _ = guard_check(root, allowlist, set())
        assert violations == []

    def test_negated_publish_path_is_still_checked(self, tmp_path):
        # "!prefix" negations re-include files — those MUST stay governed.
        root = _build_tree(tmp_path)
        (root / "scripts").mkdir(parents=True)
        (root / "scripts" / "publish_paths_exclude.txt").write_text(
            "# generated\nscripts/tools/\n!scripts/tools/public_tool.py\n"
        )
        (root / "scripts" / "tools").mkdir(parents=True)
        (root / "scripts" / "tools" / "public_tool.py").write_text(
            "from hub.apps.semantic.models import Thing\n"
        )
        allowlist = {"scripts/tools/public_tool.py:1"}
        violations, _ = guard_check(root, allowlist, set())
        assert any("public_tool.py:1" in v for v in violations)

    def test_prefer_explicit_reports_except_exception(self, tmp_path):
        root = _build_tree(tmp_path)
        (root / "hub" / "apps" / "core" / "implicit.py").write_text(
            """
def f():
    try:
        from hub.apps.semantic.models import Thing
    except Exception:
        Thing = None
"""
        )
        allowlist = {"hub/apps/core/implicit.py:4"}
        violations, implicit = guard_check(root, allowlist, set(), prefer_explicit=True)
        assert violations == []
        assert any("implicit.py:4" in v for v in implicit)

    def test_parent_map_builds(self):
        tree = ast.parse("def f():\n    return 1\n")
        parents = _build_parent_map(tree)
        fn = tree.body[0]
        ret = fn.body[0]
        assert parents[ret] is fn
        assert parents[fn] is tree


# ── Real-repo regressions: 313.H.2 guards, 313.H.3 hook conversions.
#    The ratchet proof lives here: converted sites must not reappear as
#    paid imports, the baseline must stay empty, and residual guarded
#    sites must classify correctly (line-shift-proof — lines are looked
#    up dynamically from the source). ──────────────────────────────────────


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_BASELINE = REPO_ROOT / "scripts" / "core_guard_exceptions.txt"


class ImportSiteNotFound(ValueError):
    """No import statement exists at the requested allowlist site.

    The previous failure mode here was a bare ``StopIteration`` leaking out
    of ``next(...)`` — when a guard-converted site disappeared from the
    source, the suite died with an unrelated generator traceback that did
    not even name the vanished site. A named error with the site in the
    message turns that regression into a one-line diagnosis.
    """


def _classify_real_file(relpath: str, lineno: int) -> str:
    path = REPO_ROOT / relpath
    source = path.read_text()
    tree = ast.parse(source)
    try:
        node = next(
            n
            for n in ast.walk(tree)
            if isinstance(n, (ast.Import, ast.ImportFrom)) and n.lineno == lineno
        )
    except StopIteration as exc:
        raise ImportSiteNotFound(
            f"no import statement at allowlist site {relpath}:{lineno} — "
            "the site was converted, moved, or deleted; update the "
            "guard-fixture site (line-shift-proof lookups only) or the "
            "allowlist"
        ) from exc
    return classify_import_guard(tree, node, source.splitlines())


def _source_of(relpath: str) -> str:
    return (REPO_ROOT / relpath).read_text()


def _import_lines(relpath: str, needle: str) -> list[int]:
    """Line numbers (1-based) of import statements containing ``needle``."""
    return [
        i + 1
        for i, line in enumerate(_source_of(relpath).splitlines())
        if needle in line and ("import" in line)
    ]


def _baseline_keys() -> set[str]:
    return {
        ln.split(":", 2)[0] + ":" + ln.split(":", 2)[1]
        for ln in _BASELINE.read_text().splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    }


class TestBaselineShrink313H2:
    """The production try-not-covered sites (313.H.2.1) must be guarded
    with handlers that cover BOTH core failure modes. (313.H.3 later
    hook-converted the virtualization one — see TestH3HookConversions.)"""

    SITES: ClassVar[list[str]] = [
        "hub/apps/contracts/cache_invalidation.py:165",
        # The campaign's hub edits shifted these sites (W3.4's 2477→2479→2478
        # history plus pilot-1.2's import-sort pass); the try-covered import
        # guards themselves are unchanged.  W7.1 re-anchored the drifted
        # lines (166→165, 2522→2539).
        "hub/apps/assets/views.py:2539",
    ]

    @pytest.mark.parametrize("site", SITES)
    def test_site_classifies_try_covered(self, site):
        relpath, lineno = site.rsplit(":", 1)
        assert _classify_real_file(relpath, int(lineno)) == "try-covered-BROKEN"

    def test_sites_left_the_baseline(self):
        for site in self.SITES:
            assert site not in _baseline_keys(), f"{site} should no longer be baselined"


# ── 313.H.3: hook conversions must have REMOVED the paid imports. The
#    strongest ratchet proof is source-level: the import strings are gone,
#    so the gate no longer even sees these sites. ─────────────────────────


class TestH3HookConversions:
    """Every 313.H.3-converted site lost its paid import (hooks inversion)."""

    REMOVED: ClassVar[dict[str, list[str]]] = {
        # Batch 1
        "hub/apps/compliance/signals.py": [
            "from hub.apps.marketplace.caching import",
            "from hub.apps.marketplace.models import Listing",
        ],
        "hub/apps/tenants/views.py": [
            "from hub.apps.marketplace.models import Listing, ListingStatus, PricingModel",
            "from hub.apps.billing.services import",
            "from hub.apps.billing.views import _mask_tax_id",
        ],
        "hub/apps/governance/services.py": [
            "from hub.apps.marketplace.entitlement_utils import create_entitlement_for_order",
            "from hub.apps.marketplace.entitlement_utils import revoke_entitlement_for_order",
            "from hub.apps.marketplace.models import OrderStatus",
        ],
        # Batch 2
        "hub/apps/datasets/views.py": [
            "from hub.apps.marketplace.entitlement_check import",
        ],
        "hub/apps/files/views.py": [
            "from hub.apps.marketplace.entitlement_check import",
        ],
        "hub/apps/contracts/views_product.py": [
            "from hub.apps.marketplace.payment_gateway_service import",
        ],
        "hub/apps/governance/abac.py": [
            "from hub.apps.ml.models import MLModel",
        ],
        "hub/apps/audit/involvement.py": [
            "from hub.apps.marketplace.models import Order",
        ],
        # Batch 3 — virtualization chokepoint + remainder
        "hub/apps/virtualization/_services_legacy.py": [
            "from hub.apps.marketplace.access_utils import check_entitlement",
            "from hub.apps.semantic.service_client import SemanticServiceClient",
        ],
        "hub/apps/virtualization/business_rules.py": [
            "from hub.apps.marketplace.access_utils import check_entitlement",
        ],
        "hub/apps/virtualization/services/query_service.py": [
            "from hub.apps.marketplace.access_utils import check_entitlement",
            "from hub.apps.semantic.service_client import SemanticServiceClient",
        ],
        "hub/apps/orchestration/workflows/virtualization.py": [
            "from hub.apps.semantic.service_client import SemanticServiceClient",
        ],
        "hub/apps/transformation/business_rules.py": [
            "from hub.apps.marketplace.access_utils import check_entitlement",
        ],
        "hub/apps/integrations/_services_legacy.py": [
            "from hub.apps.semantic.utils import map_asset_to_semantic",
            "from hub.apps.semantic.utils import map_odps_to_semantic",
        ],
        "hub/apps/tenants/onboarding.py": [
            "from hub.apps.billing.models import Subscription",
        ],
        "hub/apps/tenants/tax_id_service.py": [
            "from hub.apps.billing.models import Subscription",
        ],
        "hub/apps/tenants/admin_dashboard_summary.py": [
            "from hub.apps.billing.models import Subscription",
        ],
    }

    @pytest.mark.parametrize(
        ("relpath", "needle"),
        [(p, n) for p, needles in REMOVED.items() for n in needles],
    )
    def test_paid_import_removed(self, relpath, needle):
        assert needle not in _source_of(relpath), f"{relpath}: paid import crept back — '{needle}'"

    def test_converted_files_still_reach_the_hooks(self):
        """The inversions are real: the hook surface the converted files
        call exists and is pure (importable without Django side effects)."""
        import inspect

        from hub.apps.core import commercial_hooks

        for name in (
            "check_cross_tenant_entitlement",
            "check_entitlement",
            "finalize_order_approval",
            "finalize_order_rejection",
            "get_admin_billing_summary",
            "get_entitlement_provider",
            "get_file_asset_id",
            "get_ml_model_attributes",
            "get_stripe_customer_id",
            "has_active_billing_setup",
            "invalidate_listing_caches_for_asset",
            "is_order_owner",
            "list_payment_gateways_for_contract",
            "map_via_semantic",
            "revoke_order_entitlement",
            "seed_sample_listing",
            "validate_plan_downgrade",
        ):
            assert inspect.isfunction(getattr(commercial_hooks, name)), name


class TestResidualGuardedSites:
    """Sites that legitimately keep a guarded paid import (paid-by-design
    branches / test-helper degradation) must classify correctly — at
    their CURRENT lines, so line-shifts fail loudly instead of silently."""

    def test_ml_addons_import_stays_branch_guarded(self):
        lines = _import_lines("hub/apps/tenants/views.py", "hub.apps.billing.models")
        assert lines, "ml-addons billing import vanished"
        assert len(lines) == 1, f"expected one billing import line, got {lines}"
        assert _classify_real_file("hub/apps/tenants/views.py", lines[0]) == "branch-guarded"

    def test_tenants_test_factories_import_stays_try_covered(self):
        lines = _import_lines("hub/apps/tenants/tests/factories.py", "hub.apps.billing.models")
        assert lines, "factories billing import vanished"
        assert len(lines) == 1, f"expected one billing import line, got {lines}"
        assert (
            _classify_real_file("hub/apps/tenants/tests/factories.py", lines[0])
            == "try-covered-BROKEN"
        )


class TestTriageBatch1_313H3:
    """313.H.3.1 — batch-1 sites: paid imports removed (see
    TestH3HookConversions) and the guard baseline ratcheted to empty."""

    def test_guard_baseline_is_empty(self):
        assert _baseline_keys() == set(), (
            "the guard baseline must stay empty — every site goes through "
            "the hooks/branch/try-both treatment, never a baseline entry"
        )

    def test_batch1_sites_left_the_baseline(self):
        # Empty-baseline assertion above is the strong form; keep the
        # historical keys here so a reappearance is named explicitly.
        for site in [
            "hub/apps/compliance/signals.py:133",
            "hub/apps/compliance/signals.py:134",
            "hub/apps/tenants/views.py:1214",
            "hub/apps/tenants/views.py:1407",
            "hub/apps/tenants/views.py:1449",
            "hub/apps/tenants/views.py:1616",
            "hub/apps/governance/services.py:353",
            "hub/apps/governance/services.py:355",
            "hub/apps/governance/services.py:744",
            "hub/apps/governance/services.py:834",
        ]:
            assert site not in _baseline_keys(), f"{site} should no longer be baselined"
