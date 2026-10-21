"""
W12.9 — drf-spectacular silence-fixing pin.

The settings module used to install THREE suppression layers for
drf-spectacular's schema-introspection diagnostics (a stderr filter, a
``warnings.filterwarnings`` ignore, and ``DISABLE_ERRORS_AND_WARNINGS``
gated on test mode).  Those layers hid ~900 real OpenAPI schema defects
per generation: untyped path parameters, SerializerMethodFields without
return hints, invalid parameter annotations, unresolved authenticators,
duplicate operationIds, and 72 views spectacular could not introspect.

This test is the honest replacement for the suppressions: it generates
the full public schema in-process and asserts that the run produced ZERO
diagnostics (the module-level ``GENERATOR_STATS`` caches accumulate
regardless of any silencing flag, so this pin cannot be gamed), and that
the previously-broken endpoints now carry REAL schemas (not silence via
``@extend_schema(exclude=True)``).

TDD history: written RED against the pre-fix tree, where generation
emitted 173 warnings (105 unique) + 727 errors (72 unique).
"""

import contextlib
import io

import pytest
from drf_spectacular.drainage import GENERATOR_STATS
from drf_spectacular.generators import SchemaGenerator


@pytest.mark.django_db
class TestSchemaGenerationIsClean:
    """Schema generation must emit zero drf-spectacular diagnostics."""

    def test_generation_emits_no_diagnostics(self):
        before = set(GENERATOR_STATS._warn_cache) | set(GENERATOR_STATS._error_cache)
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            SchemaGenerator().get_schema(request=None, public=True)
        after = set(GENERATOR_STATS._warn_cache) | set(GENERATOR_STATS._error_cache)
        new_diagnostics = after - before

        assert new_diagnostics == set(), (
            "drf-spectacular emitted diagnostics during schema generation:\n\n"
            + "\n\n".join(sorted(new_diagnostics))
        )
        assert stderr.getvalue() == "", (
            "drf-spectacular printed to stderr during schema generation:\n\n"
            + stderr.getvalue()
        )

    def test_previously_broken_endpoints_have_real_schemas(self):
        """Endpoints the old suppressions hid must now carry real schemas."""
        schema = SchemaGenerator().get_schema(request=None, public=True)
        paths = schema["paths"]

        # draft_save had "Defaulting to generic free-form object" for its
        # PUT request body — it must now reference a real serializer.
        drafts_save = paths["/api/v1/drafts/save/"]
        assert "put" in drafts_save
        request_body = drafts_save["put"].get("requestBody", {})
        assert "content" in request_body, (
            "draft save still falls back to a free-form request body"
        )
        put_content = request_body["content"]
        assert "application/json" in put_content
        assert "schema" in put_content["application/json"]
        # The schema must NOT be the generic free-form fallback.
        assert drafts_save["put"]["requestBody"]["content"]["application/json"][
            "schema"
        ] != {"type": "object"}, (
            "draft save request body is still the generic free-form fallback"
        )

        # federated-import POST had the same free-form fallback.
        imports = paths["/api/v1/integrations/federated-import/imports/"]
        assert "post" in imports
        assert "requestBody" in imports["post"]
        assert imports["post"]["requestBody"]["content"]["application/json"]["schema"] != {
            "type": "object"
        }, "federated-import request body is still the generic free-form fallback"

        # The SSE notification stream was ignored ("unable to guess
        # serializer", "No response body") — it must now describe the
        # event-stream response it actually produces.
        stream = paths["/api/v1/notifications/stream/"]
        assert "get" in stream, "notification SSE stream has no GET operation"
        responses = stream["get"].get("responses", {})
        assert "200" in responses, "notification SSE stream lost its 200 response"
        stream_content = responses["200"].get("content", {})
        assert "text/event-stream" in stream_content, (
            "notification SSE stream response does not declare "
            "text/event-stream content"
        )

    def test_typed_path_parameters_survive_into_the_schema(self):
        """Previously-untyped path params must now be typed in the schema."""
        schema = SchemaGenerator().get_schema(request=None, public=True)
        paths = schema["paths"]

        # social review detail — previously "could not derive type of path
        # parameter id ... Defaulting to string".  The router is regex-mode,
        # so the typed lookup regex surfaces as string + a UUID pattern
        # (the honest shape for what the URL actually accepts).
        review_detail = paths["/api/v1/social/reviews/{id}/"]
        id_params = [
            p
            for method in review_detail.values()
            for p in method.get("parameters", [])
            if p.get("in") == "path" and p.get("name") == "id"
        ]
        assert id_params, "review detail lost its id path parameter"
        for p in id_params:
            assert p["schema"]["type"] == "string"
            assert "pattern" in p["schema"], (
                f"review id param lost its UUID pattern: {p}"
            )
            # spectacular anchors the pattern (^...$) for regex-mode URLs.
            assert r"[0-9a-f]{8}-[0-9a-f]{4}" in p["schema"]["pattern"], (
                f"review id pattern is not the UUID shape: {p}"
            )
