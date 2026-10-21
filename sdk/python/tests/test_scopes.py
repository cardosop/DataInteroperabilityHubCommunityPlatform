"""W6.5 (S1) — scope vocabulary pins for the Python SDK.

The parity against the BACKEND vocabulary is pinned by the contract
test (scripts/tests/test_w65_scope_set_contract.py).  This suite pins
the SDK-side behaviour: validator semantics, role lookups, the public
export surface, and the DeveloperAPI.create_api_key fail-fast
validation (no network — the ValueError fires before any request).
"""

import pytest

from datahub_interoperability import (
    ALL_SCOPES,
    ROLE_SCOPES,
    SCOPE_SCHEDULED_INGESTION_INTERNAL,
    WILDCARD_SCOPE,
    DataHubClient,
    DataHubClientConfig,
)
from datahub_interoperability.scopes import scope_set_for_role, validate_scopes


class TestVocabularyShape:
    def test_wildcard_and_internal_constants(self):
        assert WILDCARD_SCOPE == "*"
        assert SCOPE_SCHEDULED_INGESTION_INTERNAL == "scheduled_ingestion:internal"
        assert WILDCARD_SCOPE not in ALL_SCOPES
        assert SCOPE_SCHEDULED_INGESTION_INTERNAL not in ALL_SCOPES

    def test_all_scopes_covers_every_role_entry(self):
        for role_scopes in ROLE_SCOPES.values():
            assert (role_scopes - ALL_SCOPES) <= {WILDCARD_SCOPE}

    def test_every_scope_is_a_domain_action_pair(self):
        for scope in ALL_SCOPES:
            domain, action = scope.split(":", 1)
            assert domain.islower() and action in {"read", "write", "view_pii"}


class TestValidateScopes:
    def test_valid_scopes_pass(self):
        assert validate_scopes(["assets:read", "contracts:write"]) == []
        assert validate_scopes([]) == []
        assert validate_scopes(None) == []

    def test_wildcard_passes_client_validation(self):
        # Role-gated server-side (R2-B2) — the client cannot know roles.
        assert validate_scopes(["*"]) == []

    def test_unknown_scopes_are_flagged_in_order_without_duplicates(self):
        assert validate_scopes(["nope:nope"]) == ["nope:nope"]
        assert validate_scopes(["assets:read", "nope:nope", "assets:read", "nope:nope"]) == [
            "nope:nope"
        ]

    def test_internal_scope_is_always_flagged(self):
        assert validate_scopes([SCOPE_SCHEDULED_INGESTION_INTERNAL]) == [
            SCOPE_SCHEDULED_INGESTION_INTERNAL
        ]


class TestRoleLookup:
    def test_known_roles(self):
        assert scope_set_for_role("DATA_VIEWER") == frozenset(
            {"assets:read", "contracts:read", "datasets:read"}
        )
        assert scope_set_for_role("PLATFORM_ADMIN") == frozenset({WILDCARD_SCOPE})

    def test_unknown_role_is_empty(self):
        assert scope_set_for_role("NO_SUCH_ROLE") == frozenset()


class TestCreateApiKeyFailFast:
    """DeveloperAPI.create_api_key validates scopes BEFORE any request:
    a client pointed at an unreachable URL must still raise the clear
    ValueError (never a NetworkError) for a bad scope."""

    def _client(self) -> DataHubClient:
        return DataHubClient(
            DataHubClientConfig(
                base_url="http://127.0.0.1:1/api/v1",  # nothing listens here
                max_retries=0,
            )
        )

    @pytest.mark.asyncio
    async def test_invalid_scope_fails_fast_without_network(self):
        client = self._client()
        with pytest.raises(ValueError, match="Invalid API-key scopes: nope:nope"):
            await client.developer.create_api_key({"name": "k", "scopes": ["nope:nope"]})
        await client.close()

    @pytest.mark.asyncio
    async def test_internal_scope_fails_fast(self):
        client = self._client()
        with pytest.raises(ValueError, match="scheduled_ingestion:internal"):
            await client.developer.create_api_key(
                {"name": "k", "scopes": [SCOPE_SCHEDULED_INGESTION_INTERNAL]}
            )
        await client.close()

    @pytest.mark.asyncio
    async def test_no_scopes_field_skips_validation_and_hits_the_network(self):
        # No scopes key → the thin client behaviour is unchanged (the
        # request goes out; against the dead port it is a NetworkError,
        # proving validation only gates the scopes path).
        client = self._client()
        with pytest.raises(Exception) as excinfo:
            await client.developer.create_api_key({"name": "k"})
        assert "Invalid API-key scopes" not in str(excinfo.value)
        await client.close()
