"""Compose overlay parity test (task 1.8, 313-H).

The core CI job boots ``docker-compose.test.yml`` +
``docker-compose.test.core.yml`` with default profiles. The overlay excludes
paid services via ``profiles: ["paid-excluded"]``. If a paid service is added
to the test stack WITHOUT the exclusion entry, it silently boots in the core
CI job — importing paid code that does not exist in the public tree, or
crashing the stack outright.

Single source of truth: ``x-paid-services`` in ``docker-compose.test.yml``
(compose ignores ``x-`` extension keys; the test and the overlay both read
it). Adding a paid service therefore REQUIRES touching the list, and this
test fails loudly with the service named if the overlay entry is missing.

No mocks: real YAML parsing of the real files, with synthetic fixtures for
the RED drill (a synthetic unpaid profile entry must fail).
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BASE_COMPOSE = REPO_ROOT / "docker-compose.test.yml"
CORE_OVERLAY = REPO_ROOT / "docker-compose.test.core.yml"


class _ResetLoader(yaml.SafeLoader):
    pass


# The overlay uses compose's ``!reset`` tag (v2.24+) to replace merged maps.
def _reset_constructor(_loader, _node):
    return None


_ResetLoader.add_constructor("!reset", _reset_constructor)


def _load(path: Path):
    return yaml.load(path.read_text(), Loader=_ResetLoader) or {}


def _exclusion_profiles(services: dict) -> set[str]:
    """Service names whose overlay entry carries the paid-excluded profile."""
    return {
        name
        for name, spec in services.items()
        if isinstance(spec, dict) and "paid-excluded" in (spec.get("profiles") or [])
    }


def overlay_parity_violations(
    base_compose: Path = BASE_COMPOSE, overlay: Path = CORE_OVERLAY
) -> list[str]:
    """Names of paid services lacking the exclusion profile in the overlay."""
    base = _load(base_compose)
    core = _load(overlay)

    paid_list = base.get("x-paid-services")
    if not isinstance(paid_list, list) or not paid_list:
        raise ValueError(
            f"{base_compose} must declare x-paid-services (compose x- extension, "
            "the paid-service single source of truth)"
        )

    unknown = [name for name in paid_list if name not in base.get("services", {})]
    if unknown:
        raise ValueError(f"x-paid-services names missing from services: {unknown}")

    excluded = _exclusion_profiles(core.get("services", {}))
    return sorted(name for name in paid_list if name not in excluded)


class TestRealOverlay:
    def test_every_paid_service_carries_the_exclusion_profile(self):
        violations = overlay_parity_violations()
        assert violations == [], (
            "paid service(s) bootable in the core CI job — add "
            '`profiles: ["paid-excluded"]` to docker-compose.test.core.yml: '
            f"{violations}"
        )

    def test_paid_services_list_is_complete_against_the_overlay(self):
        """The reverse direction: every profiled overlay service must be a
        declared paid service (no orphan exclusion entries that hide drift)."""
        base = _load(BASE_COMPOSE)
        core = _load(CORE_OVERLAY)
        paid = set(base["x-paid-services"])
        profiled = _exclusion_profiles(core.get("services", {}))
        orphans = sorted(profiled - paid)
        assert orphans == [], f"overlay excludes services not declared paid: {orphans}"

    def test_core_services_are_not_excluded(self):
        """Core services must remain profile-free (spec: core-only-testing)."""
        core = _load(CORE_OVERLAY)
        excluded = _exclusion_profiles(core.get("services", {}))
        for core_service in ("api-service-test", "worker-service-test"):
            assert core_service not in excluded, f"{core_service} must stay profile-free"


class TestSyntheticFixtures:
    """RED drills over synthetic compose documents — the failure modes the
    real-file assertions above are supposed to catch."""

    @staticmethod
    def _write_synthetic(
        tmp_path: Path,
        *,
        paid_services: list[str],
        excluded: list[str],
        services_extra: dict | None = None,
    ):
        services = {"api-service-test": {"image": "api"}, "postgres-test": {"image": "pg"}}
        for name in paid_services:
            services[name] = {"image": f"img-{name}"}
        if services_extra:
            services.update(services_extra)
        base = tmp_path / "base.yml"
        base.write_text(yaml.safe_dump({"services": services, "x-paid-services": paid_services}))
        overlay = tmp_path / "overlay.yml"
        overlay.write_text(
            yaml.safe_dump(
                {"services": {name: {"profiles": ["paid-excluded"]} for name in excluded}}
            )
        )
        return base, overlay

    def test_synthetic_unpaid_profile_entry_fails(self, tmp_path):
        """THE scenario from the spec: a paid service added without the
        overlay exclusion must fail and name the service."""
        base, overlay = self._write_synthetic(
            tmp_path,
            paid_services=["semantic-service-test", "new-paid-service-test"],
            excluded=["semantic-service-test"],  # new-paid-service-test MISSING
        )
        violations = overlay_parity_violations(base, overlay)
        assert violations == ["new-paid-service-test"]

    def test_synthetic_full_parity_passes(self, tmp_path):
        base, overlay = self._write_synthetic(
            tmp_path,
            paid_services=["semantic-service-test", "dq-service-test"],
            excluded=["semantic-service-test", "dq-service-test"],
        )
        assert overlay_parity_violations(base, overlay) == []

    def test_synthetic_missing_x_paid_services_raises(self, tmp_path):
        base = tmp_path / "base.yml"
        base.write_text(yaml.safe_dump({"services": {"api": {"image": "api"}}}))
        overlay = tmp_path / "overlay.yml"
        overlay.write_text("services: {}\n")
        import pytest

        with pytest.raises(ValueError, match="x-paid-services"):
            overlay_parity_violations(base, overlay)
