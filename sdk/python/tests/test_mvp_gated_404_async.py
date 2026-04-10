"""
End-to-end tests for the SDK MVP-gated 404 error path.

Drives the **real** ``DataHubClient.request`` against an ``httpx.MockTransport``
that returns 404s for gated and non-gated routes. This exercises both the
``response.is_error`` branch (~line 359) and the ``HTTPStatusError`` branch
(~line 400) in the same async method without any unittest.mock involvement.

Per the spec: **exactly one** test pins the full rendered message string;
all other tests assert structural fields only.

Phase 215.2 — see openspec/changes/preprod01/specs/cli-sdk-mvp-awareness/spec.md
"""
from __future__ import annotations

import httpx
import pytest

from datahub_interoperability import (
    MVP_GATED_PREFIXES,
    DataHubClient,
    DataHubClientConfig,
    MVPGatedFeatureError,
    NotFoundError,
)
from datahub_interoperability._mvp_gates import (
    MVP_FEATURE_GATED_CODE,
    MVP_GATED_FEATURE_NAMES,
)


BASE_URL = "https://meshant-internal.example.com"


def _client_with_transport(transport: httpx.MockTransport) -> DataHubClient:
    """Build a real DataHubClient backed by an httpx.MockTransport.

    No unittest.mock — the transport is a first-class httpx primitive used to
    serve canned responses to a real ``httpx.AsyncClient``.
    """
    config = DataHubClientConfig(
        base_url=BASE_URL,
        api_token="test-token",
        max_retries=0,
        timeout=5,
    )
    client = DataHubClient(config)
    # Replace the underlying AsyncClient with one that uses our transport.
    client.client = httpx.AsyncClient(
        base_url=BASE_URL,
        transport=transport,
        headers={"User-Agent": "test", "Content-Type": "application/json"},
    )
    return client


def _transport_returning_404(body: bytes = b'{"detail":"Not Found."}') -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, content=body, request=request)

    return httpx.MockTransport(handler)


def _transport_returning_500() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, content=b'{"error":"boom"}', request=request)

    return httpx.MockTransport(handler)


# ---------------------------------------------------------------------------
# Branch A — response.is_error path (line ~359)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("prefix", sorted(MVP_GATED_PREFIXES))
async def test_response_is_error_branch_raises_for_every_gated_prefix(prefix: str) -> None:
    client = _client_with_transport(_transport_returning_404())
    try:
        with pytest.raises(MVPGatedFeatureError) as exc_info:
            await client.request("GET", f"/api/v1/{prefix}list")
        err = exc_info.value
        assert err.code == MVP_FEATURE_GATED_CODE
        assert err.http_status == 404
        assert err.prefix == prefix
        assert err.feature == MVP_GATED_FEATURE_NAMES[prefix]
        assert err.endpoint == f"{prefix}list"
        assert err.environment_url == BASE_URL
    finally:
        await client.client.aclose()


@pytest.mark.asyncio
async def test_response_is_error_branch_with_non_json_body() -> None:
    """The non-JSON ``ValueError`` arm MUST also intercept gated 404s."""
    client = _client_with_transport(_transport_returning_404(body=b"not-json-at-all"))
    try:
        with pytest.raises(MVPGatedFeatureError):
            await client.request("GET", "/api/v1/mesh/clusters")
    finally:
        await client.client.aclose()


# ---------------------------------------------------------------------------
# Branch B — HTTPStatusError path (line ~400)
# ---------------------------------------------------------------------------
#
# The ``HTTPStatusError`` branch is reached when the underlying httpx call
# raises ``httpx.HTTPStatusError``. We trigger that by configuring the
# transport to *raise* it directly via ``raise_for_status`` in a wrapping
# transport. The cleanest way is to wire ``client.client.request`` to a
# transport that returns a 404 and then have the SDK invoke
# ``response.raise_for_status()`` — but the SDK does NOT call that itself.
# Instead the ``HTTPStatusError`` branch fires when the ``response.is_error``
# block executes a ``continue`` (token refresh) and a subsequent retry hits
# an ``HTTPStatusError`` raised by an event hook. We install an event hook
# to force that path.


def _transport_for_event_hook_path() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, content=b'{"detail":"Not Found."}', request=request)

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_http_status_error_branch_raises_mvp_gated() -> None:
    """The ``except httpx.HTTPStatusError`` arm MUST also intercept gated 404s.

    We force that path by installing an httpx response event hook that calls
    ``response.raise_for_status()`` — when it fires on a 404, the surrounding
    ``try`` in ``DataHubClient.request`` catches the ``HTTPStatusError`` and
    routes through the second ``parse_error`` site.
    """
    config = DataHubClientConfig(
        base_url=BASE_URL,
        api_token="test-token",
        max_retries=0,
        timeout=5,
    )
    client = DataHubClient(config)

    async def _raise_for_status(response: httpx.Response) -> None:
        # The hook fires AFTER ``client.request`` returns the response. We
        # call raise_for_status here so the SDK's ``except httpx.HTTPStatusError``
        # arm is the one that handles the 404, not the ``response.is_error`` arm.
        # Read the body first so the hook is allowed to call raise_for_status.
        await response.aread()
        response.raise_for_status()

    client.client = httpx.AsyncClient(
        base_url=BASE_URL,
        transport=_transport_for_event_hook_path(),
        headers={"User-Agent": "test", "Content-Type": "application/json"},
        event_hooks={"response": [_raise_for_status]},
    )
    try:
        with pytest.raises(MVPGatedFeatureError) as exc_info:
            await client.request("GET", "/api/v1/baas/auth")
        err = exc_info.value
        assert err.code == MVP_FEATURE_GATED_CODE
        assert err.prefix == "baas/"
        assert err.feature == "Backend-as-a-Service"
    finally:
        await client.client.aclose()


