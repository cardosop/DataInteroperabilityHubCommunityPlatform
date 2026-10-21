#!/usr/bin/env python3
"""
pilot-readiness 1.5 — conditional CKAN token re-mint.

Turns the 1.4 manual recovery into tooling used by ``make
test-stack-reinit``: probe the ``.env.test`` token first — a valid token
means nothing to do (exit 0); only a dead/missing token triggers the
full rotation:

1. mint a fresh ``seed_token`` via the ckan CLI (``user token add``);
2. write it into ``.env.test`` (the live carrier);
3. keep the Makefile ``?=`` fallback and the compose ``CKAN_SEED_TOKEN``
   in sync (the 1.4 single-source convention);
4. revoke the superseded token (its jti is decoded from the old
   ``.env.test`` value — the api container's baked ``seed_token_20261002``
   is NOT touched, revocation is scoped to the replaced token only);
5. re-probe — the fresh token must PASS (exit 1 otherwise).

Gotchas pinned by the 1.4 rehearsal: the CLI prints the JWT on the LAST
line with a LEADING TAB (a ``^eyJ`` grep misses it), and a public CKAN
action would be a vacuous probe — the probe is the auth-required
``api_token_list`` from verify_connector_creds.

No secret value is EVER printed — the mint output is captured in memory,
files are rewritten programmatically, and diagnostics name files only.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent
_ENV_TEST = _REPO_ROOT / ".env.test"
_MAKEFILE = _REPO_ROOT / "Makefile"
_COMPOSE = _REPO_ROOT / "docker-compose.test.yml"
_CKAN_INI = "/srv/app/ckan.ini"
_TOKEN_NAME = "seed_token"
_ADMIN_USER = "admin"

_JWT_RE = re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")


def parse_mint_output(text: str) -> str | None:
    """The JWT from a ``ckan user token add`` run (leading-tab tolerant)."""
    matches = _JWT_RE.findall(text)
    return matches[-1] if matches else None


def jwt_jti(token: str) -> str | None:
    """The jti claim of a JWT, decoded without printing the token."""
    import base64
    import json

    parts = token.split(".")
    if len(parts) != 3:
        return None
    try:
        payload = parts[1] + "=" * (-len(parts[1]) % 4)
        return json.loads(base64.urlsafe_b64decode(payload)).get("jti")
    except (ValueError, KeyError):
        return None


def _atomic_write(path: Path, text: str) -> None:
    """Write ``text`` atomically: same-dir temp + ``os.replace``.

    O1 (W0.10): these files are live secret carriers (.env.test feeds
    every stack boot). A plain ``write_text`` truncates the file in
    place — a crash mid-write leaves a half-written carrier and the next
    boot fails on a malformed line. The temp + replace pattern makes the
    new content appear in one step (POSIX rename is atomic); readers
    never observe a partial file. The temp lands in the SAME directory
    so the rename is a same-filesystem operation.
    """
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as handle:
            handle.write(text)
        os.replace(tmp_name, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp_name)
        raise


def rewrite_env_test(path: Path, jwt: str) -> bool:
    if not path.is_file():
        return False
    text = path.read_text()
    pattern = re.compile(r"^CKAN_TEST_API_KEY=.*$", re.MULTILINE)
    if not pattern.search(text):
        return False
    _atomic_write(path, pattern.sub(f"CKAN_TEST_API_KEY={jwt}", text))
    return True


def rewrite_makefile(path: Path, jwt: str) -> bool:
    if not path.is_file():
        return False
    text = path.read_text()
    pattern = re.compile(r"^CKAN_TEST_API_KEY \?= .*$", re.MULTILINE)
    if not pattern.search(text):
        return False
    _atomic_write(path, pattern.sub(f"CKAN_TEST_API_KEY ?= {jwt}", text))
    return True


def rewrite_compose_seed(path: Path, jwt: str) -> bool:
    if not path.is_file():
        return False
    text = path.read_text()
    pattern = re.compile(r"^(\s*CKAN_SEED_TOKEN): .*$", re.MULTILINE)
    if not pattern.search(text):
        return False
    _atomic_write(path, pattern.sub(fr"\g<1>: {jwt}", text))
    return True


def mint_command(token_name: str = _TOKEN_NAME) -> list[str]:
    return [
        "docker", "compose", "-f", "docker-compose.test.yml",
        "exec", "-T", "ckan-test",
        "ckan", "-c", _CKAN_INI,
        "user", "token", "add", _ADMIN_USER, token_name,
    ]


def revoke_command(token_id: str) -> list[str]:
    return [
        "docker", "compose", "-f", "docker-compose.test.yml",
        "exec", "-T", "ckan-test",
        "ckan", "-c", _CKAN_INI,
        "user", "token", "revoke", token_id,
    ]


def probe_token(key: str | None, base: str) -> tuple[str, str]:
    spec = importlib.util.spec_from_file_location(
        "verify_connector_creds", _SCRIPT_DIR / "verify_connector_creds.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.ckan_probe_result(key, base=base)


def read_env_test_token() -> str | None:
    if not _ENV_TEST.is_file():
        return None
    for line in _ENV_TEST.read_text().splitlines():
        if line.startswith("CKAN_TEST_API_KEY="):
            value = line.split("=", 1)[1]
            return value or None
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true",
                        help="re-mint even when the current token is valid")
    args = parser.parse_args(argv)

    base = os.getenv("CKAN_TEST_BASE_URL", "http://localhost:5100")
    old_token = read_env_test_token()

    status, detail = probe_token(old_token, base)
    if status == "PASS" and not args.force:
        print(f"ckan token: VALID ({_ENV_TEST}) — nothing to do")
        return 0
    if old_token:
        print(f"ckan token: {status} ({detail}) — re-minting")
    else:
        print(f"ckan token: MISSING ({_ENV_TEST}) — re-minting")

    # 1. Mint through the real CLI.
    mint = subprocess.run(
        mint_command(), capture_output=True, text=True, check=False
    )
    if mint.returncode != 0:
        print(f"mint FAILED: ckan CLI exited {mint.returncode}")
        return 1
    fresh = parse_mint_output(mint.stdout)
    if not fresh:
        print("mint FAILED: no JWT in the CLI output")
        return 1

    # 2-3. Write the fresh token into every carrier.
    for label, ok in (
        (".env.test", rewrite_env_test(_ENV_TEST, fresh)),
        ("Makefile fallback", rewrite_makefile(_MAKEFILE, fresh)),
        ("compose CKAN_SEED_TOKEN", rewrite_compose_seed(_COMPOSE, fresh)),
    ):
        if not ok:
            print(f"mint FAILED: could not rewrite {label}")
            return 1
    print("token written: .env.test + Makefile fallback + compose CKAN_SEED_TOKEN")

    # 4. Revoke the superseded token (scoped: only the replaced one).
    if old_token and old_token != fresh:
        old_jti = jwt_jti(old_token)
        if old_jti and old_jti != jwt_jti(fresh):
            revoke = subprocess.run(
                revoke_command(old_jti), capture_output=True, text=True, check=False
            )
            print(f"old token revoked: {old_jti[:12]}… ({revoke.returncode == 0})")

    # 5. The fresh token must verify.
    status, detail = probe_token(fresh, base)
    if status == "PASS":
        print("ckan token: VALID — re-mint complete")
        return 0
    print(f"re-mint FAILED: fresh token probe reports {status} ({detail})")
    return 1


if __name__ == "__main__":
    sys.exit(main())
