"""
Phase 216.1.2 — SDK persona fixtures (D145).

Provides 13 persona fixtures, one per D145 persona. Each yields a
configured ``DataHubClient`` instance (or a plain credentials object
when the SDK client is not available) using persona-specific credentials
obtained via ``_persona_provisioning.provision_persona``.

Fixtures:
    visitor_client, auditor_client, community_manager_client,
    compliance_officer_client, data_analyst_client, data_consumer_client,
    data_engineer_client, data_mesh_domain_owner_client,
    data_product_owner_client, data_scientist_client,
    external_developer_client, platform_admin_client, tenant_admin_client

Parametrize helpers:
    all_mvp_personas — list of all 13 persona role strings
    all_mvp_personas_excluding(*roles) — subset excluding given roles
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Generator

import pytest

from tests._persona_provisioning import PersonaCredentials, provision_persona

# ---------------------------------------------------------------------------
# D145 persona role strings — canonical list (identical to CLI)
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
# Internal: build an SDK client with persona credentials
# ---------------------------------------------------------------------------


@dataclass
class PersonaClient:
    """An SDK client bound to a specific persona's credentials."""

    client: object  # DataHubClient or plain credentials
    credentials: PersonaCredentials
    role: str


def _make_persona_client(role: str) -> Generator[PersonaClient, None, None]:
    """Provision a persona, yield a client, clean up on teardown.

    When no backend is reachable (local dev, unit tests), falls back to
    synthetic credentials so the fixture instantiates without error.
    """
    try:
        creds = provision_persona(role)
    except Exception:
        creds = PersonaCredentials(
            api_key=f"offline-{role}-token",
            user_id=f"offline-{role}-uid",
            tenant_id="offline-tenant",
            refresh_token=f"offline-{role}-refresh",
            role=role,
        )

    api_url = os.environ.get(
        "MESHANT_API_URL",
        os.environ.get("ODH_BASE_URL", "http://localhost:8000/api/v1"),
    )

    # Try to import the real SDK client; fall back to plain credentials
    try:
        from datahub_sdk import DataHubClient

        client = DataHubClient(
            base_url=api_url,
            api_key=creds.api_key,
        )
    except ImportError:
        client = creds  # type: ignore[assignment]

    yield PersonaClient(client=client, credentials=creds, role=role)


# ---------------------------------------------------------------------------
# 13 persona fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def visitor_client():
    yield from _make_persona_client("visitor")


@pytest.fixture(scope="session")
def auditor_client():
    yield from _make_persona_client("auditor")


@pytest.fixture(scope="session")
def community_manager_client():
    yield from _make_persona_client("community_manager")


@pytest.fixture(scope="session")
def compliance_officer_client():
    yield from _make_persona_client("compliance_officer")


@pytest.fixture(scope="session")
def data_analyst_client():
    yield from _make_persona_client("data_analyst")


@pytest.fixture(scope="session")
def data_consumer_client():
    yield from _make_persona_client("data_consumer")


@pytest.fixture(scope="session")
def data_engineer_client():
    yield from _make_persona_client("data_engineer")


@pytest.fixture(scope="session")
def data_mesh_domain_owner_client():
    yield from _make_persona_client("data_mesh_domain_owner")


@pytest.fixture(scope="session")
def data_product_owner_client():
    yield from _make_persona_client("data_product_owner")


@pytest.fixture(scope="session")
def data_scientist_client():
    yield from _make_persona_client("data_scientist")


@pytest.fixture(scope="session")
def external_developer_client():
    yield from _make_persona_client("external_developer")


@pytest.fixture(scope="session")
def platform_admin_client():
    yield from _make_persona_client("platform_admin")


@pytest.fixture(scope="session")
def tenant_admin_client():
    yield from _make_persona_client("tenant_admin")
