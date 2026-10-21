#!/usr/bin/env python3
"""
Verify the PILOT (customer) account credentials without printing secrets.

pilot-readiness 2.2 — the acquisition oracle for the customer's
Databricks + AWS estate. Five live probes, each PASS / FAIL(reason) /
SKIP(missing keys):

    databricks  workspace auth — PAT, or a REAL OAuth M2M exchange
                (client_credentials, scope=all-apis) against the
                workspace /oidc/v1/token endpoint, then a live
                api/2.0/clusters/list probe.
    warehouse   the SQL warehouse EXISTS and reports its state
                (RUNNING/STOPPED) — the probe NEVER starts compute:
                no query may run before the budget caps are verified.
    aws         the AWS keys resolve via STS GetCallerIdentity and
                report WHICH account they belong to (never the keys).
    dlt         the dlt destination can RECEIVE data: an S3
                write/delete roundtrip of a probe object under a
                reserved ``.datahub-pilot-probe/`` prefix (file://
                destinations get a local write/delete roundtrip).
    budgets     THE FIRST-QUERY GUARDRAIL, two account classes
                (product-owner re-scope, 2026-10-05): on a PAID account
                the account-level budget-policies API (2.1, 2.0
                fallback) must list >=1 policy that is account-wide or
                bound to the pilot workspace — no verified caps = no
                first query. On a FREE-EDITION account (no account
                plane, no budget surface anywhere — detected by probing
                the workspace budget endpoints) a declared re-scope
                (PILOT_BUDGET_CAPS_RESCOPE=free-edition-no-billing)
                reports RESCOPE; no declaration FAILs loudly.

Environment (all PILOT-prefixed — never the sandbox account):

    DATABRICKS_PILOT_HOST / DATABRICKS_PILOT_TOKEN            (PAT)
    DATABRICKS_PILOT_CLIENT_ID / DATABRICKS_PILOT_CLIENT_SECRET (M2M SP)
    DATABRICKS_PILOT_WAREHOUSE_ID   (+ optional DATABRICKS_PILOT_HTTP_PATH)
    DATABRICKS_PILOT_WORKSPACE_ID   (budget-policy binding match, optional)
    DATABRICKS_ACCOUNT_HOST         (default https://accounts.cloud.databricks.com)
    DATABRICKS_ACCOUNT_ID
    DATABRICKS_ACCOUNT_CLIENT_ID / DATABRICKS_ACCOUNT_CLIENT_SECRET (account M2M)
        — or DATABRICKS_ACCOUNT_USERNAME / DATABRICKS_ACCOUNT_PASSWORD (basic)
    PILOT_BUDGET_CAPS_RESCOPE      (free-edition accounts only, optional)
                                   = free-edition-no-billing (the one
                                   supported class — see the budgets probe)
    AWS_PILOT_ACCESS_KEY_ID / AWS_PILOT_SECRET_ACCESS_KEY
    AWS_PILOT_REGION                (default us-east-1)
    AWS_PILOT_ENDPOINT_URL          (generic endpoint override, e.g. for probes)
    AWS_PILOT_S3_ENDPOINT_URL       (S3-ONLY override for the dlt roundtrip —
                                    e.g. the dev stack's MinIO; never
                                    redirects the STS identity probe)
    AWS_PILOT_S3_ACCESS_KEY_ID / AWS_PILOT_S3_SECRET_ACCESS_KEY
                                    (S3-ONLY credential pair for the dlt
                                    destination; the identity pair is the
                                    fallback — MinIO needs its own keys)
    AWS_PILOT_S3_REGION            (S3-ONLY region, default us-east-1 —
                                    never inherits AWS_PILOT_REGION;
                                    MinIO's default signature region)
    DLT_PILOT_BUCKET_URL            (s3://bucket/prefix or file:///path;
                                     falls back to DLT_FILESYSTEM_BUCKET_URL)

Wiring-mismatch guards (identifiers only — secrets are NEVER compared or
printed): the probe FAILS before any request when the generic/sandbox
vars the live suites consume (DATABRICKS_HOST,
DATABRICKS_SANDBOX_WAREHOUSE_ID, DATABRICKS_PILOT_HTTP_PATH) point at a
different workspace/warehouse than the pilot vars — the suites would
otherwise run against the WRONG account.

Modes:

    python scripts/verify_pilot_creds.py                        # advisory: SKIP exits 0
    python scripts/verify_pilot_creds.py --strict               # SKIP -> failure (post-flight/CI)
    python scripts/verify_pilot_creds.py --require-budgets      # exit 1 unless budgets PASS

Exit code 0 only when every executed probe PASSed (advisory mode
ignores SKIPs); 1 otherwise. See docs/runbooks/CREDENTIAL_PROVISIONING.md
for the acquisition steps.
"""

