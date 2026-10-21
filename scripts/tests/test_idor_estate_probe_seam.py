"""P0-4 (close-oss-release-conditions) — the IDOR estate-probe-creator seam
pins (Django-free, CI no-django lint).

The W11.3 IDOR synthesis engine is provider-agnostic; its ONLY estate
coupling was the ``DatabricksWorkspace`` probe creator, imported
directly from ``hub.apps.databricks_admin.models`` — the GATE-54
violation. The root fix is the W4.6 registry inversion: the creator
lives WITH the estate (``databricks_admin/e2e_tooling/``), the
provider-agnostic seam module defines the consumer side only, and the
estate registers at app-ready.

These pins enforce the seam contract (the same shape as
``test_w46_provider_seams_standalone.py``):

* the seam resolves None when no provider registered (the W4.6
  unregistered default — the core-only process has no estate models,
  so the key is never consulted there);
* register/get round-trips the REAL callable (plain registry, no mocks);
* the refusal shape is classified — ``EstateProbeCreatorUnregistered``
  exists and the synthesis wrapper uses it (a missing registration in
  an estate-installed process fails LOUD, never a silent generic
  fallback);
* the synthesis engine carries NO estate import (AST check — the
  checker's own rule, pinned here against regrowth);
* the estate fixture factory lives in ``databricks_admin/e2e_tooling/``
  and ``apps.py::ready()`` registers it (the W4.6 owning-app
  convention);
* ``scripts/check_provider_boundary.py`` exits 0 (the authoritative
  GATE-54 gate — the seam is not real until the checker agrees).
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SEAM = REPO_ROOT / "hub" / "apps" / "testing" / "estate_probe_creators.py"
SYNTH = REPO_ROOT / "hub" / "apps" / "testing" / "idor_synthesis.py"
FIXTURES = REPO_ROOT / "hub" / "apps" / "databricks_admin" / "e2e_tooling" / "idor_probe_fixtures.py"
APPS = REPO_ROOT / "hub" / "apps" / "databricks_admin" / "apps.py"
WORKSPACE_KEY = "databricks_admin.DatabricksWorkspace"


def _text(path: Path) -> str:
    assert path.is_file(), f"expected committed artifact: {path}"
    return path.read_text(encoding="utf-8")


def _imports(path: Path) -> set[str]:
    tree = ast.parse(_text(path))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_seam_resolves_none_when_unregistered():
    from hub.apps.testing.estate_probe_creators import get_estate_probe_creator

    assert get_estate_probe_creator(WORKSPACE_KEY) is None


def test_seam_register_get_round_trips_the_real_callable():
    from hub.apps.testing.estate_probe_creators import (
        get_estate_probe_creator,
        register_estate_probe_creator,
    )

    def real_creator(tenant, user):
        return (tenant, user)

    register_estate_probe_creator(WORKSPACE_KEY, real_creator)
    assert get_estate_probe_creator(WORKSPACE_KEY) is real_creator
    # the registered state is process-global by design (app-ready
    # registration); reset to the bare default so the OTHER tests keep
    # seeing the unregistered shape.
    from hub.apps.testing import estate_probe_creators as seam

    seam._registered_creators.pop(WORKSPACE_KEY, None)
    assert get_estate_probe_creator(WORKSPACE_KEY) is None


def test_refusal_shape_is_classified():
    seam_source = _text(SEAM)
    assert "class EstateProbeCreatorUnregistered" in seam_source, (
        "the seam must define the classified refusal"
    )
    assert "EstateProbeCreatorUnregistered" in _text(SYNTH), (
        "the synthesis wrapper must raise the classified refusal, never a "
        "silent generic fallback"
    )


def test_synthesis_engine_carries_no_estate_import():
    for name in _imports(SYNTH):
        assert "databricks_admin" not in name, (
            f"idor_synthesis.py imports {name!r} — the GATE-54 violation shape"
        )
    for name in _imports(SEAM):
        assert "databricks_admin" not in name, (
            f"the seam module imports {name!r} — consumer side only"
        )


_PAID_APPS = ("billing", "marketplace", "ml", "baas", "semantic")


def test_synthesis_engine_carries_no_paid_imports():
    """P2-3 (GATE-29 boundary debt): the IDOR engine's paid-object
    creators live WITH the paid apps and register through the probe
    seam — the synthesis engine imports no paid module directly (the
    same inversion shape as the estate coupling)."""
    for name in _imports(SYNTH):
        for app in _PAID_APPS:
            assert app not in name, (
                f"idor_synthesis.py imports {name!r} — the paid boundary "
                "violation shape (P2-3 root fix: creators register through "
                "the probe seam from their owning app)"
            )


def test_paid_creator_modules_register_through_the_seam():
    for app in ("billing", "marketplace", "ml", "baas"):
        module = REPO_ROOT / "hub" / "apps" / app / "idor_probe_creators.py"
        assert module.exists(), f"{app}/idor_probe_creators.py missing"
        source = _text(module)
        assert "register_probe_creator" in source, (
            f"{app}/idor_probe_creators.py must register through the seam"
        )
        apps_source = _text(REPO_ROOT / "hub" / "apps" / app / "apps.py")
        assert "idor_probe_creators" in apps_source, (
            f"{app}/apps.py ready() must import the probe creators "
            "(the owning-app convention)"
        )
        assert "idor_probe_creators.register()" in apps_source, (
            f"{app}/apps.py ready() must CALL the registration"
        )


def test_synthesis_wrappers_raise_when_unregistered():
    """The 6 paid wrappers must raise the classified refusal when the
    owning app never registered — loud, never a silent generic fallback
    (the W4.6 default shape)."""
    import importlib.util

    # The synthesis engine imports the seam through the hub package path
    # (a different module instance than this direct load), so the pin
    # asserts the CLASSIFIED SHAPE by name — the refusal must be loud
    # and named, never a silent generic fallback.
    spec = importlib.util.spec_from_file_location("idor_under_test", SYNTH)
    idor = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(idor)
    wrappers = [
        "_create_subscription",
        "_create_draft_listing",
        "_create_order",
        "_create_published_listing",
        "_create_ab_test",
        "_create_baas_api_key",
    ]
    for wrapper in wrappers:
        fn = getattr(idor, wrapper)
        raised = None
        try:
            fn(object(), object())
        except Exception as exc:  # noqa: BLE001 — the pin checks the refusal name
            raised = type(exc).__name__
        assert raised == "ProbeCreatorUnregistered", (
            f"{wrapper} did not raise ProbeCreatorUnregistered "
            f"(got {raised!r})"
        )


def test_estate_fixture_lives_with_the_estate_and_registers_at_ready():
    fixtures_source = _text(FIXTURES)
    assert f'"{WORKSPACE_KEY}"' in fixtures_source, (
        "the estate fixture module must register the workspace creator key"
    )
    assert "def create_probe_databricks_workspace" in fixtures_source, (
        "the estate fixture module must own the real creator"
    )
    assert "register_estate_probe_creator" in fixtures_source, (
        "the fixture module must register through the seam"
    )
    apps_source = _text(APPS)
    assert "idor_probe_fixtures" in apps_source, (
        "apps.py ready() must import the estate probe fixtures (W4.6 convention)"
    )
    assert "idor_probe_fixtures.register()" in apps_source, (
        "apps.py ready() must CALL the registration (the W4.6 owning-app "
        "convention — an import-only ready() would silently leave the "
        "seam unregistered)"
    )


def test_gate54_exits_zero():
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "check_provider_boundary.py")],
        capture_output=True,
        text=True,
        check=False,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0, (
        "GATE-54 not clean:\n" + result.stdout[-2000:] + result.stderr[-2000:]
    )
