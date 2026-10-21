#!/usr/bin/env python3
"""
check_idp_jwks.py — oss-release-remediation W1.0 (S3): the pilot-IdP JWKS
capability check.

The D4 precondition: the pilot IdP must expose a fetchable JWKS with at
least one usable signing key before W1.5 implements JWKS-based OIDC
signature/aud/exp verification. This script runs that check LIVE over
real HTTPS against the pilot IdP (the same library the live W16 test
uses — hub/apps/auth/idp_metadata.py) and reports the capability
verdict. Never a mock, never a cached answer.

Discovery URL resolution (first match wins):
  1. --discovery-url
  2. SSO_IDP_DISCOVERY_URL
  3. https://{DATABRICKS_PILOT_HOST or DATABRICKS_HOST}/oidc/.well-known/oauth-authorization-server
     (the Databricks-as-IdP OIDC surface, openspec 0b.12)

Exit codes:
  0  CAPABLE — the JWKS is exposed with >=1 usable signing key;
     or SKIP in advisory mode (no IdP wired) — local runs keep the
     graceful skip, CI raises (W16) instead of skipping silently.
  1  NOT_CAPABLE / FAILURE with the classified reason (never a response
     body); or SKIP under --strict (post-flight / gate mode).

--redact-host replaces the pilot hostname with <host> in ALL output —
the C1 evidence-capture mode: the committed decision note must not
carry customer-identifying hostnames.
--json emits the machine-readable report on stdout.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from envpolicy import environment_guard
from hub.apps.auth.idp_metadata import IdPMetadataError, fetch_idp_jwks

DISCOVERY_PATH = "/oidc/.well-known/oauth-authorization-server"
_NO_IDP_REASON = (
    "no pilot IdP discovery URL configured (--discovery-url / "
    "SSO_IDP_DISCOVERY_URL / DATABRICKS_HOST)"
)


def resolve_discovery_url(explicit: str | None = None) -> str | None:
    """The pilot IdP discovery URL, or None when no IdP is wired."""
    if explicit:
        return explicit
    env = os.environ.get("SSO_IDP_DISCOVERY_URL", "").strip()
    if env:
        return env
    host = (
        (
            os.environ.get("DATABRICKS_PILOT_HOST", "")
            or os.environ.get("DATABRICKS_HOST", "")
        )
        .strip()
        .strip("\"'")
    )
    if host:
        return f"https://{host}{DISCOVERY_PATH}"
    return None


def _redact(value: str | None, hostname: str | None) -> str | None:
    if value is None or not hostname:
        return value
    return value.replace(hostname, "<host>")


def _format_human(payload: dict, redact_host: str | None) -> str:
    lines = ["pilot IdP JWKS capability check (oss-release-remediation W1.0)"]
    if payload["status"] == "SKIP":
        lines.append(f"RESULT: SKIP — {payload['reason']}")
        return "\n".join(lines)
    if payload["status"] == "NOT_CAPABLE":
        reason = _redact(payload["reason"], redact_host)
        lines.append(f"RESULT: NOT_CAPABLE (JWKS_NOT_EXPOSED) — {reason}")
        return "\n".join(lines)
    report = payload["report"]
    kty = ", ".join(
        f"{name}={count}" for name, count in sorted(report["kty_counts"].items())
    )
    lines.extend(
        [
            f"  discovery:   {_redact(payload.get('discovery'), redact_host)}",
            f"  issuer:      {_redact(report['issuer'], redact_host)}",
            f"  jwks_uri:    {_redact(report['jwks_uri'], redact_host)}",
            f"  keys: {report['key_count']}  "
            f"usable signing keys: {report['usable_signing_keys']}",
            f"  kty: {kty or 'none'}",
        ]
    )
    for key in report["keys"]:
        verdict = (
            "usable=yes" if key["usable"] else f"usable=no ({key['unusable_reason']})"
        )
        lines.append(
            f"  key  kid={key['kid']}  kty={key['kty']}  alg={key['alg']}  "
            f"use={key['use']}  {verdict}"
        )
    lines.append(
        f"RESULT: CAPABLE (JWKS_EXPOSED) — "
        f"{report['usable_signing_keys']} usable signing key(s)"
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--discovery-url", default=None, help="the IdP discovery URL")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="treat SKIP (no IdP wired) as a failure — post-flight / gate mode",
    )
    parser.add_argument(
        "--redact-host",
        action="store_true",
        help="replace the pilot hostname with <host> in ALL output (C1 evidence capture)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit the machine-readable report as JSON on stdout",
    )
    args = parser.parse_args()

    url = resolve_discovery_url(args.discovery_url)
    if not url:
        # W16: in CI the missing environment fails loudly instead of
        # skipping; local runs keep the graceful skip.
        environment_guard(_NO_IDP_REASON)
        payload = {"status": "SKIP", "reason": _NO_IDP_REASON}
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(_format_human(payload, None))
        sys.exit(1 if args.strict else 0)

    redact_host = urlsplit(url).hostname if args.redact_host else None
    try:
        report = fetch_idp_jwks(url)
    except IdPMetadataError as exc:
        payload = {"status": "NOT_CAPABLE", "reason": str(exc)}
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(_format_human(payload, redact_host))
        sys.exit(1)

    payload = {
        "status": "CAPABLE",
        "discovery": url,
        "report": report,
    }
    if args.json:
        print(json.dumps(payload, indent=2, default=str))
    else:
        print(_format_human(payload, redact_host))
    sys.exit(0)


if __name__ == "__main__":
    main()
