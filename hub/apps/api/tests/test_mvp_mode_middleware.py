"""
Phase 216.0.4 — MVP mode middleware coverage.

Tests:
  1. Every prefix in MVP_GATED_RELATIVE_PREFIXES returns 404 when MVP_MODE=true.
  2. Every prefix is reachable (200 or 401, not 404) when MVP_MODE=false.
  3. Every prefix in mvp_mode.py has a corresponding URL route (catches typos).
  4. Non-gated paths (/api/v1/assets/, /api/v1/auth/me/) pass through in both modes.

The middleware reads ``settings.MVP_MODE`` (not ``os.environ``), so we use
``@override_settings(MVP_MODE=True/False)`` throughout.
"""
import pytest
from django.test import TestCase, override_settings
from django.urls import resolve, Resolver404

from hub.apps.api.mvp_mode import (
    MVP_GATED_RELATIVE_PREFIXES,
    API_V1_PREFIX,
    is_mvp_gated_api_v1_path,
)

pytestmark = pytest.mark.django_db


class MvpGatedPrefixRoutabilityTest(TestCase):
    """Every prefix in MVP_GATED_RELATIVE_PREFIXES must resolve to at least one URL route."""

    def test_every_gated_prefix_has_a_url_route(self):
        """Catches typos: if a prefix doesn't match any URL, the gate is useless."""
        unroutable = []
        for prefix in MVP_GATED_RELATIVE_PREFIXES:
            test_path = f"{API_V1_PREFIX}{prefix}"
            try:
                resolve(test_path)
            except Resolver404:
                unroutable.append(prefix)

        if unroutable:
            self.fail(
                f"MVP_GATED_RELATIVE_PREFIXES contains prefixes with no URL route "
                f"(typo?): {unroutable}. Either fix the prefix or add a URL pattern."
            )


class MvpModeGatingTest(TestCase):
    """is_mvp_gated_api_v1_path correctly classifies paths."""

    def test_gated_paths_detected(self):
        for prefix in MVP_GATED_RELATIVE_PREFIXES:
            path = f"{API_V1_PREFIX}{prefix}some-resource/"
            self.assertTrue(
                is_mvp_gated_api_v1_path(path),
                f"{path} should be gated but is_mvp_gated_api_v1_path returned False",
            )

    def test_non_gated_paths_not_detected(self):
        non_gated = [
            "/api/v1/assets/",
            "/api/v1/auth/me/",
            "/api/v1/compliance/runs/",
            "/api/v1/contracts/",
            "/api/v1/files/upload/",
            "/api/v1/tenants/",
        ]
        for path in non_gated:
            self.assertFalse(
                is_mvp_gated_api_v1_path(path),
                f"{path} should NOT be gated but is_mvp_gated_api_v1_path returned True",
            )

    def test_non_api_v1_paths_not_gated(self):
        non_api = [
            "/health/",
            "/admin/",
            "/api/v2/mesh/",
            "/mesh/",
        ]
        for path in non_api:
            self.assertFalse(
                is_mvp_gated_api_v1_path(path),
                f"{path} should not be gated (not under /api/v1/)",
            )


class MvpModeMiddlewareIntegrationTest(TestCase):
    """End-to-end middleware test via Django test client.

    The middleware reads ``settings.MVP_MODE`` per-request (not os.environ),
    so we use ``@override_settings`` to toggle the gate.
    """

    @override_settings(MVP_MODE=True)
    def test_gated_path_returns_404_when_mvp_mode_true(self):
        for prefix in MVP_GATED_RELATIVE_PREFIXES:
            path = f"{API_V1_PREFIX}{prefix}"
            response = self.client.get(path)
            self.assertEqual(
                response.status_code,
                404,
                f"Expected 404 for {path} with MVP_MODE=True, got {response.status_code}",
            )

    @override_settings(MVP_MODE=False)
    def test_gated_path_not_404_when_mvp_mode_false(self):
        for prefix in MVP_GATED_RELATIVE_PREFIXES:
            path = f"{API_V1_PREFIX}{prefix}"
            response = self.client.get(path)
            self.assertNotEqual(
                response.status_code,
                404,
                f"{path} should be reachable (200/401/403) with MVP_MODE=False, got 404",
            )

    @override_settings(MVP_MODE=True)
    def test_non_gated_path_passes_through_in_mvp_mode(self):
        # /api/v1/auth/me/ should return 401 (not authenticated), not 404
        response = self.client.get("/api/v1/auth/me/")
        self.assertIn(
            response.status_code,
            (200, 401, 403),
            f"/api/v1/auth/me/ should pass through MVP gate, got {response.status_code}",
        )


class MvpGatedPrefixCompletenessTest(TestCase):
    """Verify the prefix list covers all expected post-MVP namespaces."""

    def test_expected_prefixes_are_gated(self):
        expected = {
            "mesh/",
            "virtualization/",
            "integrations/",
            "baas/",
            "ml/",
            "ai/",
            "transformation/",
            "social/",
            "scheduled-ingestions/",
            "scheduled-exports/",
            # Added by Track A PR 1 — close backend drift: these were mounted in
            # hub/apps/api/urls.py but absent from MVP_GATED_RELATIVE_PREFIXES.
            "developer/",
            # Additional gated prefixes (batch-7-4):
            # NOTE: "admin/", "lineage/", and "quality/" are NOT gated
            # (no standalone URL routes for those prefixes).
            "dpia/",
            "ropa/",
        }
        actual = set(MVP_GATED_RELATIVE_PREFIXES)
        missing = expected - actual
        self.assertFalse(
            missing,
            f"Expected gated prefixes missing from MVP_GATED_RELATIVE_PREFIXES: {missing}",
        )


