"""Phase 6 (openspec wire-databricks-dlt-movement task 6.7) — the F3
dependency-pin coherence contract (design D7).

The friction (F3 — the umbrella proposal's residual-risk register):
``databricks-sql-connector`` genuinely requires ``pandas<2.3``, while
dlt's arrow-needing extras declare ``pyarrow>=16`` — above the repo's
``pyarrow>=14.0.1,<15.0.0`` ceiling on py<3.13. The resolution is the
pinned compatible set — ``pandas>=2.2.0,<2.3.0`` (connector-required),
``pyarrow>=14.0.1,<15.0.0`` on py<3.13 (the floor from the connector,
the ceiling the repo's coherence guard), plain ``dlt>=1.0,<2.0`` with
NO arrow-needing extras — and THIS suite keeps the set coherent: pin
drift, an extras addition, or an installed-environment violation fails
here with an actionable message.

No DB, no mocks: file-content contracts over the real requirement files
+ declared-constraint contracts over the installed distribution metadata
(the 5.6 requirement-pin suite convention).
"""

from __future__ import annotations

import importlib.metadata
import sys
from pathlib import Path

import pytest
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.version import Version

_REPO_ROOT = Path(__file__).resolve().parents[3]
_REQ_FILES = [_REPO_ROOT / "requirements.txt", _REPO_ROOT / "requirements-core.txt"]

# The F3 pin set — requirement name → exact specifier string (canonical).
# Both requirement files must declare these identically.
F3_PINS: dict[str, str] = {
    "pandas": ">=2.2.0,<2.3.0",
    "dlt": ">=1.0,<2.0",
    "databricks-sql-connector": ">=3.0,<4.0",
}
F3_PYARROW_LEGACY = ">=14.0.1,<15.0.0"  # py<3.13 leg
F3_PYARROW_MODERN = ">=22.0.0"  # py>=3.13 leg
F3_NUMPY_LEGACY = "==1.26.4"  # py<3.13 leg
F3_NUMPY_MODERN = ">=2.5.0,<3.0.0"  # py>=3.13 leg


def _requirements_by_name(path: Path) -> dict[str, list[Requirement]]:
    """Parse a requirement file into name → [Requirement] (5.6 style:
    every non-comment line must parse — a broken line fails the suite)."""
    result: dict[str, list[Requirement]] = {}
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        line = line.split(" #", 1)[0].strip()  # inline comments
        req = Requirement(line)
        result.setdefault(req.name.lower(), []).append(req)
    return result


def _active_leg(requirements: list[Requirement]) -> Requirement:
    """The pin leg whose marker matches the ACTIVE interpreter — a pin
    name with a leg for every supported python must resolve to exactly
    one leg here (no leg means the pin does not cover this python)."""
    active = [r for r in requirements if r.marker is None or r.marker.evaluate()]
    assert len(active) == 1, (
        f"expected exactly one active leg for {requirements[0].name!r} on "
        f"python {sys.version_info.major}.{sys.version_info.minor}, got {len(active)}"
    )
    return active[0]


def _installed_version(name: str) -> Version:
    try:
        return Version(importlib.metadata.version(name))
    except importlib.metadata.PackageNotFoundError as exc:
        raise AssertionError(
            f"{name} is pinned in the requirement files but not installed"
        ) from exc