from __future__ import annotations

import argparse
import base64
import contextlib
import os
import re
import sys
import urllib.parse
import uuid

_TIMEOUT = 20
_ACCOUNT_HOST_DEFAULT = "https://accounts.cloud.databricks.com"
_PROBE_ORDER = ("databricks", "warehouse", "aws", "dlt", "budgets")
# The workspace-side budget surfaces a PAID workspace exposes (a
# free-edition account answers 404 on all three — probed live 2026-10-05).
_WORKSPACE_BUDGET_SURFACES = ("/api/2.0/budgets/limits", "/api/2.0/budgets", "/api/2.1/budgets")
# The product-owner re-scope classes (pilot-readiness 2.2 STOP-THE-LINE):
# an account class with NO budget surface. The key names the account
# class; the value records WHY caps are N/A there.
_RESCOPE_CLASSES = {
    "free-edition-no-billing": (
        "free-edition account — no account plane, no billing, no budget "
        "API surface; spend caps are N/A (zero-cost tier)"
    ),
}


def _report(name: str, status: str, detail: str = "") -> None:
    line = f"{name:<10} {status:<7}"
    if detail:
        line += f" ({detail})"
    print(line)


def _normalize_host(host: str) -> str:
    """Scheme + trailing-slash insensitive host comparison."""
    host = host.strip()
    for scheme in ("https://", "http://"):
        if host.startswith(scheme):
            host = host[len(scheme) :]
            break
    return host.rstrip("/").lower()


def _api_base(host_raw: str) -> str:
    """The request base URL: the env vars may carry a bare host (the
    .env.test convention) — Databricks API endpoints are TLS-only, so a
    scheme-less host gets https:// prefixed; an explicit scheme (incl.
    http:// for scripted local endpoints) is preserved."""
    host = host_raw.strip().rstrip("/")
    if host.startswith(("http://", "https://")):
        return host
    return f"https://{host}"


def _m2m_exchange(
    host: str,
    client_id: str,
    client_secret: str,
    label: str = "exchange ",
) -> tuple[str, str]:
    """A real OAuth M2M client-credentials exchange (scope=all-apis — the
    same exchange the warehouses connector performs). Returns
    (access_token, ""); on failure returns ("", detail). The secret is
    never included."""
    import httpx

    try:
        r = httpx.post(
            f"{host}/oidc/v1/token",
            data={
                "grant_type": "client_credentials",
                "scope": "all-apis",
                "client_id": client_id,
                "client_secret": client_secret,
            },
            timeout=_TIMEOUT,
        )
    except Exception as exc:  # noqa: BLE001 — probe; never leak the key
        return "", f"{label}{type(exc).__name__}"
    if r.status_code != 200:
        return "", f"{label}HTTP {r.status_code}"
    try:
        payload = r.json()
    except ValueError:
        return "", f"{label}response is not valid JSON"
    access = payload.get("access_token", "") if isinstance(payload, dict) else ""
    if not access:
        return "", f"{label}response carried no access_token"
    return access, ""


def _workspace_bearer(host: str) -> tuple[str, str]:
    """Resolve a workspace bearer token: PAT wins over a real M2M
    exchange. Returns (bearer, mode); on exchange failure returns
    ("", detail). The secret is never included."""
    token = os.getenv("DATABRICKS_PILOT_TOKEN", "")
    if token:
        return token, "PAT"
    client_id = os.getenv("DATABRICKS_PILOT_CLIENT_ID", "")
    client_secret = os.getenv("DATABRICKS_PILOT_CLIENT_SECRET", "")
    if not (client_id and client_secret):
        return "", ""
    access, detail = _m2m_exchange(host, client_id, client_secret)
    if detail:
        return "", detail
    return access, "M2M"


