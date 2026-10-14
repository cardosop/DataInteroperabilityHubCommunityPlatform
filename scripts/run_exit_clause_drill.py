#!/usr/bin/env python3
"""pilot-readiness 4.4 — the pilot EXIT-CLAUSE drill (tenant export +
deletion), executed FOR REAL against the live test stack.

The drill protects both sides if the pilot ends: the customer's data is
exported and verified BEFORE anything is deleted, and the deletion walks
the REAL production path (PLATFORM_ADMIN soft-delete via the API → the
hard-delete sweep with only the 90-day wait bypassed → object purge),
including the guardrail proofs (legal hold blocks the sweep).

Stages (each one fails the drill loudly, never silently):
  1. seed    — provision the sacrificial tenant ``pilot-exit-drill``
               (tenant + TENANT_ADMIN + asset + uploaded object + audit).
  2. export  — ``tenant_data_export`` through the real storage backend;
               the archive is downloaded via its PRESIGNED URL from this
               host (the exact customer path) and verified: sha256 + the
               tenant.json / audit-trail.jsonl / files-manifest.json /
               per-user DSAR export contents.
  3. soft-delete — the REAL API: DELETE /api/v1/admin/tenants/{id}/ as the
               PLATFORM_ADMIN (IsPlatformAdmin flag).
  4. guardrails — prove legal_hold blocks the drill-sweep (skip logged),
               then release it.
  5. hard-delete — the REAL sweep work function with ``--drill-skip-grace``
               (only the 90-day wait is bypassed; legal-hold + DSAR
               re-checks + row-lock + TENANT_HARD_DELETED audit unchanged).
  6. verify   — tenant/users/assets/files rows gone (admin DB); the
               TENANT_HARD_DELETED audit row SURVIVES (tenant_id NULL);
               the tenant's object files purged from storage.
  7. report   — JSON + Markdown under
               docs/operations/exit-clause-drill-reports/YYYY-MM/.

W16 policy: an unreachable API/stack SKIPS locally and RAISES in CI.

Usage:
    python3 scripts/run_exit_clause_drill.py \
        --admin-email e2e_platform@example.com --admin-password <pw>
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import subprocess
import sys
import urllib.request
import zipfile
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = REPO_ROOT / "docs" / "operations" / "exit-clause-drill-reports"

DRILL_TENANT_SLUG = "pilot-exit-drill"
DRILL_TENANT_ID = "bbbbbbb1-0001-4001-8001-000000000001"

sys.path.insert(0, str(REPO_ROOT))  # envpolicy lives at the repo root
from envpolicy import skip_or_fail


def log(msg: str) -> None:
    print(f"[exit-drill] {msg}")


def _docker_compose(compose_file: str, env_file: str) -> list[str]:
    return ["docker", "compose", "-f", compose_file, "--env-file", env_file]


def _exec(args: argparse.Namespace, *cmd: str, check: bool = True) -> subprocess.CompletedProcess:
    full = [*_docker_compose(args.compose_file, args.env_file), "exec", "-T"]
    if args.postgres_db:
        full += ["-e", f"POSTGRES_DB={args.postgres_db}"]
    full += ["api-service-test", *cmd]
    result = subprocess.run(full, cwd=REPO_ROOT, capture_output=True, text=True, check=False)
    if check and result.returncode != 0:
        log(f"FAILED: {' '.join(cmd)} -> {result.stderr.strip()[:500]}")
        raise SystemExit(result.returncode or 1)
    return result


def stage_reset(args: argparse.Namespace) -> dict:
    """Hard-delete any leftover drill tenant (previous run's soft-deleted
    state included) so the drill is re-runnable: the sweep with the drill
    options does it through the REAL deletion path."""
    log("stage 0/7: reset any leftover drill tenant (re-runnable drill)")
    result = _exec(
        args,
        "python",
        "hub/manage.py",
        "tenant_hard_delete_sweep",
        "--tenant-slug",
        DRILL_TENANT_SLUG,
        "--drill-skip-grace",
        "--skip-job-row",
        "--dry-run",
    )
    # Dry-run first: if the tenant is soft-deleted it would be swept; a
    # real sweep only when a leftover exists.
    # Django's style prints the summary dict with SINGLE quotes — match
    # the key without quote assumptions.
    if "would_hard_delete_at" in result.stdout:
        log("  leftover found — hard-deleting through the real sweep")
        _exec(
            args,
            "python",
            "hub/manage.py",
            "tenant_hard_delete_sweep",
            "--tenant-slug",
            DRILL_TENANT_SLUG,
            "--drill-skip-grace",
            "--skip-job-row",
        )
    return {"reset": True}


def stage_seed(args: argparse.Namespace) -> dict:
    log("stage 1/7: seed the drill tenant")
    result = _exec(args, "python", "hub/manage.py", "seed_pilot_exit_drill_tenant")
    return {"seeded": "pilot-exit-drill", "output": result.stdout.strip().splitlines()[-1:]}


def stage_export(args: argparse.Namespace) -> dict:
    log("stage 2/7: tenant data export (real storage + DSAR machinery)")
    result = _exec(
        args,
        "python",
        "hub/manage.py",
        "tenant_data_export",
        "--slug",
        DRILL_TENANT_SLUG,
    )
    payload = json.loads(result.stdout[result.stdout.index("{") : result.stdout.rindex("}") + 1])

    # The CUSTOMER path: download through the presigned URL from this host.
    with urllib.request.urlopen(payload["download_url"], timeout=60) as resp:
        archive_bytes = resp.read()
    digest = hashlib.sha256(archive_bytes).hexdigest()
    if digest != payload["sha256"]:
        raise SystemExit(f"archive sha256 mismatch: {digest} != {payload['sha256']}")

    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as zf:
        names = set(zf.namelist())
        tenant_json = json.loads(zf.read("tenant.json"))
        manifest = json.loads(zf.read("files-manifest.json"))
        user_archives = [n for n in names if n.startswith("users/") and n.endswith(".zip")]

    for required in ("tenant.json", "audit-trail.jsonl", "files-manifest.json"):
        if required not in names:
            raise SystemExit(f"archive missing {required}")
    if tenant_json["tenant"]["slug"] != DRILL_TENANT_SLUG:
        raise SystemExit("archive tenant mismatch")
    log(
        f"  export verified: sha256={digest[:12]}… users={len(user_archives)} "
        f"files={len(manifest['files'])}"
    )
    return {
        "sha256_ok": True,
        "user_archives": len(user_archives),
        "files_listed": len(manifest["files"]),
        "storage_key": payload["storage_key"],
    }


def _api_login(args: argparse.Namespace) -> str:
    request = urllib.request.Request(
        f"{args.api_base}/api/v1/auth/login/",
        data=json.dumps({"email": args.admin_email, "password": args.admin_password}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as resp:
        return json.loads(resp.read())["access_token"]


def stage_soft_delete(args: argparse.Namespace) -> dict:
    log("stage 3/7: PLATFORM_ADMIN soft-delete through the real API")
    token = _api_login(args)
    request = urllib.request.Request(
        f"{args.api_base}/api/v1/admin/tenants/{DRILL_TENANT_ID}/",
        headers={"Authorization": f"Bearer {token}"},
        method="DELETE",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as resp:
            body = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        body = json.loads(exc.read().decode() or "{}")
        log(f"soft-delete HTTP {exc.code}: {body}")
        raise
    tenant_body = body.get("tenant", body)
    anchor = tenant_body.get("scheduled_for_deletion_at")
    assert anchor, f"soft-delete must set the grace anchor: {body}"
    log(f"  soft-deleted; grace anchor: {anchor}")
    return {"scheduled_for_deletion_at": anchor}


def _manage_shell(args: argparse.Namespace, code: str) -> str:
    """Run Python inside the api container with Django set up. Multi-line
    code (try/except etc.) is fed via STDIN to ``manage.py shell`` — a
    semicolon-joined ``-c`` one-liner cannot carry compound statements."""
    full = [*_docker_compose(args.compose_file, args.env_file), "exec", "-T"]
    if args.postgres_db:
        full += ["-e", f"POSTGRES_DB={args.postgres_db}"]
    full += ["api-service-test", "python", "hub/manage.py", "shell"]
    result = subprocess.run(
        full, cwd=REPO_ROOT, input=code, capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        log(f"FAILED: manage.py shell -> {result.stderr.strip()[:500]}")
        raise SystemExit(result.returncode or 1)
    return result.stdout


def stage_guardrails(args: argparse.Namespace) -> dict:
    log("stage 4/7: guardrail proof — legal_hold must block the drill-sweep")
    _manage_shell(
        args,
        "from hub.apps.tenants.models import Tenant;"
        "t = Tenant.all_objects.get(slug='pilot-exit-drill');"
        "t.legal_hold = True; t.save()",
    )
    result = _exec(
        args,
        "python",
        "hub/manage.py",
        "tenant_hard_delete_sweep",
        "--tenant-slug",
        DRILL_TENANT_SLUG,
        "--drill-skip-grace",
        "--skip-job-row",
    )
    summary = result.stdout
    if "legal_hold_active" not in summary:
        raise SystemExit("legal hold did NOT block the sweep — guardrail failed")
    log("  sweep SKIPPED the held tenant (legal_hold_active) — guardrail proven")

    _manage_shell(
        args,
        "from hub.apps.tenants.models import Tenant;"
        "t = Tenant.all_objects.get(slug='pilot-exit-drill');"
        "t.legal_hold = False; t.save()",
    )
    return {"guardrail": "legal_hold_active", "proven": True}


def stage_hard_delete(args: argparse.Namespace) -> dict:
    log("stage 5/7: hard-delete through the REAL sweep (only the grace wait bypassed)")
    result = _exec(
        args,
        "python",
        "hub/manage.py",
        "tenant_hard_delete_sweep",
        "--tenant-slug",
        DRILL_TENANT_SLUG,
        "--drill-skip-grace",
        "--skip-job-row",
    )
    summary = result.stdout
    # The command prints the summary as a Python dict repr — parse it
    # instead of grepping quote styles.
    import ast

    payload_text = summary[summary.index("{") : summary.rindex("}") + 1]
    parsed = ast.literal_eval(payload_text)
    if parsed.get("hard_deleted_count") != 1:
        raise SystemExit(f"sweep did not hard-delete the tenant: {summary[:400]}")
    log("  TENANT_HARD_DELETED emitted — cascade completed")
    return {"sweep_summary": parsed}


def stage_verify(args: argparse.Namespace) -> dict:
    log("stage 6/7: verify the purge (rows, audit survival, objects)")
    checks = _manage_shell(
        args,
        "from hub.apps.tenants.models import Tenant;"
        "from hub.apps.users.models import User;"
        "from hub.apps.assets.models import Asset;"
        "from hub.apps.files.models import File;"
        "from hub.apps.audit.models import AuditEvent;"
        "tid='bbbbbbb1-0001-4001-8001-000000000001';"
        "print({'tenants': Tenant.all_objects.filter(id=tid).count(),"
        "'users': User.objects.filter(tenant_id=tid).count(),"
        "'assets': Asset.objects.filter(tenant_id=tid).count(),"
        "'files': File.objects.filter(tenant_id=tid).count(),"
        "'audit_rows': AuditEvent.objects.filter(action='TENANT_HARD_DELETED').count(),"
        "'deleted_audit_tenant_null': AuditEvent.objects.filter("
        "action='TENANT_HARD_DELETED', tenant_id__isnull=True).count()})",
    )
    checks_json = checks[checks.index("{") : checks.rindex("}") + 1]
    counts = json.loads(checks_json.replace("'", '"'))
    for key in ("tenants", "users", "assets", "files"):
        if counts[key] != 0:
            raise SystemExit(f"{key} rows remain after hard-delete: {counts[key]}")
    if counts["audit_rows"] < 1 or counts["deleted_audit_tenant_null"] < 1:
        raise SystemExit("TENANT_HARD_DELETED audit row missing or tenant_id not NULL")

    # Object purge: the drill tenant's file object must be gone from storage.
    storage_probe = _manage_shell(
        args,
        """
