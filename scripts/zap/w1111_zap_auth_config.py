#!/usr/bin/env python3
"""W11.11 — ZAP authenticated-scan auth helper (oss-release-remediation).

Two real-HTTP operations around the per-role ZAP scans.  No mocks: this
script performs the actual API login and inspects the actual scan
report.

``login-config`` — logs into ``POST {target}/api/v1/auth/login/`` with
the role's credentials (read from the environment, never argv), and
writes ZAP ``-config`` replacer arguments that inject
``Authorization: Bearer <token>`` into every request the scanner sends
(the same mechanism the DAST workflow passes to
``zaproxy/action-full-scan``).  Credentials never appear on stdout,
stderr, or in the output file; under GitHub Actions the minted token is
masked in the workflow log.

``verify-report`` — fails when the scan report embeds the minted token
(an app echoing the Authorization header, or ZAP evidence leaking it,
must never be committed to the baselines).

Exit codes: 0 ok; 1 verification failure; 2 usage/typed operational
error.

Usage:
  python scripts/zap/w1111_zap_auth_config.py login-config \
      --target https://staging.example.com --username da@example.com \
      --password-env DAST_TENANT_ADMIN_PASSWORD --output zap-config.args
  python scripts/zap/w1111_zap_auth_config.py verify-report \
      --report zap.json --token-file dast.token
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

LOGIN_PATH = "/api/v1/auth/login/"

_OK = 0
_FAIL = 1
_ERROR = 2


def _fail(message: str) -> int:
    print(f"error: {message}", file=sys.stderr)
    return _ERROR


def _login(target: str, email: str, password: str) -> str:
    """POST the login endpoint and return the access token.

    Raises RuntimeError with a credential-free message on any failure —
    the password must never be interpolated into an error.
    """
    url = target.rstrip("/") + LOGIN_PATH
    payload = json.dumps({"email": email, "password": password}).encode()
    request = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8", errors="replace")
            set_cookie_headers = response.headers.get_all("Set-Cookie") or []
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"login returned HTTP {exc.code} for {email}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"login unreachable: {exc.reason}") from exc

    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError("login response is not JSON") from exc

    token = data.get("access_token")
    if not token:
        # Staging/production run USE_HTTPONLY_AUTH_COOKIES=true: the body
        # carries no token — the access JWT is in the httpOnly Set-Cookie.
        # The SAME JWT is valid in the Authorization header
        # (JWTAuthentication checks Bearer first), so extract it from the
        # Set-Cookie and keep the bearer-replacer design.
        for header in set_cookie_headers:
            for part in header.split(";"):
                key, _, value = part.strip().partition("=")
                if key == "access_token" and value:
                    token = value
                    break
            if token:
                break
    if not token:
        raise RuntimeError(
            "login response carries no access_token — neither in the body "
            "nor in an access_token Set-Cookie (unexpected auth mode)"
        )
    return str(token)


def _replacer_args(token: str) -> str:
    """The ZAP replacer rule injecting the bearer token, as a ZAP
    properties file (``key=value`` lines) — passed to the scan wrapper
    via ``-z "-configfile <path>"`` (the wrapper's ``-z`` carries ZAP
    command-line options; ``-c`` is the context-file flag and rejected
    this format)."""
    return "\n".join(
        [
            "replacer.full_list(0).description=dast-auth",
            "replacer.full_list(0).enabled=true",
            "replacer.full_list(0).matchtype=REQ_HEADER",
            "replacer.full_list(0).matchstr=Authorization",
            "replacer.full_list(0).regex=false",
            f"replacer.full_list(0).replacement=Bearer {token}",
        ]
    )


def cmd_login_config(args: argparse.Namespace) -> int:
    password = os.environ.get(args.password_env, "")
    if not password:
        return _fail(f"password env var {args.password_env} is empty or unset")
    if not args.username:
        return _fail("--username is required")

    try:
        token = _login(args.target, args.username, password)
    except RuntimeError as exc:
        return _fail(str(exc))

    if os.environ.get("GITHUB_ACTIONS"):
        # Never let the token surface in workflow logs.
        print(f"::add-mask::{token}")
    Path(args.output).write_text(_replacer_args(token) + "\n")
    if args.token_file:
        Path(args.token_file).write_text(token + "\n")
        Path(args.token_file).chmod(0o600)
    print(f"login ok for {args.username}; ZAP config written to {args.output}")
    return _OK


def cmd_verify_report(args: argparse.Namespace) -> int:
    token = ""
    if args.token_file:
        try:
            token = Path(args.token_file).read_text(encoding="utf-8").strip()
        except OSError as exc:
            return _fail(f"token file unreadable: {exc}")
    if args.token_env:
        token = os.environ.get(args.token_env, "") or token
    if not token:
        return _fail("no token supplied (--token-file or --token-env)")

    try:
        report_text = Path(args.report).read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return _fail(f"report unreadable: {exc}")
    if token in report_text:
        print(
            "error: the scan report embeds the minted bearer token — "
            "the report must not be committed or baselined",
            file=sys.stderr,
        )
        return _FAIL
    print(f"report clean: {args.report} does not embed the scan token")
    return _OK


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    login_parser = sub.add_parser("login-config")
    login_parser.add_argument("--target", required=True)
    login_parser.add_argument("--username", required=True)
    login_parser.add_argument("--password-env", required=True)
    login_parser.add_argument("--output", required=True)
    login_parser.add_argument("--token-file", default=None)
    login_parser.set_defaults(func=cmd_login_config)

    verify_parser = sub.add_parser("verify-report")
    verify_parser.add_argument("--report", required=True)
    verify_parser.add_argument("--token-file", default=None)
    verify_parser.add_argument("--token-env", default=None)
    verify_parser.set_defaults(func=cmd_verify_report)

    args = parser.parse_args(argv)
    handler = args.func
    return int(handler(args))


if __name__ == "__main__":
    sys.exit(main())