def databricks_probe_result() -> tuple[str, str]:
    """Probe the PILOT workspace auth (never the sandbox account)."""
    host_raw = os.getenv("DATABRICKS_PILOT_HOST", "")
    if not host_raw:
        return (
            "SKIP",
            "DATABRICKS_PILOT_HOST + DATABRICKS_PILOT_TOKEN "
            "(or DATABRICKS_PILOT_CLIENT_ID/DATABRICKS_PILOT_CLIENT_SECRET) not set",
        )
    host = _api_base(host_raw)
    generic_host = os.getenv("DATABRICKS_HOST", "")
    if generic_host and _normalize_host(generic_host) != _normalize_host(host):
        return (
            "FAIL",
            f"env wiring mismatch: DATABRICKS_HOST={generic_host} targets a "
            "different workspace than DATABRICKS_PILOT_HOST — the live "
            "suites would run against the wrong account",
        )
    bearer, mode = _workspace_bearer(host)
    if not bearer:
        status = "FAIL" if mode else "SKIP"
        detail = (
            f"M2M token exchange failed: {mode}"
            if mode
            else "DATABRICKS_PILOT_TOKEN (or DATABRICKS_PILOT_CLIENT_ID + "
            "DATABRICKS_PILOT_CLIENT_SECRET) not set"
        )
        return status, detail
    import httpx

    try:
        r = httpx.get(
            f"{host}/api/2.0/clusters/list",
            headers={"Authorization": f"Bearer {bearer}"},
            timeout=_TIMEOUT,
        )
    except Exception as exc:  # noqa: BLE001 — probe; never leak the key
        return "FAIL", type(exc).__name__
    if r.status_code != 200:
        return "FAIL", f"HTTP {r.status_code}"
    return "PASS", mode


def _probe_databricks() -> str:
    status, detail = databricks_probe_result()
    _report("databricks", status, detail)
    return status


def _warehouse_wiring_mismatch(warehouse_id: str) -> str:
    """The mismatch detail when the suites' consumed vars point at a
    different warehouse than the pilot id (identifiers only — secrets
    are never compared); '' when the wiring is consistent."""
    sandbox_id = os.getenv("DATABRICKS_SANDBOX_WAREHOUSE_ID", "")
    if sandbox_id and sandbox_id != warehouse_id:
        return (
            f"env wiring mismatch: DATABRICKS_SANDBOX_WAREHOUSE_ID={sandbox_id} "
            "differs from DATABRICKS_PILOT_WAREHOUSE_ID — the live suites "
            "would start the wrong warehouse"
        )
    http_path = os.getenv("DATABRICKS_PILOT_HTTP_PATH", "")
    path_id = re.search(r"/sql/1.0/warehouses/([^/]+)", http_path or "")
    if path_id and path_id.group(1) != warehouse_id:
        return (
            "env wiring mismatch: DATABRICKS_PILOT_HTTP_PATH points at "
            f"warehouse {path_id.group(1)}, not {warehouse_id}"
        )
    return ""


def warehouse_probe_result() -> tuple[str, str]:
    """Probe the PILOT SQL warehouse — state only, NEVER a start.

    The budget-cap guardrail: no compute may be touched before the
    budgets probe verified the caps. A STOPPED warehouse is reported,
    not started (starting is 2.3's job, after the caps are verified).
    """
    warehouse_id = os.getenv("DATABRICKS_PILOT_WAREHOUSE_ID", "")
    host_raw = os.getenv("DATABRICKS_PILOT_HOST", "")
    if not host_raw or not warehouse_id:
        return (
            "SKIP",
            "DATABRICKS_PILOT_HOST + DATABRICKS_PILOT_WAREHOUSE_ID not set",
        )
    mismatch = _warehouse_wiring_mismatch(warehouse_id)
    if mismatch:
        return "FAIL", mismatch
    host = _api_base(host_raw)
    bearer, mode = _workspace_bearer(host)
    if not bearer:
        status = "FAIL" if mode else "SKIP"
        detail = (
            f"M2M token exchange failed: {mode}"
            if mode
            else "DATABRICKS_PILOT_TOKEN (or DATABRICKS_PILOT_CLIENT_ID + "
            "DATABRICKS_PILOT_CLIENT_SECRET) not set"
        )
        return status, detail
    import httpx

    try:
        r = httpx.get(
            f"{host}/api/2.0/sql/warehouses/{warehouse_id}",
            headers={"Authorization": f"Bearer {bearer}"},
            timeout=_TIMEOUT,
        )
    except Exception as exc:  # noqa: BLE001 — probe; never leak the key
        return "FAIL", type(exc).__name__
    if r.status_code != 200:
        detail = (
            "HTTP 404 (warehouse not found — check the id)"
            if r.status_code == 404
            else f"HTTP {r.status_code}"
        )
        return "FAIL", detail
    state = ""
    try:
        payload = r.json()
        if isinstance(payload, dict):
            state = payload.get("state", "")
    except ValueError:
        pass
    return "PASS", f"state={state}" if state else "state unknown"


