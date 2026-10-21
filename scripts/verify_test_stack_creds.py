#!/usr/bin/env python3
"""
pilot-readiness 1.5 — test-stack credential mismatch detector.

Detects the operational landmine the 1.3/1.4 rehearsals hit: the running
MinIO volume still accepts a credential pair the env files no longer
carry, so the next bring-up breaks storage silently (healthchecks stay
green while every S3 upload 403s). Also verifies the CKAN token against
the live instance and the Fuseki password convergence between
``.env.test`` and the running api/semantic containers.

Checks (each reported PASS / FAIL / SKIP):

- ``minio-file``   — each env file's internal consistency (its
  MINIO_ROOT_* pair MUST equal its AWS_* pair; the 1.4 finding);
- ``minio-volume`` — which pair the LIVE volume accepts vs the
  ``.env.test`` pair (the re-init source of truth);
- ``ckan-token``   — the ``.env.test`` token against the live CKAN
  (auth-required ``api_token_list``; a public action would be vacuous);
- ``fuseki``       — ``.env.test`` FUSEKI_ADMIN_PASSWORD vs the running
  api-service-test/semantic-service-test baked env (confirm, don't
  repeat — pilot-readiness 1.2).

No secret value is EVER printed — reports name files, containers, and
statuses only. Exit 0 = everything consistent (or unreachable-skips),
1 = at least one FAIL. ``--strict`` turns unreachable surfaces into
FAILs (post-flight mode for ``make test-stack-reinit``).

Host-side defaults: MinIO ``http://localhost:9010`` (override with
``--minio-endpoint`` or ``MINIO_TEST_ENDPOINT``), CKAN
``http://localhost:5100`` (``CKAN_TEST_BASE_URL``). In-container runs:
point both at the compose-internal hosts.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_DEFAULT_ENV_FILES = [".env.test", ".env"]
_ENV_KEYS = (
    "MINIO_ROOT_USER",
    "MINIO_ROOT_PASSWORD",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "CKAN_TEST_API_KEY",
    "FUSEKI_ADMIN_PASSWORD",
)
_FUSEKI_CONTAINERS = ["hub-test-api", "hub-test-semantic"]


def parse_env_file(path: Path) -> dict[str, str]:
    """The credential entries of an env file (never printed)."""
    if not path.is_file():
        return {}
    parsed: dict[str, str] = {}
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        for key in _ENV_KEYS:
            if line.startswith(f"{key}="):
                parsed[key] = line.split("=", 1)[1]
                break
    return parsed


def minio_internal_violations(parsed: dict[str, str]) -> list[str]:
    """The file's own AWS_* pair must equal its MINIO_ROOT_* pair."""
    violations = []
    if (
        "MINIO_ROOT_USER" in parsed
        and "AWS_ACCESS_KEY_ID" in parsed
        and parsed["MINIO_ROOT_USER"] != parsed["AWS_ACCESS_KEY_ID"]
    ):
        violations.append("MINIO_ROOT_USER != AWS_ACCESS_KEY_ID")
    if (
        "MINIO_ROOT_PASSWORD" in parsed
        and "AWS_SECRET_ACCESS_KEY" in parsed
        and parsed["MINIO_ROOT_PASSWORD"] != parsed["AWS_SECRET_ACCESS_KEY"]
    ):
        violations.append("MINIO_ROOT_PASSWORD != AWS_SECRET_ACCESS_KEY")
    return violations


def probe_minio_pair(
    endpoint: str, user: str, password: str, timeout: float = 10.0
) -> bool | None:
    """True when the live MinIO accepts the pair; None when unreachable."""
    try:
        import boto3
    except ImportError:
        return None
    try:
        client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=user,
            aws_secret_access_key=password,
            region_name="us-east-1",
            config=boto3.session.Config(
                connect_timeout=timeout, read_timeout=timeout, retries={"max_attempts": 1}
            ),
        )
        client.list_buckets()
    except Exception as exc:  # noqa: BLE001 — probe; never leak the pair
        name = type(exc).__name__
        if name in {"ConnectTimeoutError", "EndpointConnectionError", "ConnectionError"}:
            return None
        return False
    else:
        return True


def classify_minio_volume(
    accepted_pair: tuple[str, str] | None,
    env_pair: tuple[str, str],
    rejected_all: bool = False,
    strict: bool = False,
) -> tuple[str, str]:
    """Verdict: does the live volume accept the env pair?"""
    if accepted_pair is None:
        if rejected_all:
            return (
                "FAIL",
                "volume rejects every candidate pair — it holds foreign creds; "
                "re-init via `make test-stack-reinit`",
            )
        if strict:
            return ("FAIL", "MinIO unreachable — cannot verify")
        return ("SKIP", "MinIO unreachable")
    if accepted_pair == env_pair:
        return ("PASS", "volume accepts the .env.test pair")
    return (
        "FAIL",
        "volume accepts a DIFFERENT pair — re-init via `make test-stack-reinit`",
    )


