"""Hermetic-image guard for compose services we build ourselves (Phase P.1).

Found by the P.1 full-mode stack restart: ``prefect-integration-service-test``
installed eight packages with ``pip install`` on EVERY container start, then
ran ``django.setup()`` over the full paid app registry. Measured cost was
~105s for the Django import alone; with the pip step the service needed far
longer to answer ``/health`` than its healthcheck budget allowed
(``start_period 90s`` + ``5 x 30s`` retries = 240s). It went ``unhealthy``,
and because ``api-service-test`` declares
``depends_on: prefect-integration-service-test: condition: service_healthy``
the API container never started at all — ``docker compose up -d --wait``
aborted with "dependency failed to start".

The core overlay profiles this service OUT (``profiles: ["paid-excluded"]``),
so core-mode CI never exercised it. The defect was reachable only in full
(paid) mode, which is exactly the blind spot Phase P exists to close.

Two things were wrong, and this module pins the general one:

1. Installing dependencies at container start is non-hermetic — it needs the
   network on every boot, it silently drifts from the image, and it moves
   dependency-resolution cost into the healthcheck window. Declared
   dependencies belong in the image.
2. The healthcheck budget did not reflect measured startup cost. That is
   pinned separately by ``test_healthcheck_budget_covers_measured_startup``.

Scope: services the repo BUILDS (they have a ``build:`` key) — we control
those images. Services pulled from upstream registries are exempt: patching
them would require a derived Dockerfile, which is a deliberate trade-off
rather than an oversight. Exemptions are explicit and must carry a reason.

No mocks: the real compose files are parsed. The RED drill uses synthetic
service definitions so the detector is proven to fail when it should.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
TEST_COMPOSE = REPO_ROOT / "docker-compose.test.yml"


class _ResetLoader(yaml.SafeLoader):
    """Compose ``!reset`` tags (v2.24+) are not standard YAML."""


def _reset_constructor(_loader, _node):
    return None


_ResetLoader.add_constructor("!reset", _reset_constructor)

# Services allowed to bootstrap packages at start, with the reason they cannot
# simply bake them in. Keep this empty unless there is no build context to own.
RUNTIME_INSTALL_EXEMPTIONS: dict[str, str] = {
    # Upstream prefecthq/prefect image, no local build context: adding asyncpg
    # would require a derived Dockerfile for a single driver package.
    "prefect-server-test": "upstream image, no local build context",
}


def _load(path: Path) -> dict:
    with path.open() as fh:
        return yaml.load(fh, Loader=_ResetLoader) or {}


def _command_text(service: dict) -> str:
    """Flatten a compose ``command`` (string or list form) to searchable text."""
    command = service.get("command")
    if command is None:
        return ""
    if isinstance(command, str):
        return command
    return " ".join(str(part) for part in command)


def _runtime_install_violations(services: dict) -> list[str]:
    """Return ``name: command`` for built services that install at runtime."""
    violations = []
    for name, service in sorted(services.items()):
        if not isinstance(service, dict) or "build" not in service:
            continue  # upstream image — not ours to bake
        if name in RUNTIME_INSTALL_EXEMPTIONS:
            continue
        text = _command_text(service)
        if "pip install" in text or "npm install" in text or "apt-get install" in text:
            violations.append(f"{name}: {text[:120]}")
    return violations


class TestNoRuntimePackageInstalls:
    """Built images declare their dependencies; they do not fetch them at boot."""

    def test_no_built_service_installs_packages_at_start(self):
        services = _load(TEST_COMPOSE).get("services", {})
        assert services, "docker-compose.test.yml parsed with no services"

        violations = _runtime_install_violations(services)

        assert not violations, (
            "Built compose services must declare dependencies in their image, not "
            "install them on every container start (non-hermetic, needs network at "
            "boot, and inflates startup past the healthcheck budget).\n"
            "Move the packages into the service's requirements file / Dockerfile, or "
            "add an explicit entry to RUNTIME_INSTALL_EXEMPTIONS with a reason.\n"
            "Violations:\n  " + "\n  ".join(violations)
        )

    def test_exemptions_reference_real_services(self):
        """A stale exemption would silently permit a future violation."""
        services = _load(TEST_COMPOSE).get("services", {})
        unknown = sorted(set(RUNTIME_INSTALL_EXEMPTIONS) - set(services))
        assert not unknown, f"RUNTIME_INSTALL_EXEMPTIONS names unknown services: {unknown}"

    def test_exempt_services_have_no_build_context(self):
        """Exemption is only justified when we do not build the image."""
        services = _load(TEST_COMPOSE).get("services", {})
        wrongly_exempt = sorted(
            name
            for name in RUNTIME_INSTALL_EXEMPTIONS
            if isinstance(services.get(name), dict) and "build" in services[name]
        )
        assert not wrongly_exempt, (
            "These services have a build context, so they can bake their dependencies "
            f"and must not be exempt: {wrongly_exempt}"
        )

    # --- RED drill: the detector must fail when it should ---------------------

    def test_detector_flags_a_built_service_with_runtime_pip(self):
        synthetic = {
            "some-service": {
                "build": {"context": "."},
                "command": "sh -c 'pip install requests && python main.py'",
            }
        }
        assert _runtime_install_violations(synthetic) == [
            "some-service: sh -c 'pip install requests && python main.py'"
        ]

    def test_detector_flags_list_form_commands(self):
        synthetic = {
            "some-service": {
                "build": {"context": "."},
                "command": ["sh", "-c", "pip install asyncpg && exec server"],
            }
        }
        assert len(_runtime_install_violations(synthetic)) == 1

    def test_detector_ignores_upstream_images(self):
        synthetic = {
            "upstream": {
                "image": "vendor/thing:1",
                "command": "sh -c 'pip install x && run'",
            }
        }
        assert _runtime_install_violations(synthetic) == []

    def test_detector_ignores_clean_built_service(self):
        synthetic = {
            "clean": {"build": {"context": "."}, "command": ["python", "-m", "uvicorn", "main:app"]}
        }
        assert _runtime_install_violations(synthetic) == []


class TestHealthcheckBudgetCoversMeasuredStartup:
    """Probe budgets must reflect measured startup, not optimistic guesses.

    ``prefect-integration-service-test`` runs ``django.setup()`` across the
    full paid app registry at import. That was measured at 104.7s inside the
    running container on 2026-08-23 (``python -c 'import main'``). A
    ``start_period`` below that guarantees the service is reported unhealthy
    before it has had a chance to bind its port.
    """

    # Measured 2026-08-23 in hub-test-prefect-integration; re-measure if the
    # service's import graph changes materially.
    MEASURED_DJANGO_SETUP_SECONDS = 105

    @staticmethod
    def _seconds(value: str | int | None) -> int | None:
        """Parse compose duration strings (``90s``, ``5m``, ``1m30s``)."""
        if value is None:
            return None
        if isinstance(value, int):
            return value
        text = str(value).strip()
        if text.isdigit():
            return int(text)
        total, number = 0, ""
        units = {"h": 3600, "m": 60, "s": 1}
        for char in text:
            if char.isdigit():
                number += char
            elif char in units and number:
                total += int(number) * units[char]
                number = ""
            else:
                return None
        return total or None

    def test_prefect_integration_start_period_covers_django_setup(self):
        services = _load(TEST_COMPOSE).get("services", {})
        service = services.get("prefect-integration-service-test")
        assert service, "prefect-integration-service-test missing from the test stack"

        healthcheck = service.get("healthcheck") or {}
        start_period = self._seconds(healthcheck.get("start_period"))
        assert start_period is not None, (
            "prefect-integration-service-test must declare an explicit healthcheck "
            "start_period — it performs a full Django setup before binding its port"
        )

        assert start_period >= self.MEASURED_DJANGO_SETUP_SECONDS, (
            f"start_period={start_period}s is below the measured full-mode Django "
            f"setup cost ({self.MEASURED_DJANGO_SETUP_SECONDS}s). The service is "
            "reported unhealthy before it can bind, and api-service-test "
            "(depends_on: condition: service_healthy) then never starts."
        )

    @pytest.mark.parametrize(
        ("text", "expected"),
        [("90s", 90), ("5m", 300), ("1m30s", 90), ("240", 240), (300, 300), (None, None)],
    )
    def test_duration_parser(self, text, expected):
        assert self._seconds(text) == expected