def _probe_warehouse() -> str:
    status, detail = warehouse_probe_result()
    _report("warehouse", status, detail)
    return status


def _aws_session():
    import boto3

    return boto3.Session(
        aws_access_key_id=os.getenv("AWS_PILOT_ACCESS_KEY_ID", ""),
        aws_secret_access_key=os.getenv("AWS_PILOT_SECRET_ACCESS_KEY", ""),
        region_name=os.getenv("AWS_PILOT_REGION", "us-east-1"),
    )


def aws_probe_result() -> tuple[str, str]:
    """Probe the PILOT AWS keys via STS GetCallerIdentity."""
    access = os.getenv("AWS_PILOT_ACCESS_KEY_ID", "")
    secret = os.getenv("AWS_PILOT_SECRET_ACCESS_KEY", "")
    if not access or not secret:
        return "SKIP", "AWS_PILOT_ACCESS_KEY_ID + AWS_PILOT_SECRET_ACCESS_KEY not set"
    try:
        from botocore.exceptions import ClientError
    except ImportError:
        return "SKIP", "boto3 not installed here"
    try:
        endpoint = os.getenv("AWS_PILOT_ENDPOINT_URL", "")
        kwargs = {"endpoint_url": endpoint} if endpoint else {}
        sts = _aws_session().client("sts", **kwargs)
        identity = sts.get_caller_identity()
        account = identity.get("Account", "unknown")
    except ClientError as exc:  # never the raw body — the code names the class
        code = exc.response.get("Error", {}).get("Code", type(exc).__name__)
        return "FAIL", str(code)
    except Exception as exc:  # noqa: BLE001 — probe; never leak the keys
        return "FAIL", type(exc).__name__
    else:
        return "PASS", f"account={account}"


def _probe_aws() -> str:
    status, detail = aws_probe_result()
    _report("aws", status, detail)
    return status


def _dlt_s3_probe(url: str) -> tuple[str, str]:
    """The destination must be able to RECEIVE data — a list-only probe
    would miss the write-permission landmine. A probe object is written
    under the reserved .datahub-pilot-probe/ prefix and deleted in the
    same roundtrip."""
    # The destination's credentials are INDEPENDENT of the AWS identity
    # pair: the dev stack's MinIO rejects the Athena keys
    # (InvalidAccessKeyId — hit live 2026-10-05), so the S3-only pair
    # wins when set and the identity pair is the fallback.
    access = os.getenv("AWS_PILOT_S3_ACCESS_KEY_ID") or os.getenv("AWS_PILOT_ACCESS_KEY_ID", "")
    secret = os.getenv("AWS_PILOT_S3_SECRET_ACCESS_KEY") or os.getenv(
        "AWS_PILOT_SECRET_ACCESS_KEY", ""
    )
    if not access or not secret:
        return (
            "SKIP",
            "AWS_PILOT_ACCESS_KEY_ID + AWS_PILOT_SECRET_ACCESS_KEY "
            "(or the AWS_PILOT_S3_* pair) not set",
        )
    try:
        import boto3
        from botocore.exceptions import ClientError
    except ImportError:
        return "SKIP", "boto3 not installed here"
    parsed = urllib.parse.urlparse(url)
    bucket = parsed.netloc
    prefix = parsed.path.lstrip("/").rstrip("/")
    if not bucket:
        return "FAIL", "s3:// destination has no bucket name"
    try:
        # AWS_PILOT_S3_ENDPOINT_URL is the S3-ONLY override (an
        # S3-compatible store such as the dev stack's MinIO); it falls
        # back to the generic override — the STS identity probe is
        # deliberately NOT redirected by the S3-specific key.
        endpoint = os.getenv("AWS_PILOT_S3_ENDPOINT_URL") or os.getenv("AWS_PILOT_ENDPOINT_URL", "")
        kwargs = {"endpoint_url": endpoint} if endpoint else {}
        session = boto3.Session(
            aws_access_key_id=access,
            aws_secret_access_key=secret,
            # The destination's region is INDEPENDENT of the identity
            # region: MinIO's default is us-east-1 and inheriting
            # AWS_PILOT_REGION (eu-central-1) breaks its signature
            # (InvalidAccessKeyId — hit live 2026-10-05).
            region_name=os.getenv("AWS_PILOT_S3_REGION", "us-east-1"),
        )
        s3 = session.client("s3", **kwargs)
        # list first (not head_bucket): a LIST proves read access AND its
        # 404 carries a parseable error code, while head_bucket's 404 is
        # ambiguous (botocore reports the bare status, losing the class).
        s3.list_objects_v2(Bucket=bucket, MaxKeys=1)
        key = (
            f"{prefix}/.datahub-pilot-probe/{uuid.uuid4().hex}.txt"
            if prefix
            else f".datahub-pilot-probe/{uuid.uuid4().hex}.txt"
        )
        s3.put_object(Bucket=bucket, Key=key, Body=b"datahub pilot credential probe\n")
        s3.delete_object(Bucket=bucket, Key=key)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", type(exc).__name__)
        return "FAIL", str(code)
    except Exception as exc:  # noqa: BLE001 — probe; never leak the keys
        return "FAIL", type(exc).__name__
    else:
        return "PASS", f"s3://{bucket}/{prefix or ''}".rstrip("/")


