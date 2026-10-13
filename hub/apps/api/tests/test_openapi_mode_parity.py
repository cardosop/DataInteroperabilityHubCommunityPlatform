"""P.3a — OpenAPI paid-path parity between deployment modes.

The 2026-08-14 "632 full vs 493 core paths" figure was a one-off manual
verification. This module turns it into a live test: generate the schema
with the SAME pipeline ``scripts/contract_test_openapi.py`` uses
(drf-spectacular ``SchemaGenerator(urlconf="hub.urls")`` →
``OpenAPISpecValidator.enhance_spec`` → ``OpenAPISpecEnhancer.enhance_spec``)
and assert the paid prefixes against the LIVE URL registry
(``hub.apps.api.paid_urls._PAID_URLPATTERNS``) — expectations derived from
the registry itself, never a second hand-maintained list.

Because the URLconf is loaded once per process (paid mounts included only
when `not HUB_CORE_ONLY`), each mode is asserted in the process that has
that mode:

- full mode: every prefix a paid app registered appears in the schema;
- core-only: NO paid prefix appears — the schema is core-shaped.

The mode-detection half of the test also guards against the vacuous-pass
failure mode: in core-only the paid-app set is empty, so "no paid path
present" must be proven against a non-empty EXPECTED list sourced from the
manifest (the paid app names are manifest facts even in a core process),
not against an empty registry.
"""

from __future__ import annotations

import pytest
from django.test import TestCase

from hub.apps.api import paid_urls
from hub.apps.manifest import is_core_only, paid_app_module_names

pytestmark = pytest.mark.django_db(transaction=True)


#: The schema-generation pipeline — identical to
#: scripts/contract_test_openapi.py::_generate_current_schema (the runtime /
#: regenerate-openapi-spec pipeline).
def _generate_schema() -> dict:
    from django.test import RequestFactory
    from drf_spectacular.generators import SchemaGenerator

    from hub.apps.api.openapi_enhancement import OpenAPISpecEnhancer
    from hub.apps.api.openapi_validation import OpenAPISpecValidator

    factory = RequestFactory()
    request = factory.get("/api/v1/")
    # RequestFactory does not attach a user; drf-spectacular's schema
    # introspection touches request.user (endpoint-level gating), so bind
    # an anonymous user exactly like test_capabilities.py:180-182 does.
    from django.contrib.auth.models import AnonymousUser

    request.user = AnonymousUser()
    request.auth = None  # drf-spectacular plumbing.py:1277 copies it too
    generator = SchemaGenerator(urlconf="hub.urls")
    schema = generator.get_schema(request=request, public=True)
    schema = OpenAPISpecValidator.enhance_spec(schema)
    schema = OpenAPISpecEnhancer.enhance_spec(schema)
    return schema


def _registered_paid_prefixes() -> list[str]:
    """Paid URL prefixes from the live registry (URLResolver/URLPattern).

    The registry holds a mix of ``URLResolver`` (include-style mounts) and
    ``URLPattern`` (single-view mounts, e.g. the billing review-queue).
    ``describe()`` renders the regex with quotes and, for URLPattern, the
    route name suffix — strip both to get the path prefix.
    """
    prefixes: list[str] = []
    for pattern in paid_urls._PAID_URLPATTERNS:
        described = getattr(pattern, "pattern", None)
        if described is None:
            continue
        prefix = described.describe().strip("^$").strip("'").split("' [name=")[0]
        prefix = prefix.rstrip("/")
        if prefix:
            prefixes.append(prefix)
    return sorted(set(prefixes))


def _paid_app_name_words() -> set[str]:
    """App names of the paid layer (e.g. ``marketplace``) from the manifest.

    Manifest facts are available in BOTH modes — this is what makes the
    core-only absence assertion non-vacuous.
    """
    return {name.rsplit(".", 1)[-1] for name in paid_app_module_names()}


def _operation_tags(schema: dict) -> set[str]:
    """Every operation-level tag in the schema.

    drf-spectacular tags each operation with its viewset's app name — the
    ownership signal (a paid viewset carries e.g. ``Marketplace``). Path
    WORDS are not ownership (core ``integrations/marketplace`` endpoints
    are core-owned); top-level tags are not either (unused registrations
    appear there with zero operations in core mode — measured).
    """
    tags: set[str] = set()
    for ops in schema.get("paths", {}).values():
        for method, op in ops.items():
            if method.startswith("x-") or not isinstance(op, dict):
                continue
            tags.update(op.get("tags", []))
    return tags


