"""W9.2 bootstrap pins — G12 explicit-secret config + dev-env completeness +
boundary/publish gate existence (RED-first; no Django, no mocks).

Pins the contracts the oss-maturity-assessment named:
1. every ``__X__`` placeholder in ``.env.dev.template`` is replaced by the
   ``dev-env`` Makefile recipe (the pre-fix recipe left a literal
   ``__INTERNAL_API_KEY__`` that became a de-facto well-known credential
   and crashed the internal endpoints);
2. settings.py carries NO well-known dev-secret constants and NO
   password-guessing matrix (G12: explicit config, no silent fallbacks);
3. every test-compose service that boots Django declares SECRET_KEY +
   JWT_SECRET_KEY + ENCRYPTION_KEY explicitly;
4. the dev/staging/core compose key wiring is explicit (no
   ``:-dev-secret-…`` constants; the core quickstart overlay requires the
   keys via ``${…:?}`` interpolation);
5. ``setup.sh`` and the legacy ``setup`` target are gone (the bootstrap is
   docker-only: ``make dev-env`` / ``make quickstart``);
6. ``boundary-check`` and ``publish-check`` exist and run the components
   the docs promise.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MAKEFILE = (REPO / "Makefile").read_text()
MAKEFILE_CORE = (REPO / "Makefile.core").read_text()
ALL_MAKEFILES = MAKEFILE + "\n" + MAKEFILE_CORE
SETTINGS = (REPO / "hub" / "settings.py").read_text()
TEMPLATE = (REPO / ".env.dev.template").read_text()

SERVICE_RE = re.compile(r"^  ([a-z0-9_-]+):\s*$", re.M)
ENV_KEY_RE = re.compile(r"^      ([A-Z][A-Z0-9_]*):", re.M)

REQUIRED_KEYS = {"SECRET_KEY", "JWT_SECRET_KEY", "ENCRYPTION_KEY"}


def compose_service_blocks(text: str) -> dict[str, str]:
    """Split a compose file into {service_name: raw_block} (text-based —
    compose custom tags like ``!reset`` defeat SafeLoader)."""
    blocks: dict[str, str] = {}
    matches = list(SERVICE_RE.finditer(text))
    for i, match in enumerate(matches):
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        blocks[match.group(1)] = text[start:end]
    return blocks


def service_env_keys(block: str) -> set[str]:
    return set(ENV_KEY_RE.findall(block))


def django_services(text: str) -> list[str]:
    blocks = compose_service_blocks(text)
    return [name for name, block in blocks.items() if "DJANGO_SETTINGS_MODULE" in block]


def test_template_placeholders_all_replaced_by_dev_env():
    """Every ``__X__`` placeholder in .env.dev.template is replaced by the
    dev-env recipe — a template key added without a sed line fails here."""
    placeholders = set(re.findall(r"__[A-Z0-9_]+__", TEMPLATE))
    assert placeholders, ".env.dev.template carries no placeholders?"
    dev_env_recipe = ""
    in_dev_env = False
    for line in MAKEFILE.splitlines():
        if line.startswith("dev-env:"):
            in_dev_env = True
            continue
        if in_dev_env and line.startswith("\t"):
            dev_env_recipe += line + "\n"
        elif in_dev_env:
            break
    missing = [p for p in sorted(placeholders) if p not in dev_env_recipe]
    assert not missing, (
        f"dev-env does not replace these template placeholders (the "
        f"pre-fix __INTERNAL_API_KEY__ miss class): {missing}"
    )


def test_settings_has_no_well_known_dev_secret_fallbacks():
    """G12 — the committed well-known dev secrets are gone from settings."""
    for needle in (
        "_DEV_SECRET_KEY",
        "_DEV_JWT_SECRET_KEY",
        "_DEV_ENCRYPTION_KEY",
        "dev-secret-key-not-for-production",
        "dev-jwt-secret-key-not-for-production",
        "dev-encryption-key-not-for-production",
    ):
        assert needle not in SETTINGS, f"well-known dev secret still in settings.py: {needle}"


def test_settings_has_no_postgres_password_guessing_matrix():
    """G12 — the pytest-branch password-guessing loop is gone: one explicit
    password from config, never a list of guessed passwords."""
    assert "passwords_to_try" not in SETTINGS
    assert "hub_secure" not in SETTINGS


def test_settings_has_universal_fail_closed_key_guard():
    """G12 — an explicitly-empty key fails closed in EVERY environment, not
    only production. Pinned on the guard's message marker (the behavioral
    pin lives in hub/tests/test_w92_g12_explicit_secrets.py)."""
    marker = "is not configured"
    assert marker in SETTINGS, (
        f"the universal fail-closed key guard is missing (marker {marker!r}) — "
        "settings.py still allows empty/silent-fallback keys outside production"
    )


def test_test_compose_django_services_declare_all_three_keys():
    """Every docker-compose.test.yml service that boots Django declares the
    three explicit keys (fresh CI runners have no .env.dev to fall back on).
    compliance-rq-worker-test is included explicitly — it imports
    hub.settings when executing compliance RQ tasks without setting
    DJANGO_SETTINGS_MODULE itself."""
    text = (REPO / "docker-compose.test.yml").read_text()
    offenders = []
    names = set(django_services(text)) | {"compliance-rq-worker-test"}
    for name in sorted(names):
        keys = service_env_keys(compose_service_blocks(text)[name])
        if not REQUIRED_KEYS.issubset(keys):
            offenders.append(f"{name} (has {sorted(keys & REQUIRED_KEYS)})")
    assert not offenders, f"test-compose Django services missing explicit keys: {offenders}"


def test_dev_compose_has_no_well_known_key_fallback():
    """The dev api's ``SECRET_KEY: ${SECRET_KEY:-dev-secret-…}`` constant is
    gone — keys come from .env.dev / the quickstart .env, explicitly."""
    text = (REPO / "docker-compose.yml").read_text()
    assert "dev-secret-key-change-in-production" not in text
    blocks = compose_service_blocks(text)
    # compliance-rq-worker runs RQ Django tasks — it must read .env.dev.
    assert "env_file" in blocks.get("compliance-rq-worker", ""), (
        "compliance-rq-worker must read .env.dev (it boots Django settings)"
    )


def test_core_overlay_requires_keys_explicitly():
    """The quickstart overlay passes the three keys through with required
    interpolation — a fresh clone without .env fails at compose parse time,
    not silently with a well-known key."""
    text = (REPO / "docker-compose.core.yml").read_text()
    blocks = compose_service_blocks(text)
    for name in ("api-service", "worker-service"):
        keys = service_env_keys(blocks[name])
        for key in REQUIRED_KEYS:
            assert key in keys, f"core overlay {name} does not declare {key}"
        # required-style interpolation, not a silent fallback
        assert "${SECRET_KEY:?" in blocks[name]


def test_staging_compose_declares_keys_explicitly():
    """Staging api/worker declare the three keys (the pre-fix staging stack
    ran on the settings well-known defaults)."""
    text = (REPO / "docker-compose.staging.yml").read_text()
    blocks = compose_service_blocks(text)
    for name in ("api-service", "worker-service"):
        block = blocks.get(name, "")
        keys = service_env_keys(block)
        missing = REQUIRED_KEYS - keys
        assert not missing, f"staging {name} does not declare: {sorted(missing)}"


def test_setup_sh_and_make_setup_target_removed():
    """The legacy setup.sh (wrong manage.py path, startproject stub) and the
    ``make setup`` target are gone — bootstrap is docker-only."""
    assert not (REPO / "setup.sh").exists(), "setup.sh still exists"
    assert not re.search(r"^setup:", MAKEFILE, re.M), "the legacy `setup:` make target still exists"


def test_boundary_and_publish_check_targets_exist_with_promised_components():
    """README/OSS_CONTRIBUTION promise ``make boundary-check`` and
    ``make publish-check`` — the targets must exist and run the documented
    components (boundary + guards + openspec structural + gitleaks +
    publish-tree parity)."""
    assert re.search(r"^boundary-check:", ALL_MAKEFILES, re.M), "boundary-check target missing"
    assert "check_core_boundary.py" in ALL_MAKEFILES
    publish_recipe = ""
    in_publish = False
    for line in ALL_MAKEFILES.splitlines():
        if re.match(r"^publish-check:", line):
            in_publish = True
            continue
        if in_publish:
            if line.startswith("\t"):
                publish_recipe += line + "\n"
            elif line.strip():
                break
    assert publish_recipe, "publish-check target missing"
    for component, needle in (
        ("boundary", "check_core_boundary.py"),
        ("openspec structural gate", "validate_openspec_changes.sh"),
        ("gitleaks", "gitleaks"),
        ("publish-tree parity", "test_publish_tree.py"),
    ):
        assert needle in publish_recipe, f"publish-check does not run the {component} component"


if __name__ == "__main__":
    sys.exit(0 if __import__("pytest").main([__file__, "-q", "--no-header"]) == 0 else 1)