def _dlt_file_probe(path: str) -> tuple[str, str]:
    if not os.path.isdir(path):
        return "FAIL", "directory does not exist"
    probe = os.path.join(path, f".datahub-pilot-probe-{uuid.uuid4().hex}.txt")
    try:
        with open(probe, "w") as fh:
            fh.write("datahub pilot credential probe\n")
        os.unlink(probe)
    except OSError as exc:
        with contextlib.suppress(OSError):
            os.unlink(probe)
        return "FAIL", type(exc).__name__
    else:
        return "PASS", "writable"


def dlt_probe_result() -> tuple[str, str]:
    """Probe the PILOT dlt destination (s3:// write/delete roundtrip,
    file:// writability check)."""
    url = os.getenv("DLT_PILOT_BUCKET_URL", "") or os.getenv("DLT_FILESYSTEM_BUCKET_URL", "")
    if not url:
        return "SKIP", "DLT_PILOT_BUCKET_URL (or DLT_FILESYSTEM_BUCKET_URL) not set"
    scheme = urllib.parse.urlparse(url).scheme
    if scheme == "s3":
        return _dlt_s3_probe(url)
    if scheme == "file":
        return _dlt_file_probe(urllib.parse.urlparse(url).path)
    return "FAIL", f"unsupported destination scheme '{scheme}'"


def _probe_dlt() -> str:
    status, detail = dlt_probe_result()
    _report("dlt", status, detail)
    return status


def _account_auth_headers(account_host: str) -> tuple[dict[str, str], str, str]:
    """Account-level auth for the budget-policies API: a real M2M
    exchange (account SP) or basic auth. Returns (headers, status,
    detail); status is '' once authorized."""
    account_client_id = os.getenv("DATABRICKS_ACCOUNT_CLIENT_ID", "")
    account_client_secret = os.getenv("DATABRICKS_ACCOUNT_CLIENT_SECRET", "")
    username = os.getenv("DATABRICKS_ACCOUNT_USERNAME", "")
    password = os.getenv("DATABRICKS_ACCOUNT_PASSWORD", "")
    if account_client_id and account_client_secret:
        access, detail = _m2m_exchange(
            account_host, account_client_id, account_client_secret, label="account M2M exchange "
        )
        if detail:
            # Live-discriminated (2026-10-05): a WORKSPACE-issued SP
            # authenticates the workspace token endpoint (200) but the
            # ACCOUNT endpoint rejects it with 400. Name the class so
            # the operator goes to the right console.
            if "HTTP 400" in detail:
                detail += (
                    " — the SP may be workspace-issued (workspace "
                    "principals cannot authenticate the account API; "
                    "create the service principal in the ACCOUNT console "
                    "and generate its OAuth secret there)"
                )
            return {}, "FAIL", detail
        return {"Authorization": f"Bearer {access}"}, "", ""
    if username and password:
        pair = base64.b64encode(f"{username}:{password}".encode()).decode()
        return {"Authorization": f"Basic {pair}"}, "", ""
    return (
        {},
        "SKIP",
        "DATABRICKS_ACCOUNT_CLIENT_ID + DATABRICKS_ACCOUNT_CLIENT_SECRET "
        "(or DATABRICKS_ACCOUNT_USERNAME + DATABRICKS_ACCOUNT_PASSWORD) not set",
    )


