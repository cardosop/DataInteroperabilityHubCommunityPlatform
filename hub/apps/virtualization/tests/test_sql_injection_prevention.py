"""Phase 87 – SQL injection prevention tests.

Verifies that ``VirtualizationService._normalise_query_params()`` and
``_normalise_query_params_named()`` correctly parameterise user-supplied
values so that injection payloads are **never** interpolated into the SQL
query string.

These are true unit tests — no database connections are needed because the
methods under test simply transform ``(query, params)`` tuples.
"""

from django.test import TestCase, override_settings

from hub.apps.virtualization.services import VirtualizationService


class TestSQLInjectionPrevention(TestCase):
    """Ensure malicious parameter values never appear in the query string."""

    def setUp(self):
        self.service = VirtualizationService.__new__(VirtualizationService)

    # ------------------------------------------------------------------
    # 1. DROP TABLE injection
    # ------------------------------------------------------------------

    def test_drop_table_injection_is_parameterised(self):
        """'; DROP TABLE users; -- must be a bound value, not query syntax."""
        query = "SELECT * FROM users WHERE name = :name"
        params = {"name": "'; DROP TABLE users; --"}
        safe_query, values = self.service._normalise_query_params(query, params)

        self.assertEqual(safe_query, "SELECT * FROM users WHERE name = %s")
        self.assertEqual(values, ("'; DROP TABLE users; --",))
        self.assertNotIn("DROP TABLE", safe_query)

    # ------------------------------------------------------------------
    # 2. UNION SELECT injection
    # ------------------------------------------------------------------

    def test_union_select_injection_is_parameterised(self):
        """UNION SELECT payload must remain a bound value, not SQL syntax."""
        query = "SELECT id FROM orders WHERE status = :status"
        params = {"status": "' UNION SELECT password FROM credentials --"}
        safe_query, values = self.service._normalise_query_params(query, params)

        self.assertEqual(safe_query, "SELECT id FROM orders WHERE status = %s")
        self.assertEqual(values, ("' UNION SELECT password FROM credentials --",))
        self.assertNotIn("UNION", safe_query)

    # ------------------------------------------------------------------
    # 3. Special characters in legitimate values
    # ------------------------------------------------------------------

    def test_value_with_apostrophe_succeeds(self):
        """O'Brien as a parameter value must pass through safely."""
        query = "SELECT * FROM customers WHERE last_name = :last_name"
        params = {"last_name": "O'Brien"}
        safe_query, values = self.service._normalise_query_params(query, params)

        self.assertEqual(safe_query, "SELECT * FROM customers WHERE last_name = %s")
        self.assertEqual(values, ("O'Brien",))

    def test_value_with_percent_succeeds(self):
        """100% as a parameter value must not confuse placeholder logic."""
        query = "SELECT * FROM metrics WHERE label = :label"
        params = {"label": "100%"}
        safe_query, values = self.service._normalise_query_params(query, params)

        self.assertEqual(safe_query, "SELECT * FROM metrics WHERE label = %s")
        self.assertEqual(values, ("100%",))

    # ------------------------------------------------------------------
    # 4. _normalise_query_params: placeholder conversion
    # ------------------------------------------------------------------

    def test_colon_placeholder_converted_to_positional(self):
        """:param placeholders are converted to %s with correct ordering."""
        query = "SELECT * FROM t WHERE a = :alpha AND b = :beta"
        params = {"alpha": 1, "beta": 2}
        safe_query, values = self.service._normalise_query_params(query, params)

        self.assertEqual(safe_query, "SELECT * FROM t WHERE a = %s AND b = %s")
        self.assertEqual(values, (1, 2))

    def test_pyformat_placeholder_converted_to_positional(self):
        """%(param)s placeholders are converted to %s with correct ordering."""
        query = "SELECT * FROM t WHERE x = %(foo)s AND y = %(bar)s"
        params = {"foo": "hello", "bar": "world"}
        safe_query, values = self.service._normalise_query_params(query, params)

        self.assertEqual(safe_query, "SELECT * FROM t WHERE x = %s AND y = %s")
        self.assertEqual(values, ("hello", "world"))

    def test_mixed_placeholders_converted_to_positional(self):
        """A query mixing :name and %(name)s styles is fully normalised."""
        query = "SELECT * FROM t WHERE a = :alpha AND b = %(beta)s"
        params = {"alpha": "A", "beta": "B"}
        safe_query, values = self.service._normalise_query_params(query, params)

        self.assertEqual(safe_query, "SELECT * FROM t WHERE a = %s AND b = %s")
        self.assertEqual(values, ("A", "B"))

    def test_mixed_placeholders_reversed_order(self):
        """Parameters must be in query-appearance order, not processing order."""
        query = "SELECT * FROM t WHERE b = %(beta)s AND a = :alpha"
        params = {"alpha": "A", "beta": "B"}
        safe_query, values = self.service._normalise_query_params(query, params)

        self.assertEqual(safe_query, "SELECT * FROM t WHERE b = %s AND a = %s")
        # beta appears first in the query, so B must come first
        self.assertEqual(values, ("B", "A"))

    def test_duplicate_placeholder_all_occurrences_bound(self):
        """Same placeholder used twice → value appears twice in order."""
        query = "SELECT * FROM t WHERE id = :id OR creator = :id"
        params = {"id": 42}
        safe_query, values = self.service._normalise_query_params(query, params)

        self.assertEqual(safe_query, "SELECT * FROM t WHERE id = %s OR creator = %s")
        self.assertEqual(values, (42, 42))

    # ------------------------------------------------------------------
    # 5. _normalise_query_params_named: SQLAlchemy conversion
    # ------------------------------------------------------------------

    def test_named_converts_pyformat_to_colon(self):
        """%(param)s placeholders are converted to :param for SQLAlchemy."""
        query = "SELECT * FROM t WHERE x = %(foo)s AND y = %(bar)s"
        params = {"foo": 10, "bar": 20}
        safe_query, params_out = self.service._normalise_query_params_named(query, params)

        self.assertEqual(safe_query, "SELECT * FROM t WHERE x = :foo AND y = :bar")
        self.assertEqual(params_out, {"foo": 10, "bar": 20})

    def test_named_preserves_colon_placeholders(self):
        """:param placeholders should pass through unchanged for SQLAlchemy."""
        query = "SELECT * FROM t WHERE a = :alpha"
        params = {"alpha": "val"}
        safe_query, params_out = self.service._normalise_query_params_named(query, params)

        self.assertEqual(safe_query, "SELECT * FROM t WHERE a = :alpha")
        self.assertEqual(params_out, {"alpha": "val"})

    def test_named_injection_stays_in_params(self):
        """Injection payload is kept in the params dict, not in the query."""
        query = "SELECT * FROM t WHERE col = %(col)s"
        params = {"col": "'; DROP TABLE t; --"}
        safe_query, params_out = self.service._normalise_query_params_named(query, params)

        self.assertEqual(safe_query, "SELECT * FROM t WHERE col = :col")
        self.assertNotIn("DROP TABLE", safe_query)
        self.assertEqual(params_out["col"], "'; DROP TABLE t; --")

    # ------------------------------------------------------------------
    # 6. Feature flag fallback
    # ------------------------------------------------------------------

    @override_settings(PARAMETERIZED_VIRTUAL_QUERIES=False)
    def test_feature_flag_disabled_uses_legacy_interpolation(self):
        """When PARAMETERIZED_VIRTUAL_QUERIES=False, values are string-interpolated."""
        query = "SELECT * FROM t WHERE name = :name"
        params = {"name": "Alice"}
        safe_query, values = self.service._normalise_query_params(query, params)

        # Legacy path interpolates the value directly into the query text
        self.assertEqual(safe_query, "SELECT * FROM t WHERE name = Alice")
        # No positional params returned in legacy mode
        self.assertEqual(values, ())

    @override_settings(PARAMETERIZED_VIRTUAL_QUERIES=False)
    def test_feature_flag_disabled_named_uses_legacy_interpolation(self):
        """Named variant also falls back to legacy when flag is disabled."""
        query = "SELECT * FROM t WHERE id = %(id)s"
        params = {"id": "42"}
        safe_query, params_out = self.service._normalise_query_params_named(query, params)

        self.assertEqual(safe_query, "SELECT * FROM t WHERE id = 42")
        self.assertEqual(params_out, {})

    # ------------------------------------------------------------------
    # 7. Empty parameters
    # ------------------------------------------------------------------

    def test_empty_params_returns_query_unchanged(self):
        """An empty params dict returns the original query with no values."""
        query = "SELECT 1"
        safe_query, values = self.service._normalise_query_params(query, {})

        self.assertEqual(safe_query, "SELECT 1")
        self.assertEqual(values, ())

    def test_empty_params_named_returns_query_unchanged(self):
        """Named variant with empty params returns query and empty dict."""
        query = "SELECT 1"
        safe_query, params_out = self.service._normalise_query_params_named(query, {})

        self.assertEqual(safe_query, "SELECT 1")
        self.assertEqual(params_out, {})

    def test_none_params_returns_query_unchanged(self):
        """None/falsy params should be handled the same as empty dict."""
        query = "SELECT 1"
        safe_query, values = self.service._normalise_query_params(query, None)

        self.assertEqual(safe_query, "SELECT 1")
        self.assertEqual(values, ())
