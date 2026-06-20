"""
Phase 79.6 — OpenTelemetry tracing setup tests.

These tests exercise the setup_opentelemetry_fastapi() and
get_tracer_fastapi() helper functions.  Since the OpenTelemetry
SDK may or may not be installed in the test environment, the
tests focus on the enable/disable logic and graceful degradation.
"""


# ── Disabled when env var unset ─────────────────────────────────


def test_setup_returns_none_when_disabled(monkeypatch):
    """setup_opentelemetry_fastapi returns None when
    OPENTELEMETRY_ENABLED is not 'true'."""
    monkeypatch.delenv("OPENTELEMETRY_ENABLED", raising=False)
    from shared.tracing import setup_opentelemetry_fastapi

    result = setup_opentelemetry_fastapi("test-service")
    assert result is None


def test_get_tracer_returns_none_when_disabled(monkeypatch):
    """get_tracer_fastapi returns None when OPENTELEMETRY_ENABLED
    is not 'true'."""
    monkeypatch.delenv("OPENTELEMETRY_ENABLED", raising=False)
    from shared.tracing import get_tracer_fastapi

    result = get_tracer_fastapi("test")
    assert result is None


# ── Explicitly disabled ──────────────────────────────────────────


def test_setup_returns_none_when_explicitly_false(monkeypatch):
    """Calling setup with OPENTELEMETRY_ENABLED=false returns None."""
    monkeypatch.setenv("OPENTELEMETRY_ENABLED", "false")
    from shared.tracing import setup_opentelemetry_fastapi

    result = setup_opentelemetry_fastapi("test-service")
    assert result is None


# ── Graceful degradation when otel packages missing ──────────────


def test_setup_handles_missing_otel_packages(monkeypatch):
    """If OpenTelemetry packages are missing, setup returns None
    gracefully (ImportError caught)."""
    monkeypatch.setenv("OPENTELEMETRY_ENABLED", "true")
    import sys

    import shared.tracing as tracing_mod

    # Temporarily block otel imports
    blocked = {}
    for mod_name in list(sys.modules):
        if "opentelemetry" in mod_name:
            blocked[mod_name] = sys.modules.pop(mod_name)

    if hasattr(__builtins__, "__import__"):
        original_import = __builtins__.__import__
    else:
        original_import = __import__

    def _mock_import(name, *args, **kwargs):
        if "opentelemetry" in name:
            raise ImportError(f"No module named '{name}'")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", _mock_import)

    try:
        result = tracing_mod.setup_opentelemetry_fastapi("svc")
        assert result is None
    finally:
        # Restore blocked modules
        sys.modules.update(blocked)


# ── get_tracer_fastapi graceful degradation ──────────────────────


def test_get_tracer_handles_missing_otel_packages(monkeypatch):
    """If OpenTelemetry packages are missing, get_tracer_fastapi
    returns None gracefully."""
    monkeypatch.setenv("OPENTELEMETRY_ENABLED", "true")
    import sys

    import shared.tracing as tracing_mod

    blocked = {}
    for mod_name in list(sys.modules):
        if "opentelemetry" in mod_name:
            blocked[mod_name] = sys.modules.pop(mod_name)

    if hasattr(__builtins__, "__import__"):
        original_import = __builtins__.__import__
    else:
        original_import = __import__

    def _mock_import(name, *args, **kwargs):
        if "opentelemetry" in name:
            raise ImportError(f"No module named '{name}'")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", _mock_import)

    try:
        result = tracing_mod.get_tracer_fastapi("test")
        assert result is None
    finally:
        sys.modules.update(blocked)