# Track A PR 4: explicit MVP-core allowlist. Every prefix mounted in
# hub/apps/api/urls.py must be classified as either MVP-core (this set) or
# non-MVP (MVP_GATED_RELATIVE_PREFIXES). Adding a new mount without
# classifying it fails the drift test below — preventing the same kind of
# "mounted but ungated" bug Track A PR 1 fixed for /search and /developer.
MVP_CORE_PREFIXES = frozenset(
    {
        "auth/",
        "tenants/",
        "users/",
        "audit/",
        "files/",
        "datasets/",
        "jobs/",
        "contracts/",
        "security/",
        "assets/",
        "dq/",
        "compliance/",
        "semantic/",
        "marketplace/",
        "webhooks/",
        "events/",
        "notifications/",
        "governance/",
        "billing/",
        "platform/",
        "versioning/",
        "workflows/",
        # E2E test endpoints — gated by @require_e2e_token (PR 1) and the
        # hub.E002 deploy check, NOT by MVP_MODE. They are MVP-safe to mount
        # because the token gate makes them inaccessible without provisioning.
        "test/",
        # Additional MVP-core prefixes (batch-7-4):
        # Phase 273.1 — /search permanently MVP-in-scope.
        # /admin, /lineage, and /quality have no standalone routes
        # (only sub-paths), so they're classified as core rather than gated.
        "admin/",
        "analytics/",
        "capabilities/",
        "drafts/",
        "lineage/",
        "public/",
        "quality/",
        "search/",
    }
)


class EveryMountedPrefixIsClassifiedTest(TestCase):
    """Drift safety: enumerate every mounted /api/v1/* prefix and assert
    each is classified as MVP-core or MVP-gated. No third state."""

    def _enumerate_api_v1_prefixes(self) -> set[str]:
        """Return every leaf prefix mounted under /api/v1/.

        Walks one level of include() composition so that
        `path("", include("hub.apps.social.urls"))` (where the social app
        registers its own "social/" prefix) shows up as "social/" — not "".

        Raw `re_path` catch-all entries (``api_not_found``) and pure
        non-prefix mounts (e.g. ``openapi.json``) are excluded — they are
        not first-class API surfaces and not subject to MVP gating.
        """
        from django.urls import get_resolver

        prefixes: set[str] = set()
        resolver = get_resolver()
        api_v1_resolver = None
        for entry in resolver.url_patterns:
            pattern_str = str(getattr(entry, "pattern", ""))
            if pattern_str == "api/v1/":
                api_v1_resolver = entry
                break
        if api_v1_resolver is None:
            self.fail("/api/v1/ include not found in URL conf")

        for entry in api_v1_resolver.url_patterns:
            pattern_str = str(getattr(entry, "pattern", ""))

            # Skip raw re_path catch-alls.
            if pattern_str.startswith("^") or pattern_str.startswith("(?"):
                continue

            # Skip non-prefix endpoints (no trailing slash + has dot →
            # likely a file like openapi.json / openapi.yaml).
            if "." in pattern_str and not pattern_str.endswith("/"):
                continue

            # Empty prefix include() — walk one level deeper to find what
            # the inner urlconf actually mounts (e.g. "social/").
            if pattern_str == "":
                inner = getattr(entry, "url_patterns", None)
                if inner is None:
                    continue
                for sub in inner:
                    sub_pattern = str(getattr(sub, "pattern", ""))
                    if sub_pattern and not sub_pattern.startswith("^"):
                        # Take only the first segment up to and including '/'
                        head = sub_pattern.split("/", 1)[0] + "/"
                        if head and head != "/":
                            prefixes.add(head)
                continue

            # Normal prefix mount — keep only the first path segment.
            head = pattern_str.split("/", 1)[0] + "/"
            if head and head != "/":
                prefixes.add(head)

        return prefixes

    def test_every_mounted_prefix_is_classified(self):
        gated = set(MVP_GATED_RELATIVE_PREFIXES)
        core = set(MVP_CORE_PREFIXES)

        # Both sets must be disjoint — a prefix can't be both gated and
        # core, that would be ambiguous.
        overlap = gated & core
        self.assertFalse(
            overlap,
            f"Prefix appears in BOTH MVP_CORE_PREFIXES and "
            f"MVP_GATED_RELATIVE_PREFIXES: {overlap}. Pick one.",
        )

        mounted = self._enumerate_api_v1_prefixes()
        unclassified = mounted - gated - core
        self.assertFalse(
            unclassified,
            f"Mounted /api/v1/ prefixes not classified as either core or "
            f"gated: {sorted(unclassified)}. Either add them to "
            f"MVP_CORE_PREFIXES (frontend-visible / MVP-safe) or to "
            f"MVP_GATED_RELATIVE_PREFIXES in hub/apps/api/mvp_mode.py.",
        )

        # Inverse: a classification entry that doesn't match a real mount
        # is harmless but stale — flag it so the lists stay tidy.
        stale_gated = gated - mounted
        stale_core = core - mounted
        self.assertFalse(
            stale_gated,
            f"MVP_GATED_RELATIVE_PREFIXES has entries with no matching "
            f"URL mount (typo or stale): {sorted(stale_gated)}",
        )
        # `test/` is the parent of four ensure_e2e_* paths; the enumeration
        # only sees the first segment, so allow it to be in core even when
        # the four sub-paths are what's mounted.
        unexpected_stale_core = stale_core - {"test/"}
        self.assertFalse(
            unexpected_stale_core,
            f"MVP_CORE_PREFIXES has entries with no matching URL mount: "
            f"{sorted(unexpected_stale_core)}",
        )
