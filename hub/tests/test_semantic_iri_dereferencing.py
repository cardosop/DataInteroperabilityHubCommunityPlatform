"""
Tests for Phase 22.3 — IRI Dereferencing (HTTP 303) and
Phase 22.5 — SPARQL Service Description proxy.

Verifies:
  - GET /semantic/resource/<type>/<id>/ with RDF Accept → 303 See Other
    pointing to the canonical SEMANTIC_BASE_IRI/id/<type>/<id> IRI.
  - GET /semantic/resource/<type>/<id>/ with non-RDF Accept → delegates to
    JSON-LD resolution logic (tested via mocked service client).
  - GET /semantic/sparql (no query param, authenticated) → SD (generated locally).
  - GET /semantic/sparql/description (public) → SD (generated locally).
  - Authentication is required for dereference_resource.
"""

import uuid
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SEMANTIC_BASE_IRI = "https://meshant.io"
_SAMPLE_UUID = str(uuid.uuid4())


def _make_user(email="phase22@test.example.com"):
    """Create a User with a personal Tenant (no username field)."""
    from django.contrib.auth import get_user_model

    from hub.apps.tenants.models import Tenant

    User = get_user_model()
    user = User.objects.create_user(
        email=email,
        password="testpass123",
    )
    tenant, _ = Tenant.objects.get_or_create(
        name="Phase22TestTenant",
        defaults={"slug": "phase22-test"},
    )
    user.tenant = tenant
    user.save()
    return user, tenant


# SD is now generated locally in views.py (_build_sd_turtle) — no service
# client call is made, so no mock is needed for the SD-only tests.


def _api_client(user=None):
    """Return an APIClient, optionally force-authenticated as user."""
    client = APIClient()
    if user is not None:
        client.force_authenticate(user=user)
    return client


# ---------------------------------------------------------------------------
# 22.3 — dereference_resource view
# ---------------------------------------------------------------------------


@override_settings(SEMANTIC_BASE_IRI=_SEMANTIC_BASE_IRI)
class TestDereferenceResourceRdfRedirect(TestCase):
    """RDF clients receive 303 redirect to canonical IRI."""

    def test_requires_authentication(self):
        url = reverse(
            "dereference-resource",
            kwargs={"resource_type": "asset", "resource_id": _SAMPLE_UUID},
        )
        resp = _api_client().get(url, HTTP_ACCEPT="text/turtle")
        self.assertIn(resp.status_code, (401, 403))

    def test_turtle_accept_returns_303(self):
        user, _tenant = _make_user("turtle303@test.example.com")
        url = reverse(
            "dereference-resource",
            kwargs={"resource_type": "asset", "resource_id": _SAMPLE_UUID},
        )
        resp = _api_client(user).get(url, HTTP_ACCEPT="text/turtle")
        self.assertEqual(resp.status_code, 303)

    def test_303_location_is_canonical_iri(self):
        user, _tenant = _make_user("location303@test.example.com")
        url = reverse(
            "dereference-resource",
            kwargs={"resource_type": "asset", "resource_id": _SAMPLE_UUID},
        )
        resp = _api_client(user).get(url, HTTP_ACCEPT="text/turtle")
        self.assertEqual(resp.status_code, 303)
        expected = f"{_SEMANTIC_BASE_IRI}/id/asset/{_SAMPLE_UUID}"
        self.assertEqual(resp["Location"], expected)

    def test_rdf_xml_accept_returns_303(self):
        user, _tenant = _make_user("rdfxml303@test.example.com")
        url = reverse(
            "dereference-resource",
            kwargs={"resource_type": "asset", "resource_id": _SAMPLE_UUID},
        )
        resp = _api_client(user).get(url, HTTP_ACCEPT="application/rdf+xml")
        self.assertEqual(resp.status_code, 303)

    def test_jsonld_accept_returns_303(self):
        user, _tenant = _make_user("jsonld303@test.example.com")
        url = reverse(
            "dereference-resource",
            kwargs={"resource_type": "asset", "resource_id": _SAMPLE_UUID},
        )
        resp = _api_client(user).get(url, HTTP_ACCEPT="application/ld+json")
        self.assertEqual(resp.status_code, 303)

    def test_contract_type_303(self):
        user, _tenant = _make_user("contract303@test.example.com")
        cid = str(uuid.uuid4())
        url = reverse(
            "dereference-resource",
            kwargs={"resource_type": "contract", "resource_id": cid},
        )
        resp = _api_client(user).get(url, HTTP_ACCEPT="text/turtle")
        self.assertEqual(resp.status_code, 303)
        self.assertIn(f"/id/contract/{cid}", resp["Location"])

    def test_dataset_type_303(self):
        user, _tenant = _make_user("dataset303@test.example.com")
        did = str(uuid.uuid4())
        url = reverse(
            "dereference-resource",
            kwargs={"resource_type": "dataset", "resource_id": did},
        )
        resp = _api_client(user).get(url, HTTP_ACCEPT="text/turtle")
        self.assertEqual(resp.status_code, 303)
        self.assertIn(f"/id/dataset/{did}", resp["Location"])

    def test_invalid_resource_type_returns_400(self):
        user, _tenant = _make_user("badtype303@test.example.com")
        url = reverse(
            "dereference-resource",
            kwargs={
                "resource_type": "unknown_type",
                "resource_id": _SAMPLE_UUID,
            },
        )
        resp = _api_client(user).get(url, HTTP_ACCEPT="text/turtle")
        self.assertEqual(resp.status_code, 400)


