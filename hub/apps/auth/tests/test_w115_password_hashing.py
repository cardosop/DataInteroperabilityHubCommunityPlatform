"""W11.5 (oss-release-remediation) — ASVS V6 password-hashing pins.

The crypto audit's hash-strength leg found the repo's ONLY
``PASSWORD_HASHERS`` definition lives inside the TEST-env branch
(MD5-first for suite speed — Django's documented test practice, with
the test-stack gunicorn needing MD5 verification for SDK-created
users).  Production therefore leaned on Django's framework default
(PBKDF2-first) — correct today, but ABSENT: nothing declared it, and
nothing would catch a future edit that reintroduced MD5-first for
production (the register-row-18 class: absence must be proven, not
assumed).

These pins prove the explicit posture:

* the settings module declares a NON-test production list whose first
  entry is PBKDF2-SHA256 (source-pinned — the declaration exists and
  is ordered right);
* the test-env list keeps MD5-first for speed BUT stays the ONLY
  MD5-first site, and MD5 stays listed for legacy verification;
* ``make_password`` follows the configured first hasher;
* PBKDF2 iterations meet ASVS V6 (≥600k; Django 6's 1.2M default);
* legacy MD5 / SHA1 hashes still VERIFY (``check_password`` dispatches
  on the hash prefix — no migration, no broken rows).

RED phase: the production block did not exist — the two source pins
failed against the pre-fix settings (the first draft of these pins
wrongly assumed the test-env order applied everywhere; the RED run
corrected the design to pin the DECLARATION).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from django.contrib.auth.hashers import (
    MD5PasswordHasher,
    PBKDF2PasswordHasher,
    PBKDF2SHA1PasswordHasher,
    check_password,
    get_hashers,
    make_password,
)

pytestmark = pytest.mark.django_db(transaction=True)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
SETTINGS_SOURCE = (REPO_ROOT / "hub" / "settings.py").read_text(encoding="utf-8")

_PBKDF2_PATH = "django.contrib.auth.hashers.PBKDF2PasswordHasher"
_MD5_PATH = "django.contrib.auth.hashers.MD5PasswordHasher"


def _hasher_blocks() -> list[str]:
    """Every ``PASSWORD_HASHERS = [ ... ]`` block body in settings.py."""
    return [
        match.group(1)
        for match in re.finditer(r"PASSWORD_HASHERS = \[(.*?)\]", SETTINGS_SOURCE, re.S)
    ]


def _first_entry(block: str) -> str:
    return block.strip().splitlines()[0].strip().strip('",')


def test_new_passwords_use_the_configured_first_hasher():
    """make_password must follow the configured order (PBKDF2 in
    production; the fast test hasher under the test env)."""
    hashed = make_password("correct horse battery staple")
    expected_prefix = f"{get_hashers()[0].algorithm}$"
    assert hashed.startswith(expected_prefix), hashed.split("$")[0]


def test_production_block_declares_pbkdf2_first():
    """Source pin: settings.py must DECLARE a production hasher list
    whose first entry is PBKDF2-SHA256 (not lean on the Django
    default silently)."""
    blocks = _hasher_blocks()
    assert len(blocks) >= 2, (
        "settings.py must declare BOTH the production and the test-env "
        "PASSWORD_HASHERS lists explicitly"
    )
    prod_blocks = [
        block for block in blocks if _first_entry(block) != _MD5_PATH
    ]
    assert prod_blocks, "no non-MD5-first (production) PASSWORD_HASHERS block"
    assert _first_entry(prod_blocks[0]) == _PBKDF2_PATH, (
        f"production PASSWORD_HASHERS[0] must be PBKDF2, got {_first_entry(prod_blocks[0])!r}"
    )


def test_test_env_block_is_the_only_md5_first_site():
    """The speed swap stays scoped: EXACTLY one block names MD5 first
    (the test env), and it still lists PBKDF2 for verification."""
    blocks = _hasher_blocks()
    md5_first = [block for block in blocks if _first_entry(block) == _MD5_PATH]
    assert len(md5_first) == 1, (
        f"expected exactly one MD5-first (test-env) block, got {len(md5_first)}"
    )
    assert _PBKDF2_PATH in md5_first[0], (
        "the test-env list must keep PBKDF2 for legacy verification"
    )


def test_pbkdf2_iterations_meet_asvs_v6():
    assert PBKDF2PasswordHasher.iterations >= 600_000


def test_legacy_md5_hash_still_verifies():
    """The migration contract: rows hashed with the pre-W11.5 MD5 test
    hasher keep verifying (check_password dispatches on the hash's
    algorithm prefix)."""
    legacy = MD5PasswordHasher().encode("legacy-pw", "legacy-salt-1")
    assert legacy.startswith("md5$")
    assert check_password("legacy-pw", legacy)
    assert not check_password("wrong-pw", legacy)


def test_legacy_sha1_hash_still_verifies():
    legacy = PBKDF2SHA1PasswordHasher().encode("legacy-pw-2", "legacy-salt-2")
    assert check_password("legacy-pw-2", legacy)
    assert not check_password("wrong-pw", legacy)
