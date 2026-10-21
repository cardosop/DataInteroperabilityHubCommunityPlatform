"""
Phase 42 — Normalization Registry Singleton Test

Verifies that the normalization package re-exports point to the exact same
_NORMALIZER_REGISTRY dict instance as normalization_engine.py, eliminating the
historical multi-instance bug caused by importlib.util.spec_from_file_location.
"""

from hub.apps.contracts.normalization import (
    _NORMALIZER_REGISTRY,
    get_normalizer,
    register_normalizer,
)
from hub.apps.contracts.normalization_engine import (
    _NORMALIZER_REGISTRY as reg2,
)
from hub.apps.contracts.normalization_engine import (
    get_normalizer as ge,
)


def test_registry_is_same_object():
    """The package __init__ and the engine module must share the same registry dict."""
    assert _NORMALIZER_REGISTRY is reg2


def test_get_normalizer_is_same_function():
    """get_normalizer imported via package must be the same function object."""
    assert get_normalizer is ge


def test_registered_normalizer_is_found():
    """A normalizer registered via the package is discoverable via the engine module."""

    class _TestNormalizer:
        spec_type = "TEST_PHASE42"

        def supports(self, t, v, d):
            return t == "TEST_PHASE42" and v == "0.0"

        def normalize(self, *a):
            pass

    register_normalizer(_TestNormalizer())
    assert ge("TEST_PHASE42", "0.0", {}) is not None

    # Clean up to avoid polluting the registry for other tests
    _NORMALIZER_REGISTRY.pop("TEST_PHASE42", None)
