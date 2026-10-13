#!/usr/bin/env python3
"""
Verify live connector credentials without printing secret values.

Each probe reports PASS / FAIL(status or error class) / SKIP(missing key)
for one connector.  Reads keys from the environment (load ``.env.test``
first if you run host-side):

    set -a; source .env.test; set +a
    python scripts/verify_connector_creds.py [snowflake|stripe|azure|dados|ckan|gcp|azure-sp|databricks]

The ckan probe targets the compose-internal ``http://ckan-test:5000`` by
default (that hostname only resolves inside the test network — run the
probe in a container, or override the base URL host-side, e.g.
``CKAN_TEST_BASE_URL=http://localhost:5100``).

``--strict`` (or ``CI=true``) turns every SKIP into a failure — the gate
mode used by ``make verify-pilot-creds-gate`` (oss-release-remediation
W0.5). Pass an explicit connector list in gate mode: the unprovisioned
connectors (dados, azure catalog) would otherwise fail the gate forever.

No secret value is ever printed — diagnostics name keys and statuses only.
See docs/runbooks/CREDENTIAL_PROVISIONING.md for acquisition steps.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

_TIMEOUT = 20
_CKAN_DEFAULT_BASE_URL = "http://ckan-test:5000"
_AZURE_TOKEN_ENDPOINT_DEFAULT = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"


def _report(name: str, status: str, detail: str = "") -> None:
    line = f"{name:<10} {status:<6}"
    if detail:
        line += f" ({detail})"
    print(line)


def _probe_snowflake() -> tuple[str, str]:
    key = os.getenv("SNOWFLAKE_TOKEN")
    if not key:
        _report("snowflake", "SKIP", "SNOWFLAKE_TOKEN not set")
        return ("SKIP", "SNOWFLAKE_TOKEN not set")
    try:
        import snowflake.connector
    except ImportError:
        _report("snowflake", "SKIP", "snowflake-connector-python not installed here")
        return ("SKIP", "snowflake-connector-python not installed here")
    try:
        conn = snowflake.connector.connect(
            account=os.getenv("SNOWFLAKE_ACCOUNT", ""),
            user=os.getenv("SNOWFLAKE_USER", ""),
            authenticator="oauth",
            token=key,
            login_timeout=20,
        )
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.fetchone()
        conn.close()
        status, detail = ("PASS", "")
    except Exception as exc:  # noqa: BLE001 — probe; never leak the key
        status, detail = ("FAIL", type(exc).__name__)
    _report("snowflake", status, detail)
    return (status, detail)


def _probe_stripe() -> tuple[str, str]:
    key = os.getenv("STRIPE_SECRET_KEY")
    if not key:
        _report("stripe", "SKIP", "STRIPE_SECRET_KEY not set")
        return ("SKIP", "STRIPE_SECRET_KEY not set")
    try:
        import httpx
    except ImportError:
        _report("stripe", "SKIP", "httpx not installed here")
        return ("SKIP", "httpx not installed here")
    try:
        r = httpx.get(
            "https://api.stripe.com/v1/balance",
            auth=(key, ""),
            timeout=_TIMEOUT,
        )
        if r.status_code == 200:
            status, detail = ("PASS", "")
        else:
            status, detail = ("FAIL", f"HTTP {r.status_code}")
    except Exception as exc:  # noqa: BLE001 — probe; never leak the key
        status, detail = ("FAIL", type(exc).__name__)
    _report("stripe", status, detail)
    return (status, detail)


def _probe_azure() -> tuple[str, str]:
    key = os.getenv("AZURE_MARKETPLACE_API_KEY") or os.getenv("AZURE_CATALOG_API_KEY")
    if not key:
        _report("azure", "SKIP", "AZURE_MARKETPLACE_API_KEY not set")
        return ("SKIP", "AZURE_MARKETPLACE_API_KEY not set")
    try:
        import httpx
    except ImportError:
        _report("azure", "SKIP", "httpx not installed here")
        return ("SKIP", "httpx not installed here")
    try:
        r = httpx.get(
            "https://catalogapi.azure.com/products",
            params={"api-version": "2025-05-01"},
            headers={"X-API-Key": key},
            timeout=_TIMEOUT,
        )
        if r.status_code == 200:
            status, detail = ("PASS", "")
        else:
            status, detail = ("FAIL", f"HTTP {r.status_code}")
    except Exception as exc:  # noqa: BLE001 — probe; never leak the key
        status, detail = ("FAIL", type(exc).__name__)
    _report("azure", status, detail)
    return (status, detail)


def _probe_dados() -> tuple[str, str]:
    key = os.getenv("DADOS_GOV_BR_API_KEY") or os.getenv("CKAN_DADOS_GOV_BR_API_KEY")
    if not key:
        _report("dados", "SKIP", "DADOS_GOV_BR_API_KEY not set")
        return ("SKIP", "DADOS_GOV_BR_API_KEY not set")
    try:
        import httpx
    except ImportError:
        _report("dados", "SKIP", "httpx not installed here")
        return ("SKIP", "httpx not installed here")
    try:
        r = httpx.get(
            "https://dados.gov.br/api/3/action/package_list",
            headers={"Authorization": key},
            timeout=_TIMEOUT,
        )
        if r.status_code == 200:
            status, detail = ("PASS", "")
        else:
            status, detail = ("FAIL", f"HTTP {r.status_code}")
    except Exception as exc:  # noqa: BLE001 — probe; never leak the key
        status, detail = ("FAIL", type(exc).__name__)
    _report("dados", status, detail)
    return (status, detail)


def ckan_probe_result(
    key: str | None,
    base: str | None = None,
    admin_user: str | None = None,
) -> tuple[str, str]:
    """Probe a CKAN API key and return (status, detail) without printing.

    status is PASS / FAIL / SKIP; detail is empty on PASS and never
    contains the key.  Reused by scripts/verify_test_stack_creds.py.
    """
    if not key:
        return ("SKIP", "CKAN_TEST_API_KEY not set")
    try:
        import httpx
    except ImportError:
        return ("SKIP", "httpx not installed here")
    try:
        base = base or os.getenv("CKAN_TEST_BASE_URL", _CKAN_DEFAULT_BASE_URL)
        admin_user = admin_user or os.getenv("CKAN_TEST_ADMIN_USER", "admin")
        # api_token_list is auth-required, unlike package_list (public —
        # a bogus token also gets 200 there). CKAN returns 200 with
        # {"success": false} on denied actions, so the JSON body is part
        # of the verdict: valid sysadmin token -> 200 success=true;
        # invalid/revoked -> 403.
        r = httpx.get(
            f"{base}/api/3/action/api_token_list",
            params={"user_id": admin_user},
            headers={"Authorization": key},
            timeout=_TIMEOUT,
        )
        if r.status_code == 200 and r.json().get("success"):
            return ("PASS", "")
        else:
            return ("FAIL", f"HTTP {r.status_code}")
    except Exception as exc:  # noqa: BLE001 — probe; never leak the key
        return ("FAIL", type(exc).__name__)


def _probe_ckan() -> tuple[str, str]:
    status, detail = ckan_probe_result(os.getenv("CKAN_TEST_API_KEY"))
    _report("ckan", status, detail)
    return (status, detail)


def gcp_probe_result(raw_json: str | None) -> tuple[str, str]:
    """Probe a GCP SA-key JSON: token exchange proves the key is valid.

    status is PASS / FAIL / SKIP; detail never contains key material.
    """
    raw_json = (
        raw_json or os.getenv("GCP_CREDENTIALS_JSON") or os.getenv("GCP_SERVICE_ACCOUNT_JSON")
    )
    if not raw_json:
        return ("SKIP", "GCP_CREDENTIALS_JSON not set")
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
        name = type(exc).__name__
        detail = "invalid_grant" if "invalid_grant" in str(exc) else name
        return ("FAIL", detail)
    return ("PASS", "")


def _probe_gcp() -> tuple[str, str]:
    status, detail = gcp_probe_result(None)
    _report("gcp", status, detail)
    return (status, detail)


def azure_sp_probe_result(
    tenant_id: str | None,
    client_id: str | None,
    client_secret: str | None,
) -> tuple[str, str]:
    """Probe an Azure SP client-secret pair via a client_credentials exchange.

    status is PASS / FAIL / SKIP; detail never contains the secret.
    ``AZURE_TOKEN_ENDPOINT`` overrides the token URL (test hook — the
    default is login.microsoftonline.com).
    """
    if not (client_id and client_secret and tenant_id):
        missing = [
            name
            for name, value in (
                ("AZURE_CLIENT_ID", client_id),
                ("AZURE_TENANT_ID", tenant_id),
                ("AZURE_CLIENT_SECRET", client_secret),
            )
            if not value
        ]
        return ("SKIP", f"{' / '.join(missing)} not set")
    try:
        import httpx
    except ImportError:
        return ("SKIP", "httpx not installed here")
    endpoint = os.getenv(
        "AZURE_TOKEN_ENDPOINT",
        _AZURE_TOKEN_ENDPOINT_DEFAULT.format(tenant=tenant_id),
    )
    try:
        r = httpx.post(
            endpoint,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "client_credentials",
                "scope": "https://graph.microsoft.com/.default",
            },
            timeout=_TIMEOUT,
        )
    except Exception as exc:  # noqa: BLE001 — probe; never leak the key
        return ("FAIL", type(exc).__name__)
    if r.status_code == 200:
        return ("PASS", "")
    detail = f"HTTP {r.status_code}"
    if "AADSTS7000215" in r.text or "AADSTS7000222" in r.text:
        detail = "invalid_client"
    return ("FAIL", detail)


def _probe_azure_sp() -> tuple[str, str]:
    status, detail = azure_sp_probe_result(
        os.getenv("AZURE_TENANT_ID"),
        os.getenv("AZURE_CLIENT_ID"),
        os.getenv("AZURE_CLIENT_SECRET"),
    )
    _report("azure-sp", status, detail)
    return (status, detail)


def _normalize_host(host: str) -> str:
    """A bare host gets https:// — the env files carry schemeless hosts."""
    return host if "://" in host else f"https://{host}"


