#!/usr/bin/env python3
"""The Week-1 scale load test (pilot-readiness 4.4).

Runs the k6 critical-journeys suite at the scale recorded in
tests/load/week1_scale.json against the target API, then compares the
measured p95s against the committed performance baseline
(tests/load/performance_baseline.json) via scripts/compare_k6_baseline.py
and writes the load-test report under docs/operations/load-test-reports/.

Execution:
  * k6 binary on PATH, or
  * the pinned grafana/k6:0.51.0 image (the same version the CI gate uses)
    when docker is available — host.docker.internal is wired so a container
    k6 reaches an API on the host loopback.

Scale governance: until U records the company's Week-1 numbers
(scale.confirmed=false, PILOT_READINESS_PLAN 1.7), the run proceeds at the
rehearsal scale with a WARN banner; --strict refuses, so the go/no-go gate
cannot silently bless unconfirmed scale.

Usage:
    python3 scripts/run_week1_load_test.py --api-base http://localhost:8001 \
        --auth-email pilot@example.com --auth-password <pw> [--strict]
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCALE_FILE = REPO_ROOT / "tests" / "load" / "week1_scale.json"
K6_SCRIPT = REPO_ROOT / "tests" / "load" / "critical_journeys.k6.js"
COMPARE = REPO_ROOT / "scripts" / "compare_k6_baseline.py"
REPORT_DIR = REPO_ROOT / "docs" / "operations" / "load-test-reports"
# The CI-pinned k6 version; overridable (K6_IMAGE) for environments where
# only a locally cached image is available — the version used is recorded in
# the run banner.
K6_IMAGE = os.environ.get("K6_IMAGE", "grafana/k6:0.51.0")


def load_scale(path: Path = SCALE_FILE) -> dict:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot read scale file {path}: {exc}", file=sys.stderr)
        sys.exit(2)


def scale_env(scale: dict, steady_minutes: int | None = None) -> dict[str, str]:
    k6 = scale["k6"]
    return {
        "K6_START_RATE": str(k6["start_rate"]),
        "K6_STEADY_RATE": str(k6["steady_rate"]),
        "K6_PEAK_RATE": str(k6["peak_rate"]),
        "K6_COOLDOWN_RATE": str(k6["cooldown_rate"]),
        "K6_STEADY_MINUTES": str(
            steady_minutes if steady_minutes is not None else k6["steady_minutes"]
        ),
        "K6_MAX_VUS": str(k6["max_vus"]),
    }


def run_k6(
    api_base: str,
    auth_email: str,
    auth_password: str,
    scale: dict,
    steady_minutes: int | None = None,
) -> Path:
    """Run k6, return the summary-export path. k6 threshold violations do
    NOT abort here — the comparator is the arbiter (the CI gate's contract:
    `k6 run ... || true`, then compare)."""
    with tempfile.TemporaryDirectory() as td:
        summary = Path(td) / "k6-summary.json"
        env = {
            **os.environ,
            "BASE_URL": api_base,
            "AUTH_EMAIL": auth_email,
            "AUTH_PASSWORD": auth_password,
            **scale_env(scale, steady_minutes),
        }
        if shutil.which("k6"):
            cmd = ["k6", "run", "--summary-export", str(summary), str(K6_SCRIPT)]
            result = subprocess.run(cmd, cwd=REPO_ROOT, env=env, check=False)
        elif shutil.which("docker"):
            # A containerized k6 cannot reach a loopback API on the host —
            # rewrite localhost/127.0.0.1 to the host gateway (the k6 script
            # reads BASE_URL verbatim).
            container_api = api_base.replace("localhost", "host.docker.internal").replace(
                "127.0.0.1", "host.docker.internal"
            )
            cmd = [
                "docker",
                "run",
                "--rm",
                "-i",
                # Run as the invoking user so the summary file can be
                # written into the mounted repo (the k6 image's default
                # user cannot write /app).
                "--user",
                f"{os.getuid()}:{os.getgid()}",
                "-v",
                f"{REPO_ROOT}:/app",
                "-w",
                "/app",
                "--add-host",
                "host.docker.internal:host-gateway",
                "-e",
                f"BASE_URL={container_api}",
                "-e",
                f"AUTH_EMAIL={auth_email}",
                "-e",
                f"AUTH_PASSWORD={auth_password}",
            ]
            for key, value in scale_env(scale, steady_minutes).items():
                cmd += ["-e", f"{key}={value}"]
            # k6 runs INSIDE the container: the script path must be the
            # container-side path (/app mount), not the host path.
            container_script = "/app/" + str(K6_SCRIPT.relative_to(REPO_ROOT))
            cmd += [
                K6_IMAGE,
                "run",
                "--summary-export",
                "/app/k6-summary-docker.json",
                container_script,
            ]
            result = subprocess.run(cmd, cwd=REPO_ROOT, check=False)
            summary = REPO_ROOT / "k6-summary-docker.json"
            if not summary.exists():
                print("ERROR: k6 container produced no summary file", file=sys.stderr)
                sys.exit(2)
        else:
            print(
                "ERROR: no k6 binary and no docker — install k6 or run inside "
                "the dev stack",
                file=sys.stderr,
            )
            sys.exit(2)

        print(
            f"[load-test] k6 exited {result.returncode} "
            "(thresholds arbitrated by the comparator)"
        )
        if not summary.exists():
            print("ERROR: k6 produced no summary-export", file=sys.stderr)
            sys.exit(2)
        return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--api-base", default=os.environ.get("BASE_URL", "http://localhost:8001"))
    parser.add_argument("--auth-email", default=os.environ.get("AUTH_EMAIL", ""))
    parser.add_argument("--auth-password", default=os.environ.get("AUTH_PASSWORD", ""))
    parser.add_argument("--label", default="week1")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument(
        "--steady-minutes",
        type=int,
        default=None,
        help="rehearsal override for the steady-state stage length "
        "(the full Week-1 scale is the committed file's value)",
    )
    args = parser.parse_args()

    scale = load_scale()
    if scale.get("confirmed") is not True:
        banner = (
            "scale not confirmed with U (PILOT_READINESS_PLAN 1.7) — "
            "running at the REHEARSAL scale"
        )
        if args.strict:
            print(f"ERROR: {banner} — --strict refuses unconfirmed scale", file=sys.stderr)
            return 1
        print(f"[load-test] WARN: {banner}")

    if not args.auth_email or not args.auth_password:
        print(
            "ERROR: --auth-email/--auth-password (or AUTH_EMAIL/AUTH_PASSWORD) "
            "are required",
            file=sys.stderr,
        )
        return 2

    if args.steady_minutes is not None:
        print(
            f"[load-test] WARN: rehearsal steady-stage override: "
            f"{args.steady_minutes}m (committed scale: "
            f"{scale['k6']['steady_minutes']}m)"
        )
    print(
        f"[load-test] scale: users={scale['users']} "
        f"concurrent_sessions={scale['concurrent_sessions']} "
        f"k6={scale['k6']} image={K6_IMAGE}"
    )
    summary = run_k6(
        args.api_base,
        args.auth_email,
        args.auth_password,
        scale,
        args.steady_minutes,
    )

    result = subprocess.run(
        [
            sys.executable,
            str(COMPARE),
            str(summary),
            "--mode",
            "blocking",
            "--report-dir",
            str(REPORT_DIR),
            "--label",
            args.label,
        ],
        cwd=REPO_ROOT,
        check=False,
    )
    # The docker path writes the summary into the repo root — keep it as
    # drill evidence next to the report (forensics), not as repo litter.
    docker_summary = REPO_ROOT / "k6-summary-docker.json"
    if docker_summary.exists():
        import datetime as _dt

        stamp = _dt.datetime.now(_dt.UTC).strftime("%Y-%m-%dT%H%M%SZ")
        evidence = (
            REPORT_DIR / stamp[:7] / f"k6-summary-{stamp}.json"
        )
        evidence.parent.mkdir(parents=True, exist_ok=True)
        docker_summary.replace(evidence)
        print(f"[load-test] k6 summary kept as evidence: {evidence}")
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