class TestF3PinDeclaration:
    """The pinned compatible set exists, identically, in BOTH requirement
    files — requirements-core is the runtime superset's subset profile and
    must stay coherent by construction."""

    @pytest.mark.parametrize("path", _REQ_FILES, ids=lambda p: p.name)
    def test_the_f3_trio_is_declared_with_the_canonical_specifiers(self, path):
        parsed = _requirements_by_name(path)
        for name, specifier in F3_PINS.items():
            reqs = parsed.get(name)
            assert reqs, f"{path.name} declares no {name} pin"
            assert len(reqs) == 1, f"{path.name} declares {len(reqs)} {name} pins — one expected"
            assert reqs[0].specifier == SpecifierSet(specifier), (
                f"{path.name}: the {name} pin drifted from the F3 resolution: "
                f"{reqs[0].specifier} != {specifier}"
            )
        # dlt rides the pin WITHOUT extras — the arrow-needing extras are
        # excluded by design (see TestArrowExtrasGuard).
        assert not parsed["dlt"][0].extras, "the dlt pin must carry no extras (F3)"

    def test_pyarrow_and_numpy_carry_both_python_legs(self):
        # The runtime file carries the python-version-aware matrix; the
        # core profile (a subset) carries its own simpler pins — the
        # profile-coherence contract pins those separately below.
        path = _REQ_FILES[0]
        parsed = _requirements_by_name(path)
        pyarrow_legacy = [r for r in parsed["pyarrow"] if r.marker and '< "3.13"' in str(r.marker)]
        pyarrow_modern = [r for r in parsed["pyarrow"] if r.marker and '>= "3.13"' in str(r.marker)]
        # Both legs exist with the canonical specifiers.
        assert any(r.specifier == SpecifierSet(F3_PYARROW_LEGACY) for r in pyarrow_legacy), (
            f"{path.name}: the py<3.13 pyarrow leg drifted from {F3_PYARROW_LEGACY}"
        )
        assert any(r.specifier == SpecifierSet(F3_PYARROW_MODERN) for r in pyarrow_modern), (
            f"{path.name}: the py>=3.13 pyarrow leg drifted from {F3_PYARROW_MODERN}"
        )
        numpy_legacy = [r for r in parsed["numpy"] if r.specifier == SpecifierSet(F3_NUMPY_LEGACY)]
        numpy_modern = [r for r in parsed["numpy"] if r.specifier == SpecifierSet(F3_NUMPY_MODERN)]
        assert numpy_legacy, f"{path.name}: the py<3.13 numpy leg drifted from {F3_NUMPY_LEGACY}"
        assert numpy_modern, f"{path.name}: the py>=3.13 numpy leg drifted from {F3_NUMPY_MODERN}"

    def test_the_core_profiles_active_legs_match_the_runtime_profile(self):
        """requirements-core is the runtime superset's subset profile: for
        the interpreter running this suite, the core file's ACTIVE leg for
        pyarrow and numpy must carry the same specifier as the runtime
        file's — a core/runtime split would install two different sets."""
        runtime = _requirements_by_name(_REQ_FILES[0])
        core = _requirements_by_name(_REQ_FILES[1])
        for name in ("pyarrow", "numpy"):
            runtime_active = _active_leg(runtime[name])
            core_active = _active_leg(core[name])
            assert core_active.specifier == runtime_active.specifier, (
                f"{name}: the core profile's active pin {core_active.specifier} drifted "
                f"from the runtime profile's {runtime_active.specifier} on python "
                f"{sys.version_info.major}.{sys.version_info.minor}"
            )


class TestInstalledEnvironmentCoherence:
    """The installed environment satisfies the F3 pins — the drift catcher
    (a ``pip install`` that lifts pandas/pyarrow past the pins fails here)."""

    def test_the_installed_versions_satisfy_the_active_pin_legs(self):
        for path in _REQ_FILES:
            parsed = _requirements_by_name(path)
            for name in [*F3_PINS, "pyarrow", "numpy"]:
                active = _active_leg(parsed[name])
                installed = _installed_version(name)
                assert installed in active.specifier, (
                    f"installed {name} {installed} violates the {path.name} pin "
                    f"{active.specifier} on python {sys.version_info.major}."
                    f"{sys.version_info.minor} — the F3 set drifted; reinstall "
                    f"the pinned set"
                )


class TestConnectorConstraintIntersection:
    """The connector's DECLARED constraints (the installed distribution
    metadata — the real source of the F3 friction) intersect the repo
    pins, and the installed versions satisfy both sides."""

    def test_the_connectors_declared_ranges_intersect_the_pins(self):
        connector_reqs = importlib.metadata.requires("databricks-sql-connector") or []
        for name in ("pandas", "pyarrow", "numpy"):
            declared = [
                Requirement(r)
                for r in connector_reqs
                if Requirement(r).name.lower() == name
                and (Requirement(r).marker is None or Requirement(r).marker.evaluate())
            ]
            assert declared, f"databricks-sql-connector declares no {name} constraint"
            connector_set = declared[0].specifier
            for extra in declared[1:]:
                connector_set = connector_set & extra.specifier
            pin = _active_leg(_requirements_by_name(_REQ_FILES[0])[name])
            intersection = SpecifierSet(connector_set) & SpecifierSet(pin.specifier)
            assert intersection, (
                f"the connector's {name} constraint {connector_set} does NOT intersect "
                f"the repo pin {pin.specifier} — the F3 set is incoherent"
            )
            installed = _installed_version(name)
            assert installed in connector_set, (
                f"installed {name} {installed} violates the connector's constraint {connector_set}"
            )


