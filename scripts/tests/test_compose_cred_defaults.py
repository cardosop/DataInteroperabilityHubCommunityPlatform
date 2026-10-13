"""
Contract test: compose files carry NO real-looking Stripe literals
(oss-release-remediation W0.5, Phase 5).

The tracked tree shipped the LEAKED Stripe test key pair as hardcoded
defaults in docker-compose.test.yml (secret + publishable) and the
publishable key in docker-compose.staging/dev.yml — the same values the
W0.2 scan found in git history. The defaults are now empty
``${STRIPE_SECRET_KEY:-}`` / ``${STRIPE_PUBLISHABLE_KEY:-}`` (env-only),
matching the pre-existing docker-compose.dev.yml secret pattern.

Pin: no docker-compose*.yml line may carry a Stripe key literal of the
real shape (sk_test_/sk_live_/pk_test_/pk_live_ followed by key
material). Comments that name the SHAPE ("e.g. sk_test_...") stay legal —
they carry no value — as do the deliberate whsec_test placeholders.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
_LITERAL = re.compile(r"\b(sk_test_|sk_live_|pk_test_|pk_live_)[A-Za-z0-9]{10,}")


@pytest.mark.parametrize(
    "compose_file", sorted(ROOT.glob("docker-compose*.yml")), ids=lambda p: p.name
)
def test_no_real_stripe_literals_in_compose_defaults(compose_file):
    text = compose_file.read_text()
    hits = [ln.strip() for ln in text.splitlines() if _LITERAL.search(ln)]
    assert not hits, (
        f"{compose_file.name} carries Stripe key literals: "
        "defaults must be env-only (${STRIPE_SECRET_KEY:-})"
    )


_WORKER_KEY_DEFAULT = __import__("re").compile(
    r"HUB_WORKER_API_KEY:\s*\$\{HUB_WORKER_API_KEY:-[^}]+\}"
)


@pytest.mark.parametrize(
    "compose_file", sorted(ROOT.glob("docker-compose*.yml")), ids=lambda p: p.name
)
def test_no_hardcoded_hub_worker_key_defaults(compose_file):
    """W1.14 — the worker API key must never carry a committed default.

    A hardcoded `:-<value>` default means an unset env variable silently
    authenticates the worker with a KNOWN shared secret (the design's
    fail-open auth class).  Test-stack composes may use their explicitly
    test-scoped key pattern; everything else must be env-only.
    """
    text = compose_file.read_text()
    hits = [
        ln.strip()
        for ln in text.splitlines()
        if _WORKER_KEY_DEFAULT.search(ln) and "test" not in ln.split(":-", 1)[1][:24]
    ]
    assert not hits, (
        f"{compose_file.name} carries a hardcoded HUB_WORKER_API_KEY default: "
        "the worker key must be env-provided (${HUB_WORKER_API_KEY:?})"
    )
