"""Contract pins for scripts/verify_stripe_test_keys.py (pilot-readiness 4.3).

The verifier gates the ``E2E_STRIPE_ENABLED=1`` billing-upgrade run: the
keys must be present, TEST-mode (a live key in the gate path would charge
real money), and the secret must be ACCEPTED by Stripe.  These pins run
the real script (subprocess / direct main()) against a scripted stdlib
HTTP server that records the Authorization header — the wire protocol is
exercised, never replaced; there are no behavioural mocks.

No-secret-leak is pinned both ways: the verifier's output must never
contain the key material, and the failing branches (live-key hazard,
rejected key, unreachable) must stay secret-free too.
"""

import os
import pathlib
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

SCRIPT = pathlib.Path(__file__).resolve().parent.parent / "verify_stripe_test_keys.py"

SECRET = "sk_test_contract_secret_key"
PUBLISHABLE = "pk_test_contract_publishable_key"


class _AccountHandler(BaseHTTPRequestHandler):
    """Scripted /v1/account. Records the Authorization header per request."""

    response_code = 200

    def log_message(self, *_args):
        pass

    def do_GET(self):
        self.server.requests.append(self.headers.get("Authorization", ""))
        body = b'{"id": "acct_contract_test", "object": "account"}'
        self.send_response(self.response_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture
def scripted_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _AccountHandler)
    server.requests = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


@pytest.fixture
def env_file(tmp_path):
    path = tmp_path / "env.test"
    return path


def _run(args, env, timeout=30):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout,
        check=False,  # returncode is the assertion surface, not exceptions
    )


def _env(env_file, base_url, **overrides):
    env = {
        "PATH": os.environ.get("PATH", ""),
        "ENV_TEST_FILE": str(env_file),
        "STRIPE_VERIFY_BASE_URL": base_url,
    }
    env.pop("CI", None)
    env.update(overrides)
    return env


def _write_env(env_file, secret=SECRET, publishable=PUBLISHABLE):
    env_file.write_text(
        f"STRIPE_SECRET_KEY={secret}\n"
        f"STRIPE_PUBLISHABLE_KEY={publishable}\n"
    )


# ── PASS paths ────────────────────────────────────────────────────────────


def test_valid_test_keys_pass_and_report_account_id(scripted_server, env_file):
    _write_env(env_file)
    base = f"http://127.0.0.1:{scripted_server.server_address[1]}"

    result = _run([], _env(env_file, base))

    assert result.returncode == 0
    assert "stripe-secret PASS" in result.stdout
    assert "acct_contract_test" in result.stdout
    assert "stripe-publishable PASS" in result.stdout
    # the real bearer reached the wire
    assert scripted_server.requests == [f"Bearer {SECRET}"]


def test_env_var_beats_env_file(scripted_server, env_file):
    _write_env(env_file)
    env_override = "sk_test_from_environment"
    base = f"http://127.0.0.1:{scripted_server.server_address[1]}"

    result = _run(
        [], _env(env_file, base, STRIPE_SECRET_KEY=env_override)
    )

    assert result.returncode == 0
    assert scripted_server.requests == [f"Bearer {env_override}"]


# ── live-key hazard ───────────────────────────────────────────────────────


def test_live_secret_key_fails_without_echoing_the_key(scripted_server, env_file):
    live_key = "sk_live_would_charge_real_money"
    _write_env(env_file, secret=live_key)
    base = f"http://127.0.0.1:{scripted_server.server_address[1]}"

    result = _run([], _env(env_file, base))

    assert result.returncode == 1
    assert "LIVE key" in result.stdout
    assert live_key not in result.stdout, "the key material must never be echoed"
    assert scripted_server.requests == [], "a live key must never reach the wire"


def test_live_publishable_key_fails_without_echoing_the_key(scripted_server, env_file):
    live_pk = "pk_live_frontend_embed"
    _write_env(env_file, publishable=live_pk)
    base = f"http://127.0.0.1:{scripted_server.server_address[1]}"

    result = _run([], _env(env_file, base))

    assert result.returncode == 1
    assert "LIVE key" in result.stdout
    assert live_pk not in result.stdout