def _fetch_budget_policies(
    account_host: str,
    account_id: str,
    headers: dict[str, str],
) -> tuple[list, str]:
    """The account budget-policies list (2.1 first, 2.0 fallback — both
    real surfaces). Returns (policies, detail); detail is '' on success."""
    import httpx

    for version in ("2.1", "2.0"):
        try:
            r = httpx.get(
                f"{account_host}/api/{version}/accounts/{account_id}/budget-policies",
                headers=headers,
                timeout=_TIMEOUT,
            )
        except Exception as exc:  # noqa: BLE001 — probe; never leak the key
            return [], type(exc).__name__
        if r.status_code == 200:
            try:
                payload = r.json()
            except ValueError:
                return [], "budget-policies response is not valid JSON"
            policies = (
                payload.get("policies", [])
                if isinstance(payload, dict)
                else payload
                if isinstance(payload, list)
                else None
            )
            if policies is None:
                return [], "budget-policies response carried no policy list"
            return policies, ""
        if r.status_code != 404:
            return [], f"HTTP {r.status_code}"
    return (
        [],
        "budget caps unverifiable (HTTP 404 on both the 2.1 and 2.0 "
        "budget-policies paths — the account API surface is unavailable)",
    )


def _budgets_without_account_creds() -> tuple[str, str]:
    """The account-class discriminator when NO account credentials exist.

    Probes the WORKSPACE budget surfaces with the workspace bearer:
    - any surface EXISTS (non-404) -> a PAID workspace: FAIL — account
      credentials are mandatory, the real caps path must run;
    - ALL surfaces absent (404 — probed live on free edition 2026-10-05)
      -> the free-edition class: a DECLARED re-scope
      (PILOT_BUDGET_CAPS_RESCOPE) reports RESCOPE; no declaration FAILs
      loudly — never a silent skip, never a faked PASS.
    """
    host_raw = os.getenv("DATABRICKS_PILOT_HOST", "")
    if not host_raw:
        return (
            "SKIP",
            "DATABRICKS_PILOT_HOST + workspace credentials not set "
            "(DATABRICKS_ACCOUNT_ID + account credentials would verify "
            "REAL caps on a paid account)",
        )
    host = _api_base(host_raw)
    bearer, mode = _workspace_bearer(host)
    if not bearer:
        status = "FAIL" if mode else "SKIP"
        detail = (
            f"M2M token exchange failed: {mode}"
            if mode
            else "DATABRICKS_PILOT_TOKEN (or DATABRICKS_PILOT_CLIENT_ID + "
            "DATABRICKS_PILOT_CLIENT_SECRET) not set"
        )
        return status, detail
    import httpx

    found: list[str] = []
    for surface in _WORKSPACE_BUDGET_SURFACES:
        try:
            r = httpx.get(
                f"{host}{surface}",
                headers={"Authorization": f"Bearer {bearer}"},
                timeout=_TIMEOUT,
            )
        except Exception as exc:  # noqa: BLE001 — probe; never leak the key
            return "FAIL", type(exc).__name__
        if r.status_code != 404:
            found.append(f"{surface} HTTP {r.status_code}")
    if found:
        return (
            "FAIL",
            f"a workspace budget surface exists ({found[0]}) but no "
            "account credentials are set — provide DATABRICKS_ACCOUNT_ID "
            "+ account credentials (a paid account must verify REAL caps)",
        )
    verdict, verdict_detail = _rescope_verdict()
    if verdict:
        return verdict, verdict_detail
    return (
        "FAIL",
        "no budget API surface exists on this account (workspace budget "
        "endpoints 404 and no account credentials are set). Free-edition "
        "account: record the product-owner re-scope via "
        "PILOT_BUDGET_CAPS_RESCOPE=free-edition-no-billing. Paid account: "
        "provide DATABRICKS_ACCOUNT_ID + account credentials",
    )


