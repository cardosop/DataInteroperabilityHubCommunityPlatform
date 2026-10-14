#!/usr/bin/env python3
"""Verify the Stripe TEST-mode keys required by the pilot (pilot-readiness 4.3).

The billing-upgrade E2E spec's ``E2E_STRIPE_ENABLED=1`` branch proves the
charged Stripe path end-to-end.  That run is only meaningful when the
backend actually holds VALID TEST-mode keys — a missing/blank key means
the assertion can never pass, and a LIVE key (sk_live_/pk_live_) would
charge real money from an E2E run, which must fail the gate loudly.

Surfaces checked:

* ``stripe-secret``      — STRIPE_SECRET_KEY set, ``sk_test_``-prefixed,
                           and ACCEPTED by a live ``GET /v1/account``.
* ``stripe-publishable`` — STRIPE_PUBLISHABLE_KEY set, ``pk_test_``-prefixed.
* ``stripe-pro-price``   — W2.0: STRIPE_PRO_PRICE_ID set, ``price_``-prefixed,
                           and RESOLVED live (``GET /v1/prices/{id}``:
                           active + monthly recurring) — the charged E2E
                           checkout path uses exactly this price.
* ``stripe-free-price``  — W2.0: optional by design (free plans are
                           local-only); a set-but-malformed value fails.

Key resolution: the process environment wins; otherwise ``.env.test`` is
read (override the file path with ``ENV_TEST_FILE``).  The live probe
targets https://api.stripe.com by default (override for contract tests
with ``STRIPE_VERIFY_BASE_URL``).

Exit codes: 0 = all surfaces PASS (or SKIP in advisory mode),
1 = any FAIL.  ``--strict`` turns SKIP into failure, and CI runs
(``CI=true``) are strict by construction (the W16 environment policy:
missing credentials raise instead of skipping).

No secret material is ever printed — outputs carry prefixes and Stripe
account identifiers only.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import urllib.error
import urllib.request

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

LIVE_STRIPE_BASE = "https://api.stripe.com"


class ProbeOutcome:
    """One surface's verdict: status, detail, and optional identifier."""

    def __init__(
        self,
        status: str,
        detail: str,
        identifier: str | None = None,
        strict_ok: bool = False,
    ):
        self.status = status  # PASS | FAIL | SKIP
        self.detail = detail
        self.identifier = identifier
        # A SKIP that is a DESIGNED optional state (not a missing
        # credential) stays a skip even under --strict/CI.
        self.strict_ok = strict_ok


def _read_env_test(var: str) -> str | None:
    env_path = os.environ.get("ENV_TEST_FILE", str(REPO_ROOT / ".env.test"))
    try:
        text = pathlib.Path(env_path).read_text()
    except OSError:
        return None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(var + "="):
            return stripped.split("=", 1)[1].strip()
    return None


def load_key(var: str) -> str | None:
    """Return the key from the process env or .env.test (env wins)."""
    value = os.environ.get(var)
    if value is None:
        value = _read_env_test(var)
    return value or None


