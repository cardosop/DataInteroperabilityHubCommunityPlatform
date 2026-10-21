#!/usr/bin/env python3
"""
oss-release-remediation W0.5 — env-file secret rotation tool (D/O workhorse).

Rotates credential VALUES inside env files atomically (tmp write +
``os.replace`` — the O1 convention) without ever printing a secret:

    python scripts/rotate_env_secrets.py django-secret-key
    python scripts/rotate_env_secrets.py stack-passwords
    python scripts/rotate_env_secrets.py --dry-run stack-passwords

Subcommands:

- ``django-secret-key`` — rotates SECRET_KEY only (staging scope, the
  W0.5 decision: dev ``.env``/``.env.dev`` stay untouched).
- ``stack-passwords`` — ONE grouped pass over the staging DB-family +
  storage passwords so pgbouncer and postgres rotate together
  (``POSTGRES_PASSWORD``, ``POSTGRES_ADMIN_PASSWORD``,
  ``PGBOUNCER_AUTH_PASSWORD``, ``PGBOUNCER_ADMIN_PASSWORD``,
  ``MINIO_ROOT_PASSWORD``, ``FUSEKI_ADMIN_PASSWORD``,
  ``GRAFANA_ADMIN_PASSWORD``).

Safety contract (pinned by scripts/tests/test_rotate_env_secrets.py):

- NEVER prints a value — reports key names, new-value lengths, and the
  file path only;
- refuses to run when the target file is missing;
- refuses a PARTIAL rotation — every target key must be present or the
  file is left untouched (a missing key is a loud failure, not a skip);
- atomic write — the file is replaced via a same-directory temp file, so
  a crash mid-write can never leave a truncated env file;
- ``--dry-run`` reports what would change without writing.

Values come from ``secrets.token_urlsafe`` (CSPRNG — the
``scripts/make_dev_env.py`` pattern): SECRET_KEY length 48, stack
passwords length 18.
"""

from __future__ import annotations

import argparse
import os
import secrets
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent

SECRET_KEY_LENGTH = 48
STACK_PASSWORD_LENGTH = 18

STACK_PASSWORD_KEYS = (
    "POSTGRES_PASSWORD",
    "POSTGRES_ADMIN_PASSWORD",
    "PGBOUNCER_AUTH_PASSWORD",
    "PGBOUNCER_ADMIN_PASSWORD",
    "MINIO_ROOT_PASSWORD",
    "FUSEKI_ADMIN_PASSWORD",
    "GRAFANA_ADMIN_PASSWORD",
)

_DEFAULT_ENV_FILE = _ROOT / ".env.staging"


def _new_secret(length: int) -> str:
    return secrets.token_urlsafe(length)


def load_env(path: Path) -> dict[str, str]:
    """KEY -> value map of the file (last occurrence wins; never printed)."""
    parsed: dict[str, str] = {}
    for raw_line in path.read_text().splitlines():
        if not raw_line or raw_line.startswith("#"):
            continue
        if "=" in raw_line:
            key, value = raw_line.split("=", 1)
            parsed[key.strip()] = value
    return parsed


def _replace_values(text: str, new_values: dict[str, str]) -> str:
    """Rewrite every line starting with one of the keys (comment/order-safe)."""
    lines = []
    for raw_line in text.splitlines():
        key = raw_line.split("=", 1)[0].strip() if "=" in raw_line else ""
        if key in new_values:
            lines.append(f"{key}={new_values[key]}")
        else:
            lines.append(raw_line)
    return "\n".join(lines) + "\n"


def rotate_keys(
    path: Path,
    keys: tuple[str, ...],
    length: int,
    dry_run: bool = False,
) -> int:
    """Rotate every key in ``keys`` atomically. Returns the process exit code."""
    if not path.is_file():
        print(f"rotate-env-secrets: FAIL — target file missing: {path}")
        return 1

    existing = load_env(path)
    missing = [key for key in keys if key not in existing]
    if missing:
        print(
            "rotate-env-secrets: FAIL — refusing partial rotation: "
            f"{path} is missing {', '.join(missing)}"
        )
        return 1

    new_values = {key: _new_secret(length) for key in keys}

    if dry_run:
        for key in keys:
            print(f"dry-run: would rotate {key} in {path}")
        return 0

    text = path.read_text()
    updated = _replace_values(text, new_values)

    # O1: atomic write — same-directory temp file, then rename over.
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as handle:
            handle.write(updated)
        os.replace(tmp_name, path)
    except BaseException:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
        raise

    for key in keys:
        print(f"rotated {key} in {path} (new value length {len(new_values[key])})")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "subcommand",
        choices=("django-secret-key", "stack-passwords"),
        help="which credential group to rotate",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=_DEFAULT_ENV_FILE,
        help="env file to rotate (default: .env.staging)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report what would change without writing",
    )
    args = parser.parse_args(argv)

    if args.subcommand == "django-secret-key":
        return rotate_keys(args.env_file, ("SECRET_KEY",), SECRET_KEY_LENGTH, args.dry_run)
    return rotate_keys(args.env_file, STACK_PASSWORD_KEYS, STACK_PASSWORD_LENGTH, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