def _rescope_verdict() -> tuple[str, str]:
    """The declared re-scope verdict; ('', '') when undeclared."""
    rescope = os.getenv("PILOT_BUDGET_CAPS_RESCOPE", "")
    if not rescope:
        return "", ""
    if rescope in _RESCOPE_CLASSES:
        return (
            "RESCOPE",
            f"{rescope}: {_RESCOPE_CLASSES[rescope]} "
            f"(all {len(_WORKSPACE_BUDGET_SURFACES)} workspace budget "
            "surfaces probed absent; re-scope recorded in "
            "openspec/changes/pilot-readiness/tasks.md 2.2)",
        )
    return (
        "FAIL",
        f"unknown re-scope class '{rescope}' — supported: {', '.join(sorted(_RESCOPE_CLASSES))}",
    )


def budgets_probe_result() -> tuple[str, str]:
    """THE FIRST-QUERY GUARDRAIL: verify the account's budget caps.

    Two account classes (product-owner re-scope, 2026-10-05):
    - PAID account: PASS requires >=1 budget policy that is
      account-wide (empty binding_workspace_ids) or bound to
      DATABRICKS_PILOT_WORKSPACE_ID. Without a verified cap the first
      query must not run.
    - FREE-EDITION account (no account plane, no budget API anywhere):
      the probe DETECTS the absent surfaces by evidence and reports a
      declared RESCOPE state (PILOT_BUDGET_CAPS_RESCOPE) — never a
      silent skip, never a faked PASS.
    """
    account_id = os.getenv("DATABRICKS_ACCOUNT_ID", "")
    if not account_id:
        return _budgets_without_account_creds()
    account_host = _api_base(os.getenv("DATABRICKS_ACCOUNT_HOST", _ACCOUNT_HOST_DEFAULT))
    headers, status, detail = _account_auth_headers(account_host)
    if status:
        return status, detail
    policies, detail = _fetch_budget_policies(account_host, account_id, headers)
    if detail:
        return "FAIL", detail
    if not policies:
        return (
            "FAIL",
            "no budget policies exist on the account — set the "
            "workspace/warehouse budget caps BEFORE the first query",
        )
    workspace_id = os.getenv("DATABRICKS_PILOT_WORKSPACE_ID", "")
    applicable = [
        p
        for p in policies
        if isinstance(p, dict)
        and (
            not p.get("binding_workspace_ids") or workspace_id in p.get("binding_workspace_ids", [])
        )
    ]
    if not applicable:
        return (
            "FAIL",
            f"budget policies exist ({len(policies)}) but none applies to the "
            "pilot workspace (bindings target other workspaces) — bind one "
            "account-wide or to DATABRICKS_PILOT_WORKSPACE_ID",
        )
    names = [p.get("policy_name", "") for p in applicable if p.get("policy_name")]
    label = ", ".join(names[:5]) + ("…" if len(names) > 5 else "")
    return "PASS", f"{len(applicable)} policy(s): {label}"


def _probe_budgets() -> str:
    status, detail = budgets_probe_result()
    _report("budgets", status, detail)
    return status


_PROBES = {
    "databricks": _probe_databricks,
    "warehouse": _probe_warehouse,
    "aws": _probe_aws,
    "dlt": _probe_dlt,
    "budgets": _probe_budgets,
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "probes",
        nargs="*",
        choices=list(_PROBE_ORDER),
        help="Surfaces to probe (default: all)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat SKIP as a failure (post-flight / CI mode)",
    )
    parser.add_argument(
        "--require-budgets",
        action="store_true",
        help="Exit 1 unless the budgets probe PASSED — the first-query guardrail",
    )
    args = parser.parse_args()
    targets = args.probes or list(_PROBE_ORDER)
    statuses = {name: _PROBES[name]() for name in targets}
    failed = any(status == "FAIL" for status in statuses.values())
    if args.strict:
        failed = failed or any(status == "SKIP" for status in statuses.values())
    if args.require_budgets and statuses.get("budgets", "SKIP") not in (
        "PASS",
        "RESCOPE",
    ):
        failed = True
        print(
            "budget caps NOT verified — set the workspace/warehouse budget "
            "caps BEFORE the first query (PASS requires real caps on a "
            "paid account; RESCOPE is the declared free-edition re-scope)"
        )
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