def test_non_stripe_prefix_fails(scripted_server, env_file):
    _write_env(env_file, secret="totally_not_a_key")
    base = f"http://127.0.0.1:{scripted_server.server_address[1]}"

    result = _run([], _env(env_file, base))

    assert result.returncode == 1
    assert "sk_test_ prefix" in result.stdout
    assert scripted_server.requests == [], "an ill-shaped key must never reach the wire"


# ── rejected / unreachable ────────────────────────────────────────────────


def test_rejected_key_fails(scripted_server, env_file):
    _write_env(env_file)
    original_code = scripted_server.RequestHandlerClass.response_code
    scripted_server.RequestHandlerClass.response_code = 401
    try:
        base = f"http://127.0.0.1:{scripted_server.server_address[1]}"

        result = _run([], _env(env_file, base))

        assert result.returncode == 1
        assert "rejected" in result.stdout
        assert SECRET not in result.stdout
    finally:
        # The handler class is SHARED module state — restore it so later
        # fixtures (e.g. the W2.0 price tests) don't inherit the 401.
        scripted_server.RequestHandlerClass.response_code = original_code


def test_unreachable_stripe_fails(scripted_server, env_file):
    _write_env(env_file)
    scripted_server.server_close()  # bound port, now refused

    result = _run(
        [],
        _env(
            env_file,
            f"http://127.0.0.1:{scripted_server.server_address[1]}",
        ),
    )

    assert result.returncode == 1
    assert "unreachable" in result.stdout
    assert SECRET not in result.stdout


def test_no_live_skips_the_probe(scripted_server, env_file):
    _write_env(env_file)
    base = f"http://127.0.0.1:{scripted_server.server_address[1]}"

    result = _run(["--no-live"], _env(env_file, base))

    assert result.returncode == 0
    assert "live probe disabled" in result.stdout
    assert scripted_server.requests == []


# ── missing-key semantics (advisory / strict / W16 CI) ────────────────────


def test_missing_keys_skip_in_advisory_mode(scripted_server, env_file):
    # env_file exists but carries nothing
    env_file.write_text("")
    base = f"http://127.0.0.1:{scripted_server.server_address[1]}"

    result = _run([], _env(env_file, base))

    assert result.returncode == 0
    assert "stripe-secret SKIP" in result.stdout
    assert "stripe-publishable SKIP" in result.stdout
    assert scripted_server.requests == []


def test_missing_keys_fail_in_strict_mode(scripted_server, env_file):
    env_file.write_text("")
    base = f"http://127.0.0.1:{scripted_server.server_address[1]}"

    result = _run(["--strict"], _env(env_file, base))

    assert result.returncode == 1
    assert "strict mode" in result.stdout


def test_missing_keys_fail_under_ci_w16(scripted_server, env_file):
    env_file.write_text("")
    base = f"http://127.0.0.1:{scripted_server.server_address[1]}"

    result = _run([], _env(env_file, base, CI="true"))

    assert result.returncode == 1
    assert "strict mode" in result.stdout


def test_missing_secret_but_valid_publishable(scripted_server, env_file):
    env_file.write_text(f"STRIPE_PUBLISHABLE_KEY={PUBLISHABLE}\n")
    base = f"http://127.0.0.1:{scripted_server.server_address[1]}"

    result = _run([], _env(env_file, base))

    assert result.returncode == 0
    assert "stripe-secret SKIP" in result.stdout
    assert "stripe-publishable PASS" in result.stdout
    assert scripted_server.requests == []


# ── W2.0 price-ID surface ──────────────────────────────────────────────────

PRO_PRICE_ID = "price_contract_pro_monthly"