def databricks_probe_result(host: str | None, token: str | None) -> tuple[str, str]:
    """Probe a Databricks workspace PAT (the sandbox account — the pilot
    verifier covers the PILOT account separately).

    status is PASS / FAIL / SKIP; detail never contains the token.
    """
    if not host or not token:
        missing = [
            name
            for name, value in (("DATABRICKS_HOST", host), ("DATABRICKS_TOKEN", token))
            if not value
        ]
        return ("SKIP", f"{' / '.join(missing)} not set")
    try:
        import httpx
    except ImportError:
        return ("SKIP", "httpx not installed here")
    normalized_host = _normalize_host(host)
    try:
        r = httpx.get(
            f"{normalized_host.rstrip('/')}/api/2.0/clusters/list",
            headers={"Authorization": f"Bearer {token}"},
            timeout=_TIMEOUT,
        )
    except Exception as exc:  # noqa: BLE001 — probe; never leak the key
        return ("FAIL", type(exc).__name__)
    if r.status_code == 200:
        return ("PASS", "")
    return ("FAIL", f"HTTP {r.status_code}")


def _probe_databricks() -> tuple[str, str]:
    status, detail = databricks_probe_result(
        os.getenv("DATABRICKS_HOST"), os.getenv("DATABRICKS_TOKEN")
    )
    _report("databricks", status, detail)
    return (status, detail)


_PROBES = {
    "snowflake": _probe_snowflake,
    "stripe": _probe_stripe,
    "azure": _probe_azure,
    "dados": _probe_dados,
    "ckan": _probe_ckan,
    "gcp": _probe_gcp,
    "azure-sp": _probe_azure_sp,
    "databricks": _probe_databricks,
}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "connectors",
        nargs="*",
        choices=sorted(_PROBES),
        help="Connectors to probe (default: all)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="SKIP becomes failure (exit 1) — the gate mode",
    )
    args = parser.parse_args(argv)

    # W16 environment policy: in CI a missing credential is an
    # environment failure, never a graceful skip.
    strict = args.strict or os.environ.get("CI") == "true"
    targets = args.connectors or sorted(_PROBES)
    failed = False
    for name in targets:
        status, _detail = _PROBES[name]()
        if status == "FAIL":
            failed = True
        elif status == "SKIP" and strict:
            print(
                f"{name:<10} FAIL: strict mode (or CI) — a missing connector "
                "credential cannot be skipped when the gate is armed"
            )
            failed = True
    if failed:
        print("verify-connector-creds: FAIL")
        sys.exit(1)
    print("verify-connector-creds: OK")
    sys.exit(0)


if __name__ == "__main__":
    main()
