import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.5.3 — Dimension: connection reset mid-response.

Verifies that the client handles a TCP RST / abrupt disconnect
gracefully — raises a specific ConnectionError, not an unhandled
exception or silent data truncation.
"""

import socket
import threading
import time

import requests

from tests.fixtures.test_data import unique_port


def _reset_server(port: int, send_partial: bool = True) -> None:
    """Accept one connection, optionally send partial data, then RST."""
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", port))
    srv.listen(1)
    srv.settimeout(10)
    try:
        conn, _ = srv.accept()
        # Read the request (so the client doesn't get a connection error)
        conn.recv(4096)
        if send_partial:
            # Send partial HTTP response then RST
            conn.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: 1000\r\n\r\n{"partial":')
            time.sleep(0.1)
        # Force RST by setting SO_LINGER to 0 then closing
        conn.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, b"\x01\x00\x00\x00\x00\x00\x00\x00")
        conn.close()
    except socket.timeout:
        pass
    finally:
        srv.close()


def test_connection_reset_raises_error():
    """A connection reset mid-response must raise ConnectionError."""
    port = unique_port()
    server_thread = threading.Thread(target=_reset_server, args=(port, True), daemon=True)
    server_thread.start()
    time.sleep(0.1)  # let server bind

    with pytest.raises(
        (
            requests.exceptions.ConnectionError,
            requests.exceptions.ChunkedEncodingError,
        )
    ):
        requests.get(f"http://127.0.0.1:{port}/api/v1/assets/", timeout=5)

    server_thread.join(timeout=5)


def test_connection_reset_before_response_raises_error():
    """A connection reset before any response must raise ConnectionError."""
    port = unique_port()
    server_thread = threading.Thread(target=_reset_server, args=(port, False), daemon=True)
    server_thread.start()
    time.sleep(0.1)

    with pytest.raises(requests.exceptions.ConnectionError):
        requests.get(f"http://127.0.0.1:{port}/api/v1/assets/", timeout=5)

    server_thread.join(timeout=5)


def test_connection_refused_raises_error():
    """Connecting to a port with no listener must raise ConnectionError."""
    port = unique_port()
    # Don't start any server — port is free
    with pytest.raises(requests.exceptions.ConnectionError):
        requests.get(f"http://127.0.0.1:{port}/api/v1/assets/", timeout=2)
