"""
Tests for ``hub.apps.core.resilience.fallback`` — fallback strategies.
"""

from django.test import SimpleTestCase

from hub.apps.core.resilience.fallback import (
    FallbackError,
    FallbackStrategy,
    fallback,
)


class FallbackStrategyEnumTests(SimpleTestCase):
    """Verify FallbackStrategy enum members."""

    def test_all_strategies_exist(self):
        """All four documented strategies are present."""
        assert FallbackStrategy.RETURN_NONE.value == "RETURN_NONE"
        assert FallbackStrategy.RETURN_DEFAULT.value == "RETURN_DEFAULT"
        assert FallbackStrategy.RAISE_EXCEPTION.value == "RAISE_EXCEPTION"
        assert FallbackStrategy.CUSTOM_FUNCTION.value == "CUSTOM_FUNCTION"


class FallbackReturnNoneTests(SimpleTestCase):
    """Tests for RETURN_NONE strategy."""

    def test_returns_none_with_any_args(self):
        fn = fallback(FallbackStrategy.RETURN_NONE)
        assert fn() is None
        assert fn(1, 2, key="val") is None

    def test_ignores_default_value_parameter(self):
        fn = fallback(FallbackStrategy.RETURN_NONE, default_value="should_ignore")
        assert fn() is None


class FallbackReturnDefaultTests(SimpleTestCase):
    """Tests for RETURN_DEFAULT strategy."""

    def test_returns_default_value(self):
        fn = fallback(FallbackStrategy.RETURN_DEFAULT, default_value={"ok": True})
        assert fn() == {"ok": True}

    def test_returns_default_with_args(self):
        fn = fallback(FallbackStrategy.RETURN_DEFAULT, default_value=42)
        assert fn("ignored", x=1) == 42


class FallbackRaiseExceptionTests(SimpleTestCase):
    """Tests for RAISE_EXCEPTION strategy."""

    def test_raises_fallback_error(self):
        fn = fallback(FallbackStrategy.RAISE_EXCEPTION)
        with self.assertRaises(FallbackError):
            fn()
        assert "RAISE_EXCEPTION" in str(ctx.exception)


class FallbackCustomFunctionTests(SimpleTestCase):
    """Tests for CUSTOM_FUNCTION strategy."""

    def test_calls_provided_function(self):
        def my_handler(x, y=0):
            return x + y

        fn = fallback(FallbackStrategy.CUSTOM_FUNCTION, fallback_func=my_handler)
        assert fn(3, y=7) == 10

    def test_requires_fallback_func(self):
        with self.assertRaises(ValueError):
            fallback(FallbackStrategy.CUSTOM_FUNCTION, fallback_func=None)
        assert "fallback_func required" in str(ctx.exception)


class FallbackUnknownStrategyTests(SimpleTestCase):
    """Tests for invalid strategy."""

    def test_unknown_strategy_raises_value_error(self):
        with self.assertRaises(ValueError):
            fallback("INVALID")  # type: ignore[arg-type]
