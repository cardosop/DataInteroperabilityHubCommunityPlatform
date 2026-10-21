#!/usr/bin/env python3
"""P2-6 (close-oss-release-conditions, G5) — affected-image remediation
executor.

The P0-14 audit (docs/operations/image-context-audit-2026-10-19.md)
found every tag published BEFORE the P1 rotations bakes credential
material (the tracked ``.claude/settings.json`` live bearer token,
baked by every whole-context ``COPY . .`` image, plus the ``buildcache``
cache-layer tags). P2-6 remediates AFTER the rotations land: rebuild
-and-republish (or delete) every affected tag, with evidence recorded.

One-shot execution tool (NOT in the always-on battery):

  --plan     (default) — enumerate the REAL GHCR version state for
             every published package and print the disposition plan
             WITHOUT mutating anything (an enumeration failure marks
             the plan INCOMPLETE — exit 2 — never a silent empty
             plan);
  --execute  — gated on EVERY precondition independently:
               1. the rotation gate (the real GATE-65 —
                  scripts/check_history_rotation_map.py) GREEN;
               2. ``--window-close <RFC3339>`` — the rotation
                  -completion timestamp from the P1 close record
                  (versions created before it are affected);
               3. ``--confirm-delete`` — explicit confirmation;
               4. the replacement invariant — a pre-window tag of an
                  ACTIVE package is deleted only when a post-window
                  version of that package already exists (deleting the
                  old tags without a rebuilt successor would leave
                  deployments without a pullable image).
             Then deletes every affected version via the REAL GitHub
             API (``gh api --method DELETE``).

Disposition rules (pinned pure functions):

  - buildcache tag → DELETE (a BuildKit cache artifact, never a
    deployment target; mode=max layers retain pre-fix content);
  - deleted-lane package (inference-service — the P2-6 delete-or-wire
    disposition) → DELETE every version (no rebuild is possible: the
    lane no longer exists);
  - active package, version created BEFORE the window close →
    REBUILD_THEN_DELETE until a post-window replacement exists, then
    DELETE;
  - version created AT/AFTER the window close → KEEP.

The rebuild itself is the deploy workflow's job (its P0-14 audit gate
refuses credential-bearing contexts before any push). The runbook is
docs/runbooks/image-remediation.md. Enumeration needs a gh token with
``read:packages``; deletion needs ``delete:packages``.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

_ROOT = Path(__file__).resolve().parent.parent
_GATE65 = _ROOT / "scripts/check_history_rotation_map.py"

# The P2-6 delete-or-wire disposition: the dormant inference-service
# lane is DELETED (no Dockerfile since inception — the deploy workflow
# guard always skipped it; the helm chart shipped disabled
# (enabled: false, replicaCount 0) behind an image that could never be
# built; zero push consumers). Wiring it would be Phase 114E feature
# work, not remediation. Any published versions of the deleted lane
# must still be deleted — no rebuild is possible. Package identifiers
# are FULL package names (the image name minus the registry owner) —
# the same shape the gh api versions endpoint expects.
DELETED_LANE_PACKAGES: tuple[str, ...] = (
    "datainteroperabilityhub-inference-service",
)

DISPOSITION_DELETE = "DELETE"
DISPOSITION_REBUILD_THEN_DELETE = "REBUILD_THEN_DELETE"
DISPOSITION_KEEP = "KEEP"

_BUILDCACHE = "buildcache"


def _load_audit_tool():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "audit_image_build_contexts",
        Path(__file__).resolve().parent / "audit_image_build_contexts.py",
    )
    assert spec is not None, "audit_image_build_contexts.py must load"
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def inventory_packages(repo_root: Path) -> list[str]:
    """The remediation universe: the deploy workflow's canonical push
    inventory (reused from the P0-14 audit tool — the single source of
    truth) + the deleted-lane packages (their published versions must
    still be deleted). Returns FULL package names — the image name
    minus the registry owner (``datainteroperabilityhub-<service>``),
    the identifier shape the gh api versions endpoint expects."""
    audit = _load_audit_tool()
    workflow = repo_root / ".github/workflows/deploy.yml"
    packages = {
        entry["image"].split("/")[-1]
        for entry in audit.load_inventory(workflow, repo_root)
    }
    return sorted(packages | set(DELETED_LANE_PACKAGES))


def parse_rfc3339(value: str) -> datetime:
    """RFC3339 → aware datetime (the gh API's created_at shape)."""
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def tag_names(version: dict) -> list[str]:
    """The version's registry tags (metadata.container.tags); the
    version name is the fallback."""
    tags = version.get("tags") or []
    if not tags and version.get("name"):
        tags = [version["name"]]
    return list(tags)


def is_buildcache(version: dict) -> bool:
    return any(_BUILDCACHE in tag for tag in tag_names(version))


def disposition_for(
    package: str,
    version: dict,
    window_close: str | None,
    has_post_window: bool,
) -> str:
    """The pinned disposition rules (see module docstring)."""
    if package in DELETED_LANE_PACKAGES:
        return DISPOSITION_DELETE
    if is_buildcache(version):
        return DISPOSITION_DELETE
    if window_close is None or parse_rfc3339(version["created"]) >= parse_rfc3339(
        window_close
    ):
        return DISPOSITION_KEEP
    if not has_post_window:
        return DISPOSITION_REBUILD_THEN_DELETE
    return DISPOSITION_DELETE


def executable_rows(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """Split the plan rows into the API deletion set (DELETE rows) and
    the holds (REBUILD_THEN_DELETE rows — a hold HALTS the run)."""
    deletable = [row for row in rows if row["disposition"] == DISPOSITION_DELETE]
    holds = [
        row for row in rows if row["disposition"] == DISPOSITION_REBUILD_THEN_DELETE
    ]
    return deletable, holds


def rotation_gate_verdict(
    candidates: Path | None = None, mapping: Path | None = None
) -> tuple[bool, list[str]]:
    """Run the REAL GATE-65 (check_history_rotation_map.py). (ok,
    problems): green only when every history-visible credential class
    carries dated dead-value evidence; problems carry the gate's FAIL
    lines (class keys only — never values)."""
    args = [sys.executable, str(_GATE65)]
    if candidates is not None:
        args += ["--candidates", str(candidates)]
    if mapping is not None:
        args += ["--map", str(mapping)]
    result = subprocess.run(
        args, capture_output=True, text=True, check=False, cwd=_ROOT
    )
    if result.returncode not in (0, 1):
        return (
            False,
            [f"rotation gate exited {result.returncode} (fail-closed): "
             f"{(result.stderr or result.stdout).strip()[:300]}"],
        )
    problems = [
        line.strip()
        for line in (result.stdout + "\n" + result.stderr).splitlines()
        if line.strip().startswith("FAIL:")
    ]
    return (result.returncode == 0, problems)


def decide_execution(
    verdict_ok: bool,
    window_close: str | None,
    confirm: bool,
    holds: list[dict],
) -> SimpleNamespace:
    """The execution decision — every precondition is independently
    required; the first missing one REFUSES with its own named reason."""
    if not verdict_ok:
        return SimpleNamespace(
            action="REFUSED_ROTATION_GATE",
            message="destructive actions are blocked while the rotation "
                    "gate (GATE-65) is red",
        )
    if window_close is None:
        return SimpleNamespace(
            action="REFUSED_WINDOW_CLOSE",
            message="--window-close <RFC3339> is required (the rotation"
                    "-completion timestamp from the P1 close record)",
        )
    if not confirm:
        return SimpleNamespace(
            action="REFUSED_CONFIRM",
            message="--confirm-delete is required (the deletions are "
                    "irreversible)",
        )
    if holds:
        return SimpleNamespace(
            action="HOLD_REBUILD",
            message="pre-window tags without a rebuilt successor must not "
                    "be deleted (the replacement invariant) — rebuild via "
                    "the deploy workflow first, then re-run",
        )
    return SimpleNamespace(action="PROCEED", message="")


def enumerate_package(package: str) -> tuple[list[dict], str]:
    """The REAL registry enumeration:
    ``gh api 'user/packages/container/<package>/versions' --paginate``.
    Returns (versions, error) — a failure reports its error (the
    fail-closed shape: empty versions + a non-empty error), never a
    crash and never a silent empty plan."""
    if not shutil.which("gh"):
        return [], "gh CLI not found (fail-closed)"
    result = subprocess.run(
        [
            "gh",
            "api",
            f"user/packages/container/{package}/versions",
            "--paginate",
            "--jq",
            ".[] | {id: .id, name: .name, "
            "tags: (.metadata.container.tags // []), created: .created_at}",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return [], (
            f"gh api failed for package {package!r}: "
            f"{(result.stderr or result.stdout).strip()[:300]}"
        )
    versions: list[dict] = []
    for raw in result.stdout.splitlines():
        stripped = raw.strip()
        if not stripped:
            continue
        try:
            versions.append(json.loads(stripped))
        except json.JSONDecodeError as exc:
            return [], (
                f"unparseable API line for package {package!r}: "
                f"{exc} (line head: {stripped[:80]!r})"
            )
    return versions, ""


def build_plan(
    packages: list[str],
    enumerated: dict[str, tuple[list[dict], str]],
    window_close: str | None,
    verdict_ok: bool,
    verdict_problems: list[str] | None = None,
) -> dict:
    """The pure plan builder: dispositions per enumerated version + the
    execution decision (REFUSED while any precondition is missing)."""
    rows: list[dict] = []
    package_states: list[dict] = []
    for package in packages:
        versions, error = enumerated.get(package, ([], "not enumerated"))
        has_post_window = any(
            not is_buildcache(v)
            and window_close is not None
            and parse_rfc3339(v["created"]) >= parse_rfc3339(window_close)
            for v in versions
        )
        package_rows = []
        for version in versions:
            disposition = disposition_for(
                package, version, window_close, has_post_window
            )
            display = ", ".join(tag_names(version))
            package_rows.append(
                {
                    "package": package,
                    "version_id": version.get("id"),
                    "tag": display,
                    "created": version.get("created", ""),
                    "disposition": disposition,
                }
            )
        rows.extend(package_rows)
        package_states.append(
            {
                "package": package,
                "versions": len(versions),
                "error": error,
                "rows": package_rows,
            }
        )
    deletable, holds = executable_rows(rows)
    execution = decide_execution(
        verdict_ok, window_close, confirm=False, holds=holds
    )
    return {
        "window_close": window_close,
        "verdict_ok": verdict_ok,
        "verdict_problems": verdict_problems or [],
        "packages": package_states,
        "rows": rows,
        "deletable": deletable,
        "holds": holds,
        "execution": execution.action,
    }


def render_record(plan: dict) -> str:
    """The evidence record: the gate verdict, the window close, every
    version's disposition and the execution decision."""
    lines = [
        "# Image Remediation Record — P2-6 (G5)",
        "",
        "Affected-image remediation evidence "
        "(close-oss-release-conditions). Input: "
        "docs/operations/image-context-audit-2026-10-19.md.",
        "",
        "## Rotation gate (GATE-65)",
        "",
    ]
    if plan["verdict_ok"]:
        lines.append("PASSED — every history-visible credential class "
                     "carries dated dead-value evidence.")
    else:
        lines.append("REFUSED — the rotation gate is red:")
        for problem in plan["verdict_problems"]:
            lines.append(f"- {problem}")
    lines += [
        "",
        "## Rotation window close",
        "",
        (
            plan["window_close"]
            or "NOT SET — every published version is pre-rotation "
            "(affected)"
        ),
        "",
        f"## Execution: {plan['execution']}",
        "",
    ]
    for state in plan["packages"]:
        lines += [f"### {state['package']}", ""]
        if state["error"]:
            lines.append(f"ENUMERATION FAILED: {state['error']}")
        elif not state["rows"]:
            lines.append("no published versions")
        else:
            lines += [
                "| Tag | Created | Disposition |",
                "|---|---|---|",
            ]
            for row in state["rows"]:
                lines.append(
                    f"| {row['tag']} | {row['created']} | "
                    f"{row['disposition']} |"
                )
        lines.append("")
    return "\n".join(lines) + "\n"


def _delete_version(package: str, version_id: object) -> str:
    result = subprocess.run(
        [
            "gh",
            "api",
            "--method",
            "DELETE",
            f"user/packages/container/{package}/versions/{version_id}",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return (
            f"delete failed for {package} version {version_id}: "
            f"{(result.stderr or result.stdout).strip()[:200]}"
        )
    return ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=_ROOT)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--plan", action="store_true",
                      help="print the disposition plan without mutating "
                           "anything (the default)")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--window-close", default=None,
                        help="RFC3339 rotation-completion timestamp "
                             "(required for --execute)")
    parser.add_argument("--confirm-delete", action="store_true")
    parser.add_argument("--write-record", type=Path, default=None)
    parser.add_argument("--candidates", type=Path, default=None,
                        help="GATE-65 candidates override (fixtures)")
    parser.add_argument("--map", type=Path, default=None,
                        help="GATE-65 map override (fixtures)")
    args = parser.parse_args(argv)

    verdict_ok, problems = rotation_gate_verdict(args.candidates, args.map)
    verdict_line = "PASSED" if verdict_ok else f"RED ({len(problems)} problem(s))"
    print(f"rotation gate (GATE-65): {verdict_line}")
    for problem in problems:
        print(f"  {problem}")

    packages = inventory_packages(args.repo_root)
    print(f"remediation universe: {len(packages)} package(s): "
          f"{', '.join(packages)}")

    window = args.window_close
    if window is not None:
        parse_rfc3339(window)  # refuse a malformed window close loudly

    if args.execute:
        decision = decide_execution(verdict_ok, window, args.confirm_delete, [])
        if decision.action != "PROCEED":
            print(f"REFUSED ({decision.action}): {decision.message}")
            return 1
        enumerated = {pkg: enumerate_package(pkg) for pkg in packages}
        plan = build_plan(packages, enumerated, window, verdict_ok, problems)
        deletable, holds = executable_rows(plan["rows"])
        if holds:
            print(f"REFUSED (HOLD_REBUILD): {len(holds)} pre-window version(s) "
                  f"without a rebuilt successor — rebuild via the deploy "
                  f"workflow first, then re-run")
            for row in holds:
                print(f"  hold: {row['package']} {row['tag']} "
                      f"(created {row['created']})")
            return 1
        failures = 0
        for row in deletable:
            error = _delete_version(row["package"], row["version_id"])
            if error:
                failures += 1
                print(f"HALTED: {error}")
            else:
                print(f"deleted {row['package']} version "
                      f"{row['version_id']} ({row['tag']})")
        if args.write_record:
            plan["execution"] = "EXECUTED" if failures == 0 else "PARTIAL"
            args.write_record.write_text(render_record(plan), encoding="utf-8")
            print(f"record written: {args.write_record}")
        if failures:
            print(f"EXECUTION PARTIAL: {failures} deletion(s) failed")
            return 2
        print(f"EXECUTED: {len(deletable)} affected version(s) deleted")
        return 0

    enumerated = {pkg: enumerate_package(pkg) for pkg in packages}
    incomplete = [pkg for pkg, (_, error) in enumerated.items() if error]
    plan = build_plan(packages, enumerated, window, verdict_ok, problems)
    for state in plan["packages"]:
        if state["error"]:
            print(f"  {state['package']}: ENUMERATION FAILED: {state['error']}")
        else:
            print(f"  {state['package']}: {state['versions']} version(s)")
            for row in state["rows"]:
                print(f"    {row['tag']} (created {row['created']}) → "
                      f"{row['disposition']}")
    print(f"execution: {plan['execution']}")
    if args.write_record:
        args.write_record.write_text(render_record(plan), encoding="utf-8")
        print(f"record written: {args.write_record}")
    if incomplete:
        print(f"PLAN INCOMPLETE: enumeration failed for {len(incomplete)} "
              f"package(s) — a token with read:packages is required "
              f"(see docs/runbooks/image-remediation.md)")
        return 2
    print("PLAN ONLY — re-run with --execute (gated on GATE-65 green + "
          "--window-close + --confirm-delete)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
