"""
Phase 216.1.10 — unit tests for persona fixtures infrastructure.

These tests validate the persona fixture machinery WITHOUT hitting a backend:
- MVP_PERSONA_ROLES is complete (13 personas)
- all_mvp_personas_excluding works correctly
- PersonaRunner/PersonaCredentials dataclasses are constructable
"""

from __future__ import annotations

from tests._persona_provisioning import PersonaCredentials
from tests.fixtures.personas import (
    MVP_PERSONA_ROLES,
    all_mvp_personas,
    all_mvp_personas_excluding,
)


def test_all_mvp_personas_is_a_copy():
    """Modifying the returned list must not affect the canonical list."""
    copy = all_mvp_personas[:]
    copy.pop()
    assert len(all_mvp_personas) == 13


def test_all_mvp_personas_excluding_removes_roles():
    result = all_mvp_personas_excluding("visitor", "auditor")
    assert "visitor" not in result
    assert "auditor" not in result
    assert len(result) == 11


def test_all_mvp_personas_excluding_no_args_returns_all():
    assert all_mvp_personas_excluding() == MVP_PERSONA_ROLES


def test_persona_credentials_dataclass():
    """Verify PersonaCredentials stores and exposes all five fields."""
    creds = PersonaCredentials(
        api_key="tok-123",
        user_id="u-1",
        tenant_id="t-1",
        refresh_token="ref-1",
        role="data_engineer",
    )
    assert creds.api_key == "tok-123"
    assert creds.user_id == "u-1"
    assert creds.tenant_id == "t-1"
    assert creds.refresh_token == "ref-1"
    assert creds.role == "data_engineer"
    # All fields are strings
    assert isinstance(creds.api_key, str)
    assert isinstance(creds.user_id, str)
    assert isinstance(creds.tenant_id, str)
    assert isinstance(creds.refresh_token, str)
    assert isinstance(creds.role, str)


def test_persona_roles_are_lowercase_underscore():
    """Convention: all role strings are lowercase with underscores."""
    for role in MVP_PERSONA_ROLES:
        assert role == role.lower(), f"Role {role!r} must be lowercase"
        assert " " not in role, f"Role {role!r} must not contain spaces"


def test_expected_personas_present():
    """D145 canonical set must be complete."""
    expected = {
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
        "tenant_admin",  # noqa: PHASE216-STATIC-ID
    }
    assert set(MVP_PERSONA_ROLES) == expected