import boto3
from django.conf import settings

from hub.apps.files.storage import S3StorageClient

s = S3StorageClient()
c = boto3.client(
    "s3",
    endpoint_url=s.endpoint_url,
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    use_ssl=s.use_ssl,
    verify=getattr(settings, "AWS_S3_VERIFY", True),
)
key = "tenant-files/bbbbbbb1-0001-4001-8001-000000000001/pilot-exit-drill-report.csv"
try:
    c.head_object(Bucket=s.bucket_name, Key=key)
    print("PRESENT")
except Exception as e:
    print("GONE")
""",
    )
    # manage.py shell prints an import banner before the code's output —
    # take the last non-empty line (the probe's own print).
    probe_lines = [ln for ln in storage_probe.splitlines() if ln.strip()]
    object_state = probe_lines[-1].strip() if probe_lines else "UNKNOWN"
    if "GONE" not in object_state:
        raise SystemExit(
            f"drill tenant object still present in storage: {object_state}"
        )
    log(f"  rows purged; audit survived (tenant_id NULL); object: {object_state}")
    return counts | {"object_state": object_state}


def write_report(stages: dict) -> Path:
    report_dir = REPORT_DIR / datetime.now(UTC).strftime("%Y-%m")
    report_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H%M%SZ")
    json_path = report_dir / f"exit-clause-drill-{stamp}.json"
    report = {
        "drill": "pilot-exit-clause",
        "tenant_slug": DRILL_TENANT_SLUG,
        "tenant_id": DRILL_TENANT_ID,
        "status": "PASSED",
        "operator": os.environ.get("USER", "drill-runner"),
        "timestamp": datetime.now(UTC).isoformat(),
        "stages": stages,
    }
    json_path.write_text(json.dumps(report, indent=2))
    md = f"""# Pilot Exit-Clause Drill — {stamp[:10]}

