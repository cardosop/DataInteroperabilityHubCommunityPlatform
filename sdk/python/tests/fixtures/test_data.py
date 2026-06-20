"""
Phase 216.X.2 + 216.X.4 — test data isolation primitives.

Provides:
* ``fresh_id(prefix)`` — unique identifier generator that includes the
  pytest-xdist worker id so parallel workers cannot collide on shared
  backend resources.
* ``cleanup_registry`` (autouse fixture defined in
  :mod:`fixtures.cleanup_registry`) — collects every resource a test
  creates and tears them down at function teardown, regardless of whether
  the test passed or failed.
* ``unique_port()`` — allocates a free TCP port on demand for tests that
  spin up local webhook receivers; deterministic across xdist workers.

These primitives are deliberately small and side-effect-free so they can
themselves be unit-tested without any backend dependency.
"""

from __future__ import annotations

import os
import socket
import threading
import uuid


def _xdist_worker_id() -> str:
    """Return the active pytest-xdist worker id, or ``"master"`` if not running under xdist.

    pytest-xdist exposes the worker id via the ``PYTEST_XDIST_WORKER`` env var
    (e.g. ``"gw0"``, ``"gw3"``). When tests run serially the var is unset
    and we fall back to ``"master"`` so the function still produces a
    deterministic, parseable suffix.
    """
    return os.environ.get("PYTEST_XDIST_WORKER", "master")


def fresh_id(prefix: str) -> str:
    """Return a unique identifier suitable for naming a backend resource.

    The shape is ``<prefix>-<worker_id>-<short_uuid>``. The worker id
    component guarantees that two parallel xdist workers creating
    ``fresh_id("asset")`` cannot collide; the uuid component guarantees
    no collision within a single worker.

    Args:
        prefix: Short string describing the resource type. MUST be
            non-empty and contain only ``[a-z0-9-]`` characters so the
            resulting id is safe for URLs and shell commands.

    Returns:
        A new unique id string.

    Raises:
        ValueError: if ``prefix`` is empty or contains forbidden characters.
    """
    if not prefix:
        raise ValueError("fresh_id prefix must be non-empty")
    if not all(c.isalnum() or c == "-" or c == "_" for c in prefix):
        raise ValueError(f"fresh_id prefix {prefix!r} must contain only [A-Za-z0-9_-]")
    worker = _xdist_worker_id()
    suffix = uuid.uuid4().hex[:8]
    return f"{prefix}-{worker}-{suffix}"


_PORT_LOCK = threading.Lock()
_ALLOCATED_PORTS: set[int] = set()


def unique_port(host: str = "127.0.0.1") -> int:
    """Allocate a free TCP port and return its number.

    The port is verified-free by binding a temporary socket on ``host``;
    the OS picks a free ephemeral port. The number is recorded in a
    process-local set so subsequent calls within the same worker do not
    return the same port even if a previous caller has not yet bound it.
    Different xdist workers run in different processes so they have
    independent allocation pools — the OS guarantees that no two workers
    bind the same port at the same time.

    Returns:
        A port number that was free at the time of the call.
    """
    with _PORT_LOCK:
        for _ in range(64):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind((host, 0))
                port = sock.getsockname()[1]
            if port not in _ALLOCATED_PORTS:
                _ALLOCATED_PORTS.add(port)
                return port
        raise RuntimeError("unique_port could not allocate a non-recycled port in 64 attempts")


def reset_unique_port_pool_for_tests() -> None:
    """Clear the in-process allocated-port set. Test-only — use sparingly."""
    with _PORT_LOCK:
        _ALLOCATED_PORTS.clear()
