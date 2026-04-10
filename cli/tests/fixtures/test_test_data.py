"""
Phase 216.X.9 — unit tests for ``cli/tests/fixtures/test_data.py``.

Covers ``fresh_id``, ``unique_port``, and the xdist-worker-id helper.
No mocks, no stubs — exercises the real OS port allocation, real env
vars, and the real uuid generator.
"""
from __future__ import annotations

import socket

import pytest

from tests.fixtures.test_data import (
    _xdist_worker_id,
    fresh_id,
    reset_unique_port_pool_for_tests,
    unique_port,
)


# ---------------------------------------------------------------------------
# fresh_id
# ---------------------------------------------------------------------------


def test_fresh_id_returns_unique_values_within_a_worker() -> None:
    ids = {fresh_id("asset") for _ in range(1024)}
    assert len(ids) == 1024, "uuid suffix MUST collide-resist within a worker"


@pytest.mark.parametrize("prefix", ["asset", "contract", "tenant", "webhook"])
def test_fresh_id_starts_with_prefix(prefix: str) -> None:
    assert fresh_id(prefix).startswith(prefix + "-")


def test_fresh_id_includes_xdist_worker_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PYTEST_XDIST_WORKER", "gw7")
    value = fresh_id("asset")
    assert "-gw7-" in value, f"expected gw7 in {value!r}"


def test_fresh_id_falls_back_to_master_when_no_xdist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PYTEST_XDIST_WORKER", raising=False)
    value = fresh_id("asset")
    assert "-master-" in value, f"expected master fallback in {value!r}"


@pytest.mark.parametrize("bad", ["", "has space", "has/slash", "has.dot", "has!bang"])
def test_fresh_id_rejects_invalid_prefix(bad: str) -> None:
    with pytest.raises(ValueError):
        fresh_id(bad)


def test_xdist_worker_id_returns_master_when_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PYTEST_XDIST_WORKER", raising=False)
    assert _xdist_worker_id() == "master"


# ---------------------------------------------------------------------------
# unique_port
# ---------------------------------------------------------------------------


def test_unique_port_returns_a_free_port() -> None:
    reset_unique_port_pool_for_tests()
    port = unique_port()
    # The port MUST be bindable right now (caller may immediately bind it).
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", port))


def test_unique_port_does_not_return_duplicates() -> None:
    reset_unique_port_pool_for_tests()
    ports = {unique_port() for _ in range(32)}
    assert len(ports) == 32, "unique_port returned duplicates"


def test_unique_port_returns_int_in_valid_range() -> None:
    reset_unique_port_pool_for_tests()
    port = unique_port()
    assert isinstance(port, int)
    assert 1024 < port < 65536
