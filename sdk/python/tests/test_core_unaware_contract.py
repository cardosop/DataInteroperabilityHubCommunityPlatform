"""
P.5 — the SDK stays CORE-UNAWARE (deliberate, pinned decision).

The SDK is a thin HTTP client: it does not (and MUST not) know which
backend deployment it is talking to.  Against a core-only backend, a paid
endpoint 404s and the SDK surfaces its standard NotFoundError hierarchy —
the CLI owns the friendly "SaaS feature" gating (``_core_gates``); the SDK
must never import it.

These tests pin BOTH halves of that contract so the decision stops
reading as an unstated gap:
  * structural — no ``datahub_cli`` import anywhere in the SDK package;
  * behavioural — the SDK's 404 mapping knows only the MVP wire-format
    contract (a BACKEND property), and raises only SDK error types.
"""

from __future__ import annotations

import ast
from pathlib import Path

import httpx
import pytest

from datahub_interoperability.client import _maybe_raise_mvp_gated
from datahub_interoperability.errors import MVPGatedFeatureError, NotFoundError

SDK_ROOT = Path(__file__).resolve().parents[1]


def _make_404(url: str) -> httpx.Response:
    request = httpx.Request("GET", url)
    return httpx.Response(404, json={"detail": "Not Found."}, request=request)


def test_sdk_package_never_imports_the_cli():
    """Structural pin: the SDK has zero dependency on ``datahub_cli``."""
    offending: list[str] = []
    for py in SDK_ROOT.rglob("*.py"):
        if "__pycache__" in py.parts:
            continue
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("datahub_cli"):
                        offending.append(f"{py}: import {alias.name}")
            elif (
                isinstance(node, ast.ImportFrom)
                and node.module
                and node.module.startswith("datahub_cli")
            ):
                offending.append(f"{py}: from {node.module}")
    assert not offending, f"SDK imports the CLI: {offending}"


def test_paid_path_404_not_gated_by_the_sdk():
    """Behavioural pin: a PAID path 404ing on a core backend is NOT
    intercepted by the SDK's MVP-gate mapping — the SDK has no core-gate
    table; the caller falls through to the standard 404 error path (a
    plain NotFoundError)."""
    response = _make_404("https://hub.example.com/api/v1/marketplace/listings/")
    _maybe_raise_mvp_gated(response)  # must NOT raise — no SDK-side core gate


def test_mvp_gated_404_raises_sdk_own_error():
    """The MVP-gated mapping IS in the SDK (it is a wire-format contract
    of the BACKEND, not a client-side deployment decision), and it raises
    the SDK's own error hierarchy."""
    response = _make_404("https://hub.example.com/api/v1/baas/tenants/")
    with pytest.raises(NotFoundError):
        _maybe_raise_mvp_gated(response)
    assert issubclass(MVPGatedFeatureError, NotFoundError)
