#!/usr/bin/env python3
"""
oss-release-remediation W0.5 — OLD-credential dead-check.

One-time evidence generator run INSIDE the maintenance window: proves the
OLD credential values (the ones that leaked into git history) are now
REJECTED by their providers after rotation. NEVER chained into CI or the
make gate — its git-history sources vanish at the W0.4 force-push; GATE-51
freezes the pre-force-push result in the rotation record.

Old values are collected (hash-deduplicated, NEVER printed) from:

- ``.env*.bak-*`` snapshot files (the pilot 1.4 rotation snapshots);
- ``git show <commit>:<path>`` for the leak commits named in
  docs/audits/secret-scan-2026-10-06.md (12fb0ccc, 955a8cd2, 054f8b35,
  e8836c9c — ``.env.test`` + ``docker-compose.test.yml``);
- the CURRENT env files (the values being rotated right now: the live
  AWS pair, the current Stripe key, the staging pairs).

Per surface, each distinct old value is probed expecting REJECTION:

- PASS = provider rejects with a classified error (AWS STS
  InvalidClientTokenId/InvalidAccessKeyId/AccessDenied/ExpiredToken,
  Stripe/Databricks 401/403, GCP invalid_grant, Azure invalid_client,
  Snowflake auth-class failure);
- FAIL = provider ACCEPTS the old value — still live, stop-the-line;
- SKIP = unverifiable (429/5xx/network/unclassified);
- ADVISORY = source missing / no old value (the frozen-evidence mode —
  post-force-push re-runs fall here and GATE-51 accepts the frozen rows).

Exit 0 in advisory mode unless a FAIL is found; ``--strict`` (or
``CI=true``) turns SKIP and ADVISORY into failure. Env overrides:
``OLD_CREDS_BAK_FILES``, ``OLD_CREDS_GIT_COMMITS`` (``sha:path`` pairs,
colon-separated), ``OLD_CREDS_CURRENT_FILES``.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent

# The leak commits named in docs/audits/secret-scan-2026-10-06.md §
# HIGH-class evidence — old values live in their .env.test +
# docker-compose.test.yml trees.
_LEAK_COMMITS = ("12fb0ccc", "955a8cd2", "054f8b35", "e8836c9c")
_GIT_SOURCE_PATHS = (".env.test", "docker-compose.test.yml")

_AWS_DEAD_CODES = {
    "InvalidClientTokenId",
    "InvalidAccessKeyId",
    "AccessDenied",
    "ExpiredToken",
}
_SNOWFLAKE_AUTH_MARKERS = (
    "oauth",
    "token",
    "auth",
    "credential",
    "incorrect",
)


def classify_http_status(status: int) -> str:
    """401/403 = rejected (PASS); 2xx = accepted (FAIL); else SKIP."""
    if status in (401, 403):
        return "PASS"
    if 200 <= status < 300:
        return "FAIL"
    return "SKIP"


def classify_aws_sts(code: str) -> str:
    """The STS error code of the old-pair call ('' = accepted)."""
    if not code:
        return "FAIL"
    if code in _AWS_DEAD_CODES:
        return "PASS"
    return "SKIP"


def classify_gcp_grant(message: str) -> str:
    """The token-exchange error for the old SA key ('' = accepted)."""
    if not message:
        return "FAIL"
    if "invalid_grant" in message:
        return "PASS"
    return "SKIP"


def classify_azure_token(status: int, body: str) -> str:
    """The client_credentials verdict for the old SP secret."""
    if status == 200:
        return "FAIL"
    # The AAD error codes for an invalid/expired client secret
    # (AADSTS7000215 / AADSTS7000222 — matched on the numeric code).
    if "7000215" in body or "7000222" in body:
        return "PASS"
    return "SKIP"


def classify_snowflake_auth(message: str) -> str:
    """The connect-error message for the old token ('' = connected)."""
    if not message:
        return "FAIL"
    lowered = message.lower()
    if any(marker in lowered for marker in _SNOWFLAKE_AUTH_MARKERS):
        return "PASS"
    return "SKIP"


def parse_env_file(path: Path) -> dict[str, str]:
    """The non-empty credential entries of an env file (never printed)."""
    if not path.is_file():
        return {}
    parsed: dict[str, str] = {}
    for raw_line in path.read_text().splitlines():
        if not raw_line or raw_line.startswith("#") or "=" not in raw_line:
            continue
        key, value = raw_line.split("=", 1)
        key = key.strip()
        if key and value:
            parsed[key] = value
    return parsed


def git_show(repo: Path, commit: str, path: str) -> dict[str, str] | None:
    """The env entries of ``path`` at ``commit``; None when unreachable."""
    result = subprocess.run(
        ["git", "-C", str(repo), "show", f"{commit}:{path}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    parsed: dict[str, str] = {}
    for raw_line in result.stdout.splitlines():
        if not raw_line or raw_line.startswith("#") or "=" not in raw_line:
            continue
        key, value = raw_line.split("=", 1)
        key = key.strip()
        if key and value:
            parsed[key] = value
    return parsed


def _aws_pairs(parsed: dict[str, str]) -> list[tuple[str, str]]:
    key_id = parsed.get("AWS_ACCESS_KEY_ID")
    secret = parsed.get("AWS_SECRET_ACCESS_KEY")
    return [(key_id, secret)] if key_id and secret else []


def _azure_triples(parsed: dict[str, str]) -> list[tuple[str, str, str]]:
    client = parsed.get("AZURE_CLIENT_ID")
    tenant = parsed.get("AZURE_TENANT_ID")
    secret = parsed.get("AZURE_CLIENT_SECRET")
    return [(tenant, client, secret)] if client and tenant and secret else []


def _databricks_pairs(parsed: dict[str, str]) -> list[tuple[str, str]]:
    host = parsed.get("DATABRICKS_HOST")
    pairs = []
    for key in ("DATABRICKS_TOKEN", "DATABRICKS_PILOT_TOKEN"):
        if host and parsed.get(key):
            pairs.append((host, parsed[key]))
    return pairs


def collect_old_values(
    bak_files: list[Path],
    git_sources: list[tuple[Path, str, str]],
) -> dict[str, list[tuple[str, ...]]]:
    """Per-surface distinct old credentials (deduped; never printed).

    Values are tuples: aws=(key_id, secret), azure=(client, tenant,
    secret), databricks=(host, token), gcp/stripe/snowflake=(value,).
    """
    collected: dict[str, list[tuple[str, ...]]] = {
        "aws": [],
        "azure": [],
        "databricks": [],
        "gcp": [],
        "stripe": [],
        "snowflake": [],
    }

    def add(surface: str, credential: tuple[str, ...]) -> None:
        if credential not in collected[surface]:
            collected[surface].append(credential)

    parsed_sources: list[dict[str, str]] = []
    for bak in bak_files:
        parsed_sources.append(parse_env_file(bak))
    for repo, commit, path in git_sources:
        parsed = git_show(repo, commit, path)
        if parsed:
            parsed_sources.append(parsed)

    for parsed in parsed_sources:
        for pair in _aws_pairs(parsed):
            add("aws", pair)
        for triple in _azure_triples(parsed):
            add("azure", triple)
        for host, token in _databricks_pairs(parsed):
            add("databricks", (host, token))
        for key in ("GCP_CREDENTIALS_JSON", "GCP_SERVICE_ACCOUNT_JSON"):
            if parsed.get(key):
                add("gcp", (parsed[key],))
        if parsed.get("STRIPE_SECRET_KEY"):
            add("stripe", (parsed["STRIPE_SECRET_KEY"],))
        if parsed.get("SNOWFLAKE_TOKEN"):
            add("snowflake", (parsed["SNOWFLAKE_TOKEN"],))
    return collected


def probe_stripe_dead(key: str, base: str | None = None) -> tuple[str, str]:
    """Expect 401 from Stripe for the old key."""
    import httpx

    base = base or "https://api.stripe.com"
    try:
        r = httpx.get(f"{base}/v1/balance", auth=(key, ""), timeout=20)
    except Exception as exc:  # noqa: BLE001 — probe; never leak the key
        return ("SKIP", type(exc).__name__)
    status = classify_http_status(r.status_code)
    return (status, f"HTTP {r.status_code}")


def probe_databricks_dead(host: str, token: str) -> tuple[str, str]:
    """Expect 403/401 from the workspace for the old PAT."""
    import httpx

    try:
        r = httpx.get(
            f"{host.rstrip('/')}/api/2.0/clusters/list",
            headers={"Authorization": f"Bearer {token}"},
            timeout=20,
        )
    except Exception as exc:  # noqa: BLE001 — probe; never leak the key
        return ("SKIP", type(exc).__name__)
    status = classify_http_status(r.status_code)
    return (status, f"HTTP {r.status_code}")


def probe_azure_dead(
    tenant: str, client: str, secret: str, endpoint: str | None = None
) -> tuple[str, str]:
    """Expect invalid_client from the token endpoint for the old secret."""
    import httpx

    endpoint = endpoint or (f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token")
    try:
        r = httpx.post(
            endpoint,
            data={
                "client_id": client,
                "client_secret": secret,
                "grant_type": "client_credentials",
                "scope": "https://graph.microsoft.com/.default",
            },
            timeout=20,
        )
    except Exception as exc:  # noqa: BLE001 — probe; never leak the key
        return ("SKIP", type(exc).__name__)
    status = classify_azure_token(r.status_code, r.text)
    return (status, f"HTTP {r.status_code}")


def probe_gcp_dead(raw_json: str) -> tuple[str, str]:
    """Expect invalid_grant from the SA-key token exchange."""
    try:
        import google.auth
        import google.auth.transport.requests
        from google.oauth2 import service_account
    except ImportError:
        return ("SKIP", "google-auth not installed here")
    try:
        info = json.loads(raw_json)
        credentials = service_account.Credentials.from_service_account_info(info)
        request = google.auth.transport.requests.Request()
        credentials.refresh(request)
    except Exception as exc:  # noqa: BLE001 — probe; never leak the key
        return (classify_gcp_grant(str(exc)), "")
    return ("FAIL", "exchange accepted the old key")


def probe_aws_dead(key_id: str, secret: str, endpoint: str | None = None) -> tuple[str, str]:
    """Expect an STS rejection for the old pair."""
    try:
        import boto3
    except ImportError:
        return ("SKIP", "boto3 not installed here")
    try:
        client = boto3.client(
            "sts",
            aws_access_key_id=key_id,
            aws_secret_access_key=secret,
            region_name="us-east-1",
            endpoint_url=endpoint,
        )
        client.get_caller_identity()
    except Exception as exc:  # noqa: BLE001 — probe; never leak the key
        code = getattr(exc, "response", {}).get("Error", {}).get("Code", "")
        if code:
            return (classify_aws_sts(code), code)
        return ("SKIP", type(exc).__name__)
    return ("FAIL", "STS accepted the old pair")


def probe_snowflake_dead(
    token: str, account: str | None = None, user: str | None = None
) -> tuple[str, str]:
    """Expect an auth-class rejection from Snowflake for the old token."""
    try:
        import snowflake.connector
    except ImportError:
        return ("SKIP", "snowflake-connector-python not installed here")
    account = account or os.getenv("SNOWFLAKE_ACCOUNT", "")
    user = user or os.getenv("SNOWFLAKE_USER", "")
    if not account:
        return ("SKIP", "SNOWFLAKE_ACCOUNT not set")
    try:
        conn = snowflake.connector.connect(
            account=account,
            user=user,
            authenticator="oauth",
            token=token,
            login_timeout=20,
        )
        conn.close()
    except Exception as exc:  # noqa: BLE001 — probe; never leak the key
        return (classify_snowflake_auth(str(exc)), "")
    return ("FAIL", "Snowflake accepted the old token")


_SURFACE_PROBES = {
    "aws": probe_aws_dead,
    "azure": probe_azure_dead,
    "databricks": probe_databricks_dead,
    "gcp": probe_gcp_dead,
    "stripe": probe_stripe_dead,
    "snowflake": probe_snowflake_dead,
}


def _resolve_sources(argv: list[str]) -> tuple[list[Path], list[tuple[Path, str, str]]]:
    """Source lists from argv/env (env overrides beat repo defaults)."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--bak-files", action="append", default=None)
    parser.add_argument("--git-commits", action="append", default=None)
    parser.add_argument("--current-files", action="append", default=None)
    args = parser.parse_args(argv)

    if args.bak_files is not None:
        bak_files = [Path(p) for p in args.bak_files]
    elif os.environ.get("OLD_CREDS_BAK_FILES") is not None:
        bak_files = [Path(p) for p in os.environ["OLD_CREDS_BAK_FILES"].split(":") if p]
    else:
        bak_files = sorted(_ROOT.glob(".env*.bak-*"))

    git_sources: list[tuple[Path, str, str]] = []
    if args.git_commits is not None:
        pairs = args.git_commits
    elif os.environ.get("OLD_CREDS_GIT_COMMITS") is not None:
        pairs = os.environ["OLD_CREDS_GIT_COMMITS"].split(":")
    else:
        pairs = [f"{commit}:{path}" for commit in _LEAK_COMMITS for path in _GIT_SOURCE_PATHS]
    for pair in pairs:
        if ":" in pair:
            commit, path = pair.split(":", 1)
            git_sources.append((_ROOT, commit, path))

    if args.current_files is not None:
        current_files = [Path(p) for p in args.current_files]
    elif os.environ.get("OLD_CREDS_CURRENT_FILES") is not None:
        current_files = [Path(p) for p in os.environ["OLD_CREDS_CURRENT_FILES"].split(":") if p]
    else:
        current_files = [
            _ROOT / ".env.test",
            _ROOT / ".env.staging",
            _ROOT / ".env",
            _ROOT / ".env.dev",
        ]
    bak_files.extend(current_files)
    return bak_files, git_sources


def main(argv: list[str] | None = None) -> int:
    argv = list(argv) if argv is not None else sys.argv[1:]
    strict = "--strict" in argv or os.environ.get("CI") == "true"
    bak_files, git_sources = _resolve_sources(argv)
    collected = collect_old_values(bak_files, git_sources)

    failed = False
    for surface in ("aws", "gcp", "azure", "databricks", "snowflake", "stripe"):
        credentials = collected[surface]
        if not credentials:
            print(f"{surface:<10} ADVISORY source-missing (frozen-evidence mode)")
            if strict:
                failed = True
            continue
        for credential in credentials:
            try:
                status, detail = _SURFACE_PROBES[surface](*credential)
            except Exception as exc:  # noqa: BLE001 — probe; never leak values
                status, detail = ("SKIP", type(exc).__name__)
            suffix = f" ({detail})" if detail else ""
            print(f"{surface:<10} {status:<8}{suffix}")
            if status == "FAIL" or (status in ("SKIP", "ADVISORY") and strict):
                failed = True

    print("verify_old_creds_dead:", "FAIL" if failed else "OK")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