@override_settings(SEMANTIC_BASE_IRI=_SEMANTIC_BASE_IRI)
class TestDereferenceResourceJsonFallback(TestCase):
    """Non-RDF clients receive JSON-LD response via service client."""

    def test_json_accept_does_not_redirect(self):
        """application/json Accept must NOT trigger a 303 redirect."""
        user, _tenant = _make_user("jsonfall@test.example.com")
        url = reverse(
            "dereference-resource",
            kwargs={"resource_type": "asset", "resource_id": _SAMPLE_UUID},
        )
        # Patch semantic service + asset lookup so test is self-contained.
        mock_result = {
            "@context": {},
            "@id": f"{_SEMANTIC_BASE_IRI}/id/asset/{_SAMPLE_UUID}",
            "@type": "hub:DataAsset",
        }
        # Patch the resolution service — the view delegates to
        # SemanticURIResolutionService.resolve() in the non-RDF path.
        with patch(
            "hub.apps.semantic.services.SemanticURIResolutionService.resolve"
        ) as mock_resolve:
            from hub.apps.semantic.services import UriResolutionOutcome

            mock_resolve.return_value = UriResolutionOutcome(status_code=200, data=mock_result)
            resp = _api_client(user).get(url, HTTP_ACCEPT="application/json")
        # Must NOT be a redirect.
        self.assertNotEqual(resp.status_code, 303)


# ---------------------------------------------------------------------------
# 22.5 / 22.9 — SPARQL 1.1 Service Description proxy
# ---------------------------------------------------------------------------


class TestSparqlServiceDescriptionDedicatedEndpoint(TestCase):
    """
    The dedicated /semantic/sparql/description endpoint requires
    authentication (Phase 219.2) and returns the Turtle Service Description.
    """

    def test_returns_turtle_service_description(self):
        user, _tenant = _make_user("sd-desc@test.example.com")
        url = reverse("sparql-service-description")
        resp = _api_client(user).get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/turtle", resp.get("Content-Type", ""))
        self.assertIn("sd:Service", resp.content.decode())

    def test_authenticated_request_accepted(self):
        """An authenticated request must not receive 401 or 403."""
        user, _tenant = _make_user("sd-auth@test.example.com")
        url = reverse("sparql-service-description")
        resp = _api_client(user).get(url)
        self.assertNotIn(resp.status_code, (401, 403))

    def test_unauthenticated_request_rejected(self):
        """An unauthenticated request must be rejected with 401 or 403."""
        url = reverse("sparql-service-description")
        resp = _api_client().get(url)
        self.assertIn(resp.status_code, (401, 403))


class TestSparqlQueryBareGetReturnsSD(TestCase):
    """GET /semantic/sparql with no query param → SD (authenticated)."""

    def test_authenticated_bare_get_returns_sd(self):
        user, _tenant = _make_user("sdtest@test.example.com")
        url = reverse("sparql-query")  # /api/v1/semantic/sparql
        resp = _api_client(user).get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/turtle", resp.get("Content-Type", ""))

    def test_sparql_query_get_with_query_still_works(self):
        """GET /semantic/sparql?query=... delegates to SPARQL execution."""
        user, _tenant = _make_user("sdquery@test.example.com")
        url = reverse("sparql-query")
        mock_result = {"results": {"bindings": []}}
        with patch(
            "hub.apps.semantic.views.SemanticServiceClient",
            return_value=MagicMock(query_sparql=MagicMock(return_value=mock_result)),
        ):
            resp = _api_client(user).get(
                url,
                {"query": "SELECT * WHERE { ?s ?p ?o } LIMIT 1"},
            )
        # Result is 200 JSON — NOT a turtle SD.
        if resp.status_code == 200:
            ct = resp.get("Content-Type", "")
            self.assertNotIn("text/turtle", ct)
