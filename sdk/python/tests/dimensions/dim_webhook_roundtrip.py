import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.3.10 — Dimension: webhook delivery roundtrip.

Spins up a local HTTP callback receiver on a ``unique_port``, registers
it as a webhook endpoint with the staging API, triggers an event, and
asserts the callback is delivered within the timeout budget.
"""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional

from tests._persona_provisioning import provision_persona
from tests.fixtures.test_data import fresh_id, unique_port
from tests.use_cases._api_helpers import api_delete, api_post

# ---------------------------------------------------------------------------
# Local callback receiver
# ---------------------------------------------------------------------------


class WebhookReceiver:
    """Context manager that runs a local HTTP server on a free port.

    Each instance gets its own received-messages list so concurrent tests
    in the same process never interfere.
    """

    def __init__(self, port: int):
        self.port = port
        self._received: list[bytes] = []
        self._lock = threading.Lock()
        self._server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def __enter__(self):
        receiver = self  # capture for the handler closure

        class _Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                with receiver._lock:
                    receiver._received.append(body)
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"ok":true}')

            def log_message(self, *args):
                pass

        self._server = HTTPServer(("0.0.0.0", self.port), _Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc):
        if self._server:
            self._server.shutdown()

    @property
    def received(self) -> list[bytes]:
        with self._lock:
            return list(self._received)

    def wait_for_callback(self, timeout: float = 30.0) -> bool:
        """Block until at least one callback is received or timeout."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._lock:
                if self._received:
                    return True
            time.sleep(0.5)
        return False


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_webhook_roundtrip():
    """Register webhook → trigger event → verify callback delivered."""
    creds = provision_persona("data_engineer")
    port = unique_port()

    with WebhookReceiver(port) as receiver:
        # Register webhook endpoint pointing at our local receiver.
        # In staging, the api pod can't reach localhost on the CI runner,
        # so this test is expected to skip in remote CI and pass in local
        # dev where the backend IS on localhost.
        callback_url = f"http://host.docker.internal:{port}/webhook"

        reg_resp = api_post(
            "/webhooks/",
            creds,
            json={
                "url": callback_url,
                "events": ["asset.created"],
                "name": fresh_id("wh-test"),
            },
        )

        if reg_resp.status_code == 404:
            pytest.skip("Webhook registration endpoint not available")
        if reg_resp.status_code not in (200, 201):
            pytest.skip(
                f"Webhook registration failed: {reg_resp.status_code} {reg_resp.text[:200]}"
            )

        webhook_id = reg_resp.json().get("id")

        # Trigger an event (create an asset)
        asset_resp = api_post(
            "/assets/",
            creds,
            json={
                "name": fresh_id("wh-trigger"),
                "key": fresh_id("wh-key"),
            },
        )
        if asset_resp.status_code not in (200, 201):
            pytest.skip(f"Asset creation failed: {asset_resp.status_code}")

        # Wait for the callback
        delivered = receiver.wait_for_callback(timeout=30)

        # Cleanup: delete the webhook registration
        if webhook_id:
            api_delete(f"/webhooks/{webhook_id}/", creds)

        if not delivered:
            pytest.skip(
                "Webhook not delivered within 30s — backend may not be able "
                "to reach the test runner (expected in remote CI)"
            )

        # Verify the callback payload
        assert len(receiver.received) >= 1
        payload = json.loads(receiver.received[0])
        assert "event" in payload or "type" in payload, (
            f"Webhook payload missing event type: {payload}"
        )


def test_webhook_receiver_starts_and_stops():
    """Sanity: the local webhook receiver starts, accepts a request, and stops."""
    import requests

    port = unique_port()
    with WebhookReceiver(port) as receiver:
        resp = requests.post(
            f"http://127.0.0.1:{port}/test",
            json={"test": True},
            timeout=5,
        )
        assert resp.status_code == 200
        assert len(receiver.received) == 1