class _PriceHandler(_AccountHandler):
    """Extends the scripted account handler with a /v1/prices/<id> route."""

    price_response_code = 200

    def do_GET(self):
        if self.path.startswith("/v1/prices/"):
            self.server.requests.append(self.headers.get("Authorization", ""))
            if self.price_response_code != 200:
                body = b'{"error": {"message": "No such price"}}'
                self.send_response(self.price_response_code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            price_id = self.path.rsplit("/", 1)[-1]
            body = (
                f'{{"id": "{price_id}", "object": "price", "active": true, '
                '"currency": "usd", "recurring": {"interval": "month"}}'
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()


@pytest.fixture
def price_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _PriceHandler)
    server.requests = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


def _write_env_with_price(env_file, pro_price=PRO_PRICE_ID):
    _write_env(env_file)
    env_file.write_text(
        env_file.read_text() + f"STRIPE_PRO_PRICE_ID={pro_price}\n"
    )


def test_pro_price_set_and_verified_passes(price_server, env_file):
    _write_env_with_price(env_file)
    base = f"http://127.0.0.1:{price_server.server_address[1]}"

    result = _run([], _env(env_file, base))

    assert result.returncode == 0
    assert "stripe-pro-price PASS" in result.stdout
    assert price_server.requests == [f"Bearer {SECRET}", f"Bearer {SECRET}"]
    assert PRO_PRICE_ID not in result.stdout, "price id must never be echoed"


def test_pro_price_missing_skips_advisory_and_fails_strict(price_server, env_file):
    _write_env(env_file)  # no price entry
    base = f"http://127.0.0.1:{price_server.server_address[1]}"

    result = _run([], _env(env_file, base))
    assert result.returncode == 0
    assert "stripe-pro-price SKIP" in result.stdout

    result = _run(["--strict"], _env(env_file, base))
    assert result.returncode == 1
    assert "stripe-pro-price FAIL" in result.stdout


def test_pro_price_wrong_shape_fails_without_wire(price_server, env_file):
    _write_env_with_price(env_file, pro_price="prod_not_a_price")
    base = f"http://127.0.0.1:{price_server.server_address[1]}"

    result = _run([], _env(env_file, base))

    assert result.returncode == 1
    assert "price_ prefix" in result.stdout
    assert "prod_not_a_price" not in result.stdout
    assert price_server.requests == [f"Bearer {SECRET}"], (
        "an ill-shaped price id must never reach the wire"
    )


def test_pro_price_rejected_by_stripe_fails_without_echo(price_server, env_file):
    _write_env_with_price(env_file)
    original_code = price_server.RequestHandlerClass.price_response_code
    price_server.RequestHandlerClass.price_response_code = 404
    try:
        base = f"http://127.0.0.1:{price_server.server_address[1]}"

        result = _run([], _env(env_file, base))

        assert result.returncode == 1
        assert "stripe-pro-price FAIL" in result.stdout
        assert PRO_PRICE_ID not in result.stdout
    finally:
        # Shared handler class — restore so later pins don't inherit 404.
        price_server.RequestHandlerClass.price_response_code = original_code


def test_free_price_never_blocks_the_gate(price_server, env_file):
    _write_env_with_price(env_file)
    env_file.write_text(
        env_file.read_text() + "STRIPE_FREE_PRICE_ID=price_contract_free\n"
    )
    base = f"http://127.0.0.1:{price_server.server_address[1]}"

    result = _run(["--strict"], _env(env_file, base))

    assert result.returncode == 0
    assert "stripe-free-price" in result.stdout
    assert "stripe-free-price FAIL" not in result.stdout


class TestEnvExamplePriceEntries:
    """The .env.test.example template documents the W2.0 price entries."""

    def test_example_documents_price_entries(self):
        example = pathlib.Path(__file__).resolve().parent.parent.parent / ".env.test.example"
        text = example.read_text()
        assert "STRIPE_PRO_PRICE_ID=" in text, (
            ".env.test.example must document STRIPE_PRO_PRICE_ID"
        )
        assert "STRIPE_FREE_PRICE_ID=" in text, (
            ".env.test.example must document STRIPE_FREE_PRICE_ID"
        )
        for line in text.splitlines():
            for var in ("STRIPE_PRO_PRICE_ID", "STRIPE_FREE_PRICE_ID"):
                if line.strip().startswith(var + "="):
                    assert line.split("=", 1)[1].strip() == "", (
                        "the committed template must never carry a real "
                        f"{var} value (masked/blank only)"
                    )
