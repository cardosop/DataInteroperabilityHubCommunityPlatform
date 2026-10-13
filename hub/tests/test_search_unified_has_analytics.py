"""
Phase 54.6 — UnifiedSearchView Analytics Tracking Test

Validates that UnifiedSearchView calls SearchEngine.track_search()
on successful queries.
"""

import inspect
import os

from django.test import TestCase


class UnifiedSearchAnalyticsTest(TestCase):
    """Test that UnifiedSearchView has analytics tracking."""

    def test_unified_search_calls_track_search(self):
        """UnifiedSearchView.get() must call SearchEngine.track_search()."""
        from hub.apps.search.views import UnifiedSearchView

        source = inspect.getsource(UnifiedSearchView)
        assert "track_search" in source, (
            "UnifiedSearchView must call SearchEngine.track_search() "
            "for analytics parity with SearchViewSet"
        )

    def test_unified_search_passes_query_and_result_count(self):
        """track_search call must include query and result_count."""
        from hub.apps.search.views import UnifiedSearchView

        source = inspect.getsource(UnifiedSearchView)
        assert "query=q" in source or "query=q," in source, (
            "track_search must receive the search query"
        )
        assert "result_count=" in source, "track_search must receive result_count"

    def test_analytics_failure_does_not_break_search(self):
        """track_search must be wrapped in a protective block (fire-and-forget)."""
        from hub.apps.search.views import UnifiedSearchView

        source = inspect.getsource(UnifiedSearchView)
        # The protective wrapper around track_search
        track_idx = source.index("track_search")
        # Find the nearest preceding paragraph before track_search
        wrapper = source[:track_idx]
        wrapper = wrapper[wrapper.rfind("\n\n") :]
        # The fire-and-forget contract is satisfied by either an explicit
        # try/except or contextlib.suppress (same guarantee: an analytics
        # failure must never break the search response).
        assert "try:" in wrapper or "suppress(" in wrapper, (
            "track_search must be inside try/except (or contextlib.suppress) "
            "to not break search"
        )

    def test_search_viewset_has_deprecation_headers_in_source(self):
        """SearchViewSet must have finalize_response with Deprecation header."""
        views_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "apps",
            "search",
            "views.py",
        )
        with open(views_path) as f:
            source = f.read()
        assert "Deprecation" in source
        assert "successor-version" in source