def fuseki_container_passwords(containers: list[str]) -> dict[str, str]:
    """Baked FUSEKI_ADMIN_PASSWORD of each running container (no output)."""
    passwords: dict[str, str] = {}
    for name in containers:
        out = subprocess.run(
            ["docker", "exec", name, "printenv", "FUSEKI_ADMIN_PASSWORD"],
            capture_output=True,
            text=True,
            check=False,
        )
        if out.returncode == 0 and out.stdout.strip():
            passwords[name] = out.stdout.strip()
    return passwords


def classify_fuseki(
    env_password: str, container_passwords: dict[str, str]
) -> tuple[str, str]:
    """Verdict: converged = every running container bakes the env password."""
    if not container_passwords:
        return ("SKIP", "containers not running")
    diverged = [n for n, p in container_passwords.items() if p != env_password]
    if diverged:
        return (
            "FAIL",
            f"diverged containers: {', '.join(sorted(diverged))} "
            "(recreate them together with --env-file .env.test)",
        )
    return ("PASS", f"converged across {len(container_passwords)} containers")


def report(surface: str, target: str, status: str, detail: str = "") -> None:
    line = f"{surface:<12} {target:<10} {status:<5}"
    if detail:
        line += f" ({detail})"
    print(line)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", action="append", default=None,
                        help="env file(s) to verify (default: .env.test .env)")
    parser.add_argument("--minio-endpoint",
                        default=os.getenv("MINIO_TEST_ENDPOINT", "http://localhost:9010"))
    parser.add_argument("--strict", action="store_true",
                        help="treat unreachable surfaces as FAIL (post-flight)")
    args = parser.parse_args(argv)

    env_files = [Path(p) for p in (args.env_file or _DEFAULT_ENV_FILES)]
    parsed_files = {str(p): parse_env_file(p) for p in env_files}

    failed = False

    # 1. Internal consistency per env file (pure — works with the stack down).
    for name, parsed in parsed_files.items():
        if not parsed:
            report("minio-file", name, "SKIP", "file not found")
            continue
        violations = minio_internal_violations(parsed)
        if violations:
            report("minio-file", name, "FAIL", "; ".join(violations))
            failed = True
        else:
            report("minio-file", name, "PASS", "AWS_* == MINIO_ROOT_*")

    # 2. Live volume acceptance vs the primary env file's pair (.env.test
    #    by default; the first --env-file when .env.test is not among them).
    primary_name = ".env.test" if ".env.test" in parsed_files else next(iter(parsed_files))
    env_test = parsed_files.get(primary_name)
    if not env_test:
        report("minio-volume", primary_name, "SKIP", "no env file found")
    else:
        env_pair = (env_test["MINIO_ROOT_USER"], env_test["MINIO_ROOT_PASSWORD"])
        candidates = [env_pair]
        for parsed in parsed_files.values():
            pair = (parsed.get("MINIO_ROOT_USER"), parsed.get("MINIO_ROOT_PASSWORD"))
            if all(pair) and pair not in candidates:
                candidates.append(pair)
        accepted = None
        rejected_all = False
        for candidate in candidates:
            result = probe_minio_pair(args.minio_endpoint, *candidate)
            if result is True:
                accepted = candidate
                break
            if result is False:
                rejected_all = True  # volume answered, but rejected this pair
        status, detail = classify_minio_volume(
            accepted, env_pair, rejected_all=rejected_all, strict=args.strict
        )
        report("minio-volume", primary_name, status, detail)
        if status == "FAIL":
            failed = True

    # 3. CKAN token (reuses the auth-required probe from verify_connector_creds).
    if env_test and env_test.get("CKAN_TEST_API_KEY"):
        spec = importlib.util.spec_from_file_location(
            "verify_connector_creds", _SCRIPT_DIR / "verify_connector_creds.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        status, detail = module.ckan_probe_result(
            env_test["CKAN_TEST_API_KEY"],
            base=os.getenv("CKAN_TEST_BASE_URL", "http://localhost:5100"),
        )
        if status == "SKIP" and args.strict:
            status, detail = "FAIL", "CKAN unreachable"
        report("ckan-token", ".env.test", status, detail)
        if status == "FAIL":
            failed = True
    else:
        report("ckan-token", ".env.test", "SKIP", "CKAN_TEST_API_KEY not set")

    # 4. Fuseki convergence (confirm, don't repeat).
    if env_test and env_test.get("FUSEKI_ADMIN_PASSWORD"):
        status, detail = classify_fuseki(
            env_test["FUSEKI_ADMIN_PASSWORD"],
            fuseki_container_passwords(_FUSEKI_CONTAINERS),
        )
        if status == "SKIP" and args.strict:
            status, detail = "FAIL", "containers not running"
        report("fuseki", ".env.test", status, detail)
        if status == "FAIL":
            failed = True
    else:
        report("fuseki", ".env.test", "SKIP", "FUSEKI_ADMIN_PASSWORD not set")

    print("verify_test_stack_creds:", "FAIL" if failed else "OK")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
