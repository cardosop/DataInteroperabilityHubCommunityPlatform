"""
Phase 216.1.1 — CLI persona fixtures (D145).

Provides 13 persona fixtures, one per D145 persona. Each yields a
``CliRunner`` pre-configured with a temp config dir and persona-specific
credentials obtained via ``_persona_provisioning.provision_persona``.

Fixtures:
    visitor_runner, auditor_runner, community_manager_runner,
    compliance_officer_runner, data_analyst_runner, data_consumer_runner,
    data_engineer_runner, data_mesh_domain_owner_runner,
    data_product_owner_runner, data_scientist_runner,
    external_developer_runner, platform_admin_runner, tenant_admin_runner

Parametrize helpers:
    all_mvp_personas — list of all 13 persona role strings
    all_mvp_personas_excluding(*roles) — subset excluding given roles
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Generator
from dataclasses import dataclass

import pytest
from click.testing import CliRunner
from tests._persona_provisioning import PersonaCredentials, provision_persona

# ---------------------------------------------------------------------------
# D145 persona role strings — canonical list
# ---------------------------------------------------------------------------

MVP_PERSONA_ROLES: list[str] = [
    "visitor",
    "auditor",
    "community_manager",
    "compliance_officer",
    "data_analyst",
    "data_consumer",
    "data_engineer",
    "data_mesh_domain_owner",
    "data_product_owner",
    "data_scientist",
    "external_developer",
    "platform_admin",
    "tenant_admin",
]

all_mvp_personas: list[str] = list(MVP_PERSONA_ROLES)


def all_mvp_personas_excluding(*roles: str) -> list[str]:
    """Return the persona list minus the given roles."""
    excluded = set(roles)
    return [r for r in MVP_PERSONA_ROLES if r not in excluded]


# ---------------------------------------------------------------------------
# Internal: build a CliRunner with persona credentials
# ---------------------------------------------------------------------------


@dataclass
class PersonaRunner:
    """A CliRunner bound to a specific persona's credentials."""

    runner: CliRunner
    credentials: PersonaCredentials
    role: str
    config_dir: str


def _make_persona_runner(role: str) -> Generator[PersonaRunner, None, None]:
    """Provision a persona, yield a runner, clean up on teardown.

    When no backend is reachable (local dev, unit tests), falls back to
    synthetic credentials so the fixture instantiates without error.
    Tests that actually hit the API will fail at call time with a clear
    auth error — much better than crashing at fixture setup.
    """
    try:
        creds = provision_persona(role)
    except Exception:
        # Fallback: synthetic credentials for offline/unit-test use.
        creds = PersonaCredentials(
            api_key=f"offline-{role}-token",
            user_id=f"offline-{role}-uid",
            tenant_id="offline-tenant",
            refresh_token=f"offline-{role}-refresh",
            role=role,
        )

    with tempfile.TemporaryDirectory(prefix=f"cli-{role}-") as tmpdir:
        # Write a config.yaml that points the CLI at the right API + token
        config_dir = os.path.join(tmpdir, ".datahub")
        os.makedirs(config_dir, exist_ok=True)

        _port = os.environ.get("API_TEST_PORT", "8000")
        api_url = os.environ.get(
            "MESHANT_API_URL",
            os.environ.get("ODH_BASE_URL", f"http://localhost:{_port}/api/v1"),
        )
        config_path = os.path.join(config_dir, "config.yaml")
        with open(config_path, "w") as f:
            f.write(f"api_url: {api_url}\napi_key: {creds.api_key}\n")

        runner = CliRunner(
            env={
                "DATAHUB_CONFIG_DIR": config_dir,
                "DATAHUB_API_URL": api_url,
                "DATAHUB_API_KEY": creds.api_key,
            },
        )

        yield PersonaRunner(
            runner=runner,
            credentials=creds,
            role=role,
            config_dir=config_dir,
        )


# ---------------------------------------------------------------------------
# 13 persona fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def visitor_runner():
    yield from _make_persona_runner("visitor")


@pytest.fixture(scope="session")
def auditor_runner():
    yield from _make_persona_runner("auditor")


@pytest.fixture(scope="session")
def community_manager_runner():
    yield from _make_persona_runner("community_manager")


@pytest.fixture(scope="session")
def compliance_officer_runner():
    yield from _make_persona_runner("compliance_officer")


@pytest.fixture(scope="session")
def data_analyst_runner():
    yield from _make_persona_runner("data_analyst")


@pytest.fixture(scope="session")
def data_consumer_runner():
    yield from _make_persona_runner("data_consumer")


@pytest.fixture(scope="session")
def data_engineer_runner():
    yield from _make_persona_runner("data_engineer")


@pytest.fixture(scope="session")
def data_mesh_domain_owner_runner():
    yield from _make_persona_runner("data_mesh_domain_owner")


@pytest.fixture(scope="session")
def data_product_owner_runner():
    yield from _make_persona_runner("data_product_owner")


@pytest.fixture(scope="session")
def data_scientist_runner():
    yield from _make_persona_runner("data_scientist")


@pytest.fixture(scope="session")
def external_developer_runner():
    yield from _make_persona_runner("external_developer")


@pytest.fixture(scope="session")
def platform_admin_runner():
    yield from _make_persona_runner("platform_admin")


@pytest.fixture(scope="session")
def tenant_admin_runner():
    yield from _make_persona_runner("tenant_admin")