def probe_account(secret: str, base_url: str, timeout: int = 15):
    """GET /v1/account with the bearer secret. Returns (status, body).

    Raises urllib.error.HTTPError (rejected key) or URLError (unreachable).
    """
    req = urllib.request.Request(
        f"{base_url}/v1/account",
        headers={"Authorization": f"Bearer {secret}"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


def check_secret(secret: str | None, base_url: str, no_live: bool) -> ProbeOutcome:
    if not secret:
        return ProbeOutcome(
            "SKIP",
            "STRIPE_SECRET_KEY not set (env or .env.test)",
        )
    if secret.startswith("sk_live_"):
        return ProbeOutcome(
            "FAIL",
            "STRIPE_SECRET_KEY is a LIVE key in a test context — an "
            "E2E_STRIPE_ENABLED=1 run with this key would charge real "
            "money. Replace it with a test-mode key immediately.",
        )
    if not secret.startswith("sk_test_"):
        return ProbeOutcome(
            "FAIL",
            "STRIPE_SECRET_KEY is not a test-mode key (expected sk_test_ prefix)",
        )
    if no_live:
        return ProbeOutcome("SKIP", "live probe disabled (--no-live)")
    return _live_probe_outcome(secret, base_url)


def _live_probe_outcome(secret: str, base_url: str) -> ProbeOutcome:
    try:
        _status, body = probe_account(secret, base_url)
    except urllib.error.HTTPError as exc:
        return ProbeOutcome(
            "FAIL",
            f"Stripe rejected the key (HTTP {exc.code}) — invalid or revoked",
        )
    except urllib.error.URLError as exc:
        return ProbeOutcome(
            "FAIL",
            f"Stripe unreachable ({exc.reason}) — the key cannot be verified",
        )
    except OSError:
        # ConnectionResetError/ConnectionRefusedError surface directly as
        # OSError (not URLError) on reset connections — classify instead
        # of crashing. The reason is never echoed (host details leak env).
        return ProbeOutcome(
            "FAIL",
            "Stripe unreachable (connection error) — the key cannot be verified",
        )
    return ProbeOutcome("PASS", "accepted by Stripe", identifier=body.get("id"))


def check_publishable(publishable: str | None) -> ProbeOutcome:
    if not publishable:
        return ProbeOutcome(
            "SKIP",
            "STRIPE_PUBLISHABLE_KEY not set (env or .env.test)",
        )
    if publishable.startswith("pk_live_"):
        return ProbeOutcome(
            "FAIL",
            "STRIPE_PUBLISHABLE_KEY is a LIVE key in a test context — the "
            "frontend would embed a live publishable key in test bundles",
        )
    if not publishable.startswith("pk_test_"):
        return ProbeOutcome(
            "FAIL",
            "STRIPE_PUBLISHABLE_KEY is not a test-mode key (expected pk_test_ prefix)",
        )
    return ProbeOutcome("PASS", "test-mode publishable key")


# ── W2.0 price-ID surfaces ──────────────────────────────────────────────────


def check_pro_price(pro_price: str | None, secret: str, base_url: str) -> ProbeOutcome:
    """The canonical PRO price must be recorded AND resolve in the
    provisioned Stripe dashboard — the E2E_STRIPE_ENABLED=1 checkout
    path charges it, so a stale/dangling ID fails the gate loudly."""
    if not pro_price:
        return ProbeOutcome(
            "SKIP",
            "STRIPE_PRO_PRICE_ID not set (env or .env.test)",
        )
    if not secret:
        return ProbeOutcome(
            "SKIP",
            "cannot verify the price without STRIPE_SECRET_KEY "
            "(the secret surface carries the failure)",
            strict_ok=True,
        )
    if not pro_price.startswith("price_"):
        return ProbeOutcome(
            "FAIL",
            "STRIPE_PRO_PRICE_ID is not a Stripe Price id (expected price_ prefix)",
        )
    try:
        req = urllib.request.Request(
            f"{base_url}/v1/prices/{pro_price}",
            headers={"Authorization": f"Bearer {secret}"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return ProbeOutcome(
            "FAIL",
            f"Stripe rejected the price lookup (HTTP {exc.code}) — the "
            "recorded PRO price id is stale or was deleted",
        )
    except (urllib.error.URLError, OSError):
        return ProbeOutcome(
            "FAIL",
            "Stripe unreachable — the recorded PRO price id cannot be verified",
        )
    if not body.get("active"):
        return ProbeOutcome(
            "FAIL",
            "the recorded PRO price is INACTIVE in Stripe — checkout would "
            "fail with 'price inactive'",
        )
    recurring = body.get("recurring") or {}
    if recurring.get("interval") != "month":
        return ProbeOutcome(
            "FAIL",
            "the recorded PRO price is not monthly recurring "
            f"(interval={recurring.get('interval')!r})",
        )
    # No identifier: price ids are never echoed (the no-secret-leak
    # contract covers them — CI logs are public within the team).
    return ProbeOutcome(
        "PASS",
        "recorded and active in Stripe (monthly recurring)",
    )


def check_free_price(free_price: str | None) -> ProbeOutcome:
    """FREE is deliberately optional: free plans create LOCAL-ONLY
    subscriptions (billing/services.py) and Stripe has no $0 recurring
    price. The entry exists to make the tier→price mapping explicit —
    it never blocks the gate, in any mode."""
    if not free_price:
        return ProbeOutcome(
            "SKIP",
            "STRIPE_FREE_PRICE_ID not set — free plans are local-only "
            "(no Stripe price required)",
            strict_ok=True,
        )
    if not free_price.startswith("price_"):
        return ProbeOutcome(
            "FAIL",
            "STRIPE_FREE_PRICE_ID is set but is not a Stripe Price id "
            "(expected price_ prefix) — fix or clear it",
        )
    return ProbeOutcome("PASS", "recorded (free-tier price id present)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="SKIP becomes failure (exit 1) — use as the gate mode",
    )
    parser.add_argument(
        "--no-live",
        action="store_true",
        help="skip the live account probe (contract-test hook)",
    )
    args = parser.parse_args(argv)

    # W16 environment policy: in CI a missing credential is an
    # environment failure, never a graceful skip.
    strict = args.strict or os.environ.get("CI") == "true"
    base_url = os.environ.get("STRIPE_VERIFY_BASE_URL", LIVE_STRIPE_BASE)

    secret = load_key("STRIPE_SECRET_KEY")
    outcomes = [
        ("stripe-secret", check_secret(secret, base_url, args.no_live)),
        ("stripe-publishable", check_publishable(load_key("STRIPE_PUBLISHABLE_KEY"))),
        # W2.0 — canonical plan price IDs (PRO verified live; FREE optional).
        ("stripe-pro-price", check_pro_price(load_key("STRIPE_PRO_PRICE_ID"), secret or "", base_url)),
        ("stripe-free-price", check_free_price(load_key("STRIPE_FREE_PRICE_ID"))),
    ]

    failed = False
    for name, outcome in outcomes:
        suffix = f" ({outcome.identifier})" if outcome.identifier else ""
        print(f"{name} {outcome.status}: {outcome.detail}{suffix}")
        if outcome.status == "FAIL":
            failed = True
        elif outcome.status == "SKIP" and strict and not outcome.strict_ok:
            print(
                f"{name} FAIL: strict mode (or CI) — a missing Stripe test key "
                "cannot be skipped when the gate is armed"
            )
            failed = True

    if failed:
        print(
            "verify-stripe-test-keys: FAIL — E2E_STRIPE_ENABLED=1 would either "
            "fail mid-run or charge a live account",
        )
        return 1
    print("verify-stripe-test-keys: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