class TestDltCoreCoherence:
    """dlt core rides the pinned set: it declares no pandas/pyarrow/numpy
    requirement of its own (verified against the installed metadata) and
    imports + resolves the movement's staging destination on it."""

    def test_dlt_core_declares_no_arrow_pins_and_imports_on_the_pinned_set(self):
        dlt_reqs = importlib.metadata.requires("dlt") or []
        core = [
            Requirement(r)
            for r in dlt_reqs
            if (Requirement(r).marker is None or Requirement(r).marker.evaluate())
        ]
        for name in ("pandas", "pyarrow", "numpy"):
            assert all(r.name.lower() != name for r in core), (
                f"dlt core declares a {name} requirement — the F3 set must be "
                f"re-verified against the pinned dlt"
            )
        import dlt

        assert dlt.destinations.filesystem is not None, (
            "the movement staging destination must resolve on the pinned set"
        )


class TestArrowExtrasGuard:
    """The F3 exclusion contract: every dlt extra whose pyarrow floor
    exceeds the repo's active pyarrow ceiling is INCOMPATIBLE with the
    pin set — the repo's dlt pin must not declare any of them."""

    def test_no_arrow_needing_dlt_extra_is_declared_on_the_pin(self):
        # The active pyarrow ceiling (None when the active leg has no upper).
        pin = _active_leg(_requirements_by_name(_REQ_FILES[0])["pyarrow"])
        ceiling = None
        for spec in pin.specifier:
            if spec.operator in ("<", "<="):
                ceiling = Version(spec.version)
        floor_overflow: dict[str, Version] = {}
        if ceiling is not None:
            dlt_reqs = importlib.metadata.requires("dlt") or []
            for raw in dlt_reqs:
                req = Requirement(raw)
                extra = set(req.extras)
                if req.name.lower() != "pyarrow" or not extra:
                    continue
                floor = None
                for spec in req.specifier:
                    if spec.operator in (">=", ">"):
                        candidate = Version(spec.version)
                        floor = candidate if floor is None or candidate > floor else floor
                if floor is not None and floor > ceiling:
                    for e in extra:
                        floor_overflow.setdefault(e, floor)
        dlt_pin = _requirements_by_name(_REQ_FILES[0])["dlt"][0]
        declared = set(dlt_pin.extras)
        conflicting = sorted(floor_overflow.keys() & declared)
        assert not conflicting, (
            f"the dlt pin declares the arrow-needing extras {conflicting} — each "
            f"requires pyarrow above the repo ceiling {ceiling} (F3). Raise the "
            f"pyarrow pin on py<3.13 in BOTH requirement files first, then add "
            f"the extra"
        )


class TestF3CommentContracts:
    """The pin comments carry the verified WHY (the 5.6 comment-pin
    convention) — so the next engineer sees the F3 resolution at the pin."""

    @pytest.mark.parametrize("path", _REQ_FILES, ids=lambda p: p.name)
    def test_the_pandas_pin_comment_cites_the_connector(self, path):
        line = next(
            raw for raw in path.read_text().splitlines() if raw.strip().startswith("pandas")
        )
        assert "databricks-sql-connector" in line, (
            f"{path.name}: the pandas pin comment must cite the connector "
            f"constraint that forces <2.3"
        )

    @pytest.mark.parametrize("path", _REQ_FILES, ids=lambda p: p.name)
    def test_the_pyarrow_pin_comment_records_the_f3_resolution(self, path):
        line = next(
            raw
            for raw in path.read_text().splitlines()
            if raw.strip().startswith("pyarrow") and "<15.0" in raw
        )
        for token in ("F3", "wire-databricks-dlt-movement", "dlt"):
            assert token in line, (
                f"{path.name}: the py<3.13 pyarrow pin comment must record the F3 "
                f"resolution ({token} missing)"
            )