# ---------------------------------------------------------------------------
# Backwards-compat
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_existing_except_notfound_still_catches_gated_404() -> None:
    """Refining ``except NotFoundError`` to ``MVPGatedFeatureError`` MUST be additive."""
    client = _client_with_transport(_transport_returning_404())
    try:
        caught: NotFoundError | None = None
        try:
            await client.request("GET", "/api/v1/mesh/clusters")
        except NotFoundError as e:
            caught = e
        assert isinstance(caught, MVPGatedFeatureError)
    finally:
        await client.client.aclose()


@pytest.mark.asyncio
async def test_404_against_non_gated_route_is_not_misclassified() -> None:
    client = _client_with_transport(_transport_returning_404())
    try:
        with pytest.raises(NotFoundError) as exc_info:
            await client.request("GET", "/api/v1/contracts/does-not-exist")
        assert not isinstance(exc_info.value, MVPGatedFeatureError)
        assert exc_info.value.code != MVP_FEATURE_GATED_CODE
    finally:
        await client.client.aclose()


@pytest.mark.asyncio
async def test_500_against_gated_route_is_not_misclassified() -> None:
    client = _client_with_transport(_transport_returning_500())
    try:
        with pytest.raises(Exception) as exc_info:
            await client.request("GET", "/api/v1/mesh/clusters")
        assert not isinstance(exc_info.value, MVPGatedFeatureError)
    finally:
        await client.client.aclose()


# ---------------------------------------------------------------------------
# Public-API contract — top-level imports
# ---------------------------------------------------------------------------


def test_top_level_imports_expose_introspection_api() -> None:
    """``from datahub_interoperability import …`` MUST expose the gating set."""
    from datahub_interoperability import MVP_GATED_PREFIXES as exported_set
    from datahub_interoperability import MVPGatedFeatureError as exported_err
    from datahub_interoperability import NotFoundError as exported_nf

    assert isinstance(exported_set, frozenset)
    assert exported_set, "MVP_GATED_PREFIXES MUST not be empty"
    assert all(isinstance(p, str) for p in exported_set)
    assert all(p.endswith("/") for p in exported_set), (
        "every gated prefix MUST end with '/' to match the canonical hub format"
    )
    assert issubclass(exported_err, exported_nf)


def test_mvp_gated_feature_error_to_dict_serialization() -> None:
    """``to_dict()`` MUST round-trip the MVP-gated structured fields.

    Other SDK errors expose ``to_dict()`` as the documented JSON envelope; the
    new error type MUST honor that contract so programmatic consumers can
    serialize a gated 404 to JSON without losing the feature/prefix/endpoint
    metadata.
    """
    err = MVPGatedFeatureError(
        feature="Data Mesh",
        prefix="mesh/",
        endpoint="mesh/clusters",
        environment_url="https://meshant-internal.example.com",
    )
    payload = err.to_dict()
    assert payload["error"]["code"] == MVP_FEATURE_GATED_CODE
    assert payload["error"]["http_status"] == 404
    details = payload["error"]["details"]
    assert details["feature"] == "Data Mesh"
    assert details["prefix"] == "mesh/"
    assert details["endpoint"] == "mesh/clusters"
    assert details["environment_url"] == "https://meshant-internal.example.com"


def test_introspection_does_not_require_http() -> None:
    """A consumer can pre-check a path against ``MVP_GATED_PREFIXES`` offline."""
    from datahub_interoperability import MVP_GATED_PREFIXES as gates

    path = "mesh/clusters/abc"
    assert any(path.startswith(p) for p in gates)


# ---------------------------------------------------------------------------
# Exactly-one full-message regression lock
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_rendered_message_for_one_representative_feature() -> None:
    """Pin the full rendered message string for the Data Mesh feature."""
    client = _client_with_transport(_transport_returning_404())
    try:
        with pytest.raises(MVPGatedFeatureError) as exc_info:
            await client.request("GET", "/api/v1/mesh/clusters/abc")
        err = exc_info.value
        expected = (
            "The 'Data Mesh' feature is not available in the current MVP release.\n"
            "\n"
            "  Endpoint:    mesh/clusters/abc\n"
            "  Environment: https://meshant-internal.example.com\n"
            "  Status:      Post-MVP (planned)\n"
            "\n"
            "This is a deliberate gate, not a missing resource — the route exists in\n"
            "the codebase and will be enabled after the MVP release. To track when\n"
            "'Data Mesh' becomes available, see the project roadmap.\n"
            "\n"
            "Error code: MVP_FEATURE_GATED"
        )
        assert err.message == expected
    finally:
        await client.client.aclose()