def _is_paid_tag(tag: str, paid_words: set[str]) -> bool:
    """Whether an operation tag names a paid app.

    Exact app-name match only — substring matching is unusable here:
    ``ml`` matches inside ``openapi.yaml`` and ``ai`` inside countless
    English words (measured on the core schema). The convention is the
    viewset's app name (possibly space-separated, e.g. ``Rate limiting``).
    """
    normalized = tag.lower().replace("_", " ")
    return any(normalized == word or normalized == word.replace("_", " ") for word in paid_words)


class OpenAPIModeParityTests(TestCase):
    def test_mode_consistent_paid_prefix_parity(self):
        schema = _generate_schema()
        paths = schema.get("paths", {})
        registered = _registered_paid_prefixes()
        # GraphQL mounts are non-DRF views — drf-spectacular documents REST
        # endpoints only, so /graphql* correctly never appears in the
        # schema in EITHER mode. They are pinned separately below.
        drf_prefixes = {prefix for prefix in registered if not prefix.startswith("graphql")}
        expected_path_prefixes = {f"/{prefix}" for prefix in drf_prefixes}
        # A mount prefix like /api/v1/billing never appears as a literal
        # path key — its children do (e.g. /api/v1/billing/invoices/).
        present = {
            prefix
            for prefix in expected_path_prefixes
            if any(path == prefix or path.startswith(prefix + "/") for path in paths)
        }

        if is_core_only():
            # No paid-prefix path may exist, and no operation may be owned
            # by a paid viewset. Prove the expectation is non-vacuous FIRST:
            # the paid registry may be empty in a core process (ready()
            # never ran), so expectedness comes from the manifest's paid
            # app names. Ownership is read from OPERATION TAGS (the paid
            # viewset carries its app name), not from path words — core
            # integrations/marketplace endpoints are core-owned (measured:
            # zero paid-tagged operations in the core schema).
            paid_words = _paid_app_name_words()
            assert paid_words, "manifest must name paid apps in core mode"
            leaked = sorted(
                {tag for tag in _operation_tags(schema) if _is_paid_tag(tag, paid_words)}
            )
            assert not leaked, f"paid operations leaked into the core schema: {leaked}"
            assert not present
        else:
            missing = expected_path_prefixes - present
            assert registered, (
                "full mode must have paid prefixes registered before the "
                "schema is generated (URLconf loads after ready())"
            )
            assert not missing, (
                f"paid prefixes registered but absent from the full schema: {sorted(missing)}"
            )

    def test_schema_generation_pipeline_is_healthy(self):
        """The pipeline itself must not crash in either mode."""
        schema = _generate_schema()
        assert schema.get("paths"), "schema generation must produce paths"
        assert schema.get("info", {}).get("title")

    def test_full_mode_has_paid_owned_operations(self):
        """Guard-the-guard: the tag-ownership signal must actually fire in
        full mode, otherwise the core-mode 'no paid tags' assertion could
        pass because paid viewsets never tag their operations."""
        if is_core_only():
            self.skipTest("paid ownership exists only in full mode")
        paid_words = _paid_app_name_words()
        paid_tags = {
            tag for tag in _operation_tags(_generate_schema()) if _is_paid_tag(tag, paid_words)
        }
        assert paid_tags, "full mode must contain paid-owned operations"

    def test_graphql_mounts_are_registered_but_not_in_rest_schema(self):
        """GraphQL endpoints are non-DRF; the schema omits them by design —
        in BOTH modes. The registry fact itself is still pinned here so a
        dropped graphql registration fails the suite."""
        registered = _registered_paid_prefixes()
        graphql_prefixes = [p for p in registered if p.startswith("graphql")]
        if is_core_only():
            assert graphql_prefixes == []
        else:
            assert graphql_prefixes, "full mode must register the graphql mounts"
        schema = _generate_schema()
        for prefix in graphql_prefixes:
            assert not any(
                path == f"/{prefix}" or path.startswith(f"/{prefix}/")
                for path in schema.get("paths", {})
            ), f"{prefix} must not appear in the REST schema"