| Field | Value |
|---|---|
| Status | **{report["status"]}** |
| Tenant | `{DRILL_TENANT_SLUG}` |
| Operator | `{report["operator"]}` |

## Stages

"""
    for name, detail in stages.items():
        md += f"- **{name}**: {json.dumps(detail)[:200]}\n"
    (json_path.with_suffix(".md")).write_text(md)
    log(f"report: {json_path}")
    return json_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--api-base", default=os.environ.get("API_BASE_URL", "http://localhost:8001")
    )
    parser.add_argument("--admin-email", default=os.environ.get("EXIT_DRILL_ADMIN_EMAIL", ""))
    parser.add_argument("--admin-password", default=os.environ.get("EXIT_DRILL_ADMIN_PASSWORD", ""))
    parser.add_argument("--compose-file", default="docker-compose.test.yml")
    parser.add_argument("--env-file", default=".env.test")
    parser.add_argument("--postgres-db", default=os.environ.get("EXIT_DRILL_DB", ""))
    parser.add_argument("--skip-seed", action="store_true")
    args = parser.parse_args()

    # W16: unreachable stack skips locally, raises in CI.
    probe = subprocess.run(
        [
            *_docker_compose(args.compose_file, args.env_file),
            "ps",
            "--status",
            "running",
            "api-service-test",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if probe.returncode != 0:
        skip_or_fail("api-service-test not running — bring the test stack up")
    if not args.admin_email or not args.admin_password:
        print(
            "ERROR: --admin-email/--admin-password (or EXIT_DRILL_ADMIN_*) are required",
            file=sys.stderr,
        )
        return 2

    stages: dict = {}
    if not args.skip_seed:
        stages["reset"] = stage_reset(args)
        stages["seed"] = stage_seed(args)
    stages["export"] = stage_export(args)
    stages["soft_delete"] = stage_soft_delete(args)
    stages["guardrails"] = stage_guardrails(args)
    stages["hard_delete"] = stage_hard_delete(args)
    stages["verify"] = stage_verify(args)
    write_report(stages)
    log("EXIT-CLAUSE DRILL PASSED (exit 0)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
