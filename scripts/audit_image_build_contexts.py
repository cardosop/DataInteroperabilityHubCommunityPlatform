#!/usr/bin/env python3
"""P0-14 (close-oss-release-conditions, G5) — published-image build-context
audit.

Published images bake whatever their build context carries at build
time — pre-scrub checkouts baked real ``.env*`` files and the tracked
``.claude/settings.json`` (live bearer token) regardless of the git
rewrite. This audit proves, per PUBLISHED image (the deploy workflow's
build-push inventory — the canonical CI build definition):

1. the Dockerfile COPY'd content carries no ``.env*`` files (templates
   like ``.env.example`` / ``*.template`` are allowed);
2. the context ``.dockerignore`` excludes ``.env*`` and ``.claude/``
   (the root-fix boundary for ``COPY . .`` images);
3. the credential leg: the REAL gitleaks binary scans the COPY'd
   content with the house config (fail-closed when the binary is
   missing — an audit without the scan is no audit).

The committed report (docs/operations/image-context-audit-2026-10-19.md)
is the P2-6 input: every tag published before the P1 rotations is
affected and must be rebuilt-and-republished (or deleted) AFTER the
rotations.

Exit codes: 0 clean, 1 findings, 2 usage error (missing dockerfile,
missing gitleaks binary, unreadable workflow).
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
DEPLOY_WF = _ROOT / ".github/workflows/deploy.yml"
REPORT_DOC = _ROOT / "docs/operations/image-context-audit-2026-10-19.md"

ENV_NAME_RE = re.compile(r"^\.env(\..*)?$")
TEMPLATE_SUFFIXES = (".example", ".template", ".sample")

# The deploy workflow's build step ids → service names (the canonical
# PUSH inventory — a new build step without an entry here fails the
# P0-14 inventory pin). The dormant inference-service lane was DELETED
# in P2-6 (delete-or-wire disposition) — its build step no longer
# exists; any published versions of the deleted lane are remediated by
# scripts/remediate_affected_images.py's deleted-lane package list.
STEP_SERVICE = {
    "build-api": "api-service",
    "build-worker": "worker-service",
    "build-compliance": "compliance-service",
    "build-prefect-integration": "prefect-integration-service",
    "build-semantic": "semantic-service",
    "build-dq": "dq-service",
    "build-datacontract": "datacontract-service",
    "build-frontend": "frontend",
    "build-product-site": "product-site",
}


def is_env_file(name: str) -> bool:
    """A REAL env file (templates like .env.example / *.template are
    the documented shipped shapes and are allowed)."""
    if not ENV_NAME_RE.match(name):
        return False
    return not name.endswith(TEMPLATE_SUFFIXES)


def parse_dockerfile_copies_via_text(text: str) -> set[str]:
    """Context-source paths a Dockerfile COPYs/ADDs into the image.

    Real-syntax handling: backslash continuations joined, ``--flag``
    options (incl. ``--from=stage`` refs — stage content is not context
    content) dropped, JSON array form parsed, absolute and
    variable-expanded sources skipped (not context-resolvable).
    """
    logical: list[str] = []
    buf = ""
    for raw in text.splitlines():
        line = raw.rstrip()
        buf = f"{buf} {line.strip()}" if buf else line
        if buf.endswith("\\"):
            buf = buf[:-1].rstrip()
            continue
        logical.append(buf)
        buf = ""
    if buf:
        logical.append(buf)

    copies: set[str] = set()
    for line in logical:
        stripped = line.strip()
        upper = stripped.upper()
        if not upper.startswith(("COPY ", "ADD ")):
            continue
        body = stripped.split(None, 1)[1]
        if body.lstrip().startswith("["):
            # JSON form: COPY ["src", ... "dest"]
            try:
                tokens = json.loads(body)
            except json.JSONDecodeError:
                continue
            srcs = [str(t) for t in tokens[:-1]]
        else:
            while body.lstrip().startswith("--"):
                end = body.find(" ", 2)
                if end == -1:
                    body = ""
                    break
                body = body[end:].lstrip()
            tokens = body.split()
            if len(tokens) < 2:
                continue
            srcs = tokens[:-1]
        for raw_src in srcs:
            src = raw_src.strip("'\"")
            if src.startswith(("/", "$")):
                continue
            if src == "..":
                continue
            copies.add("" if src == "." else src)
    return copies


def parse_dockerfile_copies(path: Path) -> set[str]:
    return parse_dockerfile_copies_via_text(path.read_text(encoding="utf-8"))


def dockerignored(relpath: str, patterns: list[str]) -> bool:
    """Minimal real .dockerignore semantics: last matching pattern wins;
    slashless patterns match any path segment (dir form also matches the
    segment prefix); slashed patterns fnmatch the full path (dir form
    also matches the subtree)."""
    ignored = False
    for raw in patterns:
        pat = raw.strip()
        if not pat or pat.startswith("#"):
            continue
        negate = pat.startswith("!")
        if negate:
            pat = pat[1:].strip()
        anchored = pat.startswith("/")
        if anchored:
            pat = pat[1:]
        dir_only = pat.endswith("/")
        pat = pat.rstrip("/")
        if not pat:
            continue
        segments = relpath.split("/")
        if "/" not in pat:
            if dir_only:
                match = any(seg.startswith(pat) for seg in segments)
            else:
                match = any(fnmatch.fnmatch(seg, pat) for seg in segments)
        else:
            match = fnmatch.fnmatch(relpath, pat) or (
                dir_only and relpath.startswith(pat + "/")
            )
        if match:
            ignored = not negate
    return ignored


def load_dockerignore_patterns(root: Path) -> list[str]:
    d = root / ".dockerignore"
    if not d.is_file():
        return []
    return d.read_text(encoding="utf-8", errors="replace").splitlines()


def audit_context(
    root: Path,
    copies: set[str],
    dockerignore: Path | None = None,
) -> list[str]:
    """Env-file findings for one build context (the COPY'd content)."""
    patterns = (
        dockerignore.read_text(encoding="utf-8").splitlines()
        if dockerignore is not None and dockerignore.is_file()
        else load_dockerignore_patterns(root)
    )
    findings: list[str] = []
    for src in sorted(copies):
        if src in ("", "."):
            # `COPY . .` — the whole context enters the image.
            files = sorted(f for f in root.rglob("*") if f.is_file())
            for f in files:
                rel = f.relative_to(root).as_posix()
                if is_env_file(f.name) and not dockerignored(rel, patterns):
                    findings.append(f"baked env file: {rel}")
            continue
        path = root / src
        if path.is_file():
            if is_env_file(path.name) and not dockerignored(src, patterns):
                findings.append(f"baked env file: {src}")
        elif path.is_dir():
            for f in sorted(path.rglob("*")):
                if not f.is_file():
                    continue
                rel = f.relative_to(root).as_posix()
                if is_env_file(f.name) and not dockerignored(rel, patterns):
                    findings.append(f"baked env file: {rel}")
    return findings


def load_inventory(workflow: Path, root: Path = _ROOT) -> list[dict]:
    """The canonical publish inventory: every docker/build-push-action
    step in the deploy workflow's build job."""
    try:
        import yaml
    except ImportError:
        print("ERROR: PyYAML required (pip install pyyaml)", file=sys.stderr)
        sys.exit(2)
    wf = yaml.safe_load(workflow.read_text(encoding="utf-8"))
    env = wf.get("env", {})
    registry = str(env.get("REGISTRY", "ghcr.io"))
    # IMAGE_NAMESPACE is a github-expression — resolve the owner from
    # the real origin remote, never a hardcoded guess.
    namespace = f"{_git_origin_owner(root)}/datainteroperabilityhub"
    inventory: list[dict] = []
    for step in wf["jobs"]["build"]["steps"]:
        uses = step.get("uses", "")
        if not uses.startswith("docker/build-push-action"):
            continue
        sid = step.get("id", "")
        service = STEP_SERVICE.get(sid)
        if service is None:
            print(f"ERROR: unlisted build step {sid!r} — extend STEP_SERVICE")
            return []
        with_block = step.get("with", {})
        inventory.append(
            {
                "service": service,
                "image": f"{registry}/{namespace}-{service}",
                "context": str(with_block.get("context", ".")),
                "file": str(with_block.get("file", "")),
            }
        )
    return inventory


def _git_origin_owner(root: Path) -> str:
    url = subprocess.run(
        ["git", "-C", str(root), "remote", "get-url", "origin"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    match = re.search(r"(?:github\.com[:/])([^/]+)/", url)
    return match.group(1) if match else "cardosop"


def credential_findings(root: Path) -> list[str]:
    """The REAL gitleaks scan over the tracked tree (the COPY'd content
    for the whole-context images). Fail-closed on a missing binary."""
    gitleaks = shutil.which("gitleaks")
    if not gitleaks:
        print(
            "ERROR: gitleaks binary missing — the credential leg cannot "
            "run; an audit without the scan is no audit",
            file=sys.stderr,
        )
        sys.exit(2)
    with tempfile.TemporaryDirectory(prefix="image-context-audit.") as tmp:
        staging = Path(tmp) / "tracked"
        staging.mkdir()
        tracked = subprocess.run(
            ["git", "-C", str(root), "ls-files"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.splitlines()
        for line in tracked:
            src = root / line
            if not src.is_file():
                continue
            dst = staging / line
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(src.read_bytes())
        report = Path(tmp) / "report.json"
        result = subprocess.run(
            [
                gitleaks,
                "detect",
                "--no-git",
                "--source",
                ".",
                "--config",
                str(root / ".gitleaks.toml"),
                "--report-format",
                "json",
                "--report-path",
                str(report),
                "--no-banner",
                "--log-level=error",
            ],
            cwd=staging,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode not in (0, 1):
            return [f"gitleaks failed (exit {result.returncode})"]
        findings = json.loads(report.read_text(encoding="utf-8"))
        return [
            f"{f.get('RuleID')} in {f.get('File')} (line {f.get('StartLine')})"
            for f in findings
        ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=_ROOT)
    parser.add_argument(
        "--write-report",
        action="store_true",
        help="refresh the committed report doc",
    )
    args = parser.parse_args(argv)

    workflow = args.root / ".github/workflows/deploy.yml"
    if not workflow.is_file():
        print(f"ERROR: deploy workflow missing: {workflow}", file=sys.stderr)
        return 2
    inventory = load_inventory(workflow, args.root)
    if not inventory:
        return 2

    problems: list[str] = []
    rows: list[dict] = []
    for entry in inventory:
        dockerfile = args.root / entry["file"]
        if not dockerfile.is_file():
            # The workflow itself guards on the missing file
            # (`if [ -f services/inference-service/Dockerfile ]`) — a
            # dormant lane, reported for P2-6 (stale published tags),
            # not a hard audit failure.
            rows.append(
                {**entry, "env_findings": [], "dockerignore_ok": None,
                 "dormant": True}
            )
            continue
        context = args.root if entry["context"] == "." else (args.root / entry["context"])
        copies = parse_dockerfile_copies(dockerfile)
        findings = audit_context(context, copies, dockerignore=context / ".dockerignore")
        patterns = load_dockerignore_patterns(context)
        required = [".env*"]
        if entry["context"] == ".":
            # .claude/ lives at the repo root — only the whole-repo
            # context can bake it.
            required.append(".claude/")
        for pat in required:
            if pat not in patterns and not any(
                p == pat.rstrip("/") or p == pat for p in patterns
            ):
                problems.append(
                    f"{entry['service']}: context .dockerignore does not "
                    f"exclude {pat!r}"
                )
        problems.extend(f"{entry['service']}: {f}" for f in findings)
        rows.append(
            {
                **entry,
                "env_findings": findings,
                "dockerignore_ok": ".env*" in patterns and (
                    entry["context"] != "." or ".claude/" in patterns
                ),
            }
        )

    cred = credential_findings(args.root)
    if cred:
        problems.extend(f"credential: {c}" for c in cred)

    print(f"P0-14 image-context audit: {len(inventory)} images")
    for row in rows:
        if row.get("dormant"):
            status = "DORMANT"
        elif row["env_findings"] or not row["dockerignore_ok"]:
            status = "FINDING"
        else:
            status = "OK"
        print(f"  {status:7s} {row['image']} ({row['file']}, context={row['context']})")
        for f in row["env_findings"]:
            print(f"          - {f}")
    print(f"  credential leg: {len(cred)} finding(s)")

    if args.write_report:
        _write_report(rows, cred)
        print(f"report written: {REPORT_DOC}")

    if problems:
        print(f"IMAGE-CONTEXT AUDIT FAILED: {len(problems)} problem(s)")
        for p in problems:
            print(f"  FAIL: {p}")
        return 1
    print("IMAGE-CONTEXT AUDIT CLEAN")
    return 0


def _write_report(rows: list[dict], cred: list[str]) -> None:
    lines = [
        "# Image Build-Context Audit — 2026-10-19 (P0-14, G5)",
        "",
        "Audit of every PUBLISHED image's build context for baked `.env*`",
        "files and credential material. Published images carry whatever the",
        "context held at build time — pre-scrub checkouts baked real env",
        "files and the tracked `.claude/settings.json` (live `sk-` bearer",
        "token) regardless of the git rewrite.",
        "",
        "## Findings",
        "",
    ]
    exposed = (
        "The tracked `.claude/settings.json` carried a live bearer token and "
        "is baked by every whole-context (`COPY . .`) backend image "
        "(api-service, worker-service) plus the buildcache tags. Root-fixed "
        "2026-10-19: the file is untracked (it was already gitignored), the "
        "root `.dockerignore` now excludes `.claude/`, and the house "
        "gitleaks config gained the anthropic rule (the gap that let the "
        "token pass the P0-9 tracked-tree scan)."
    )
    lines += ["### Credential exposure", "", exposed, ""]
    if cred:
        lines += ["Credential findings (tracked tree):", ""]
        lines += [f"- {c}" for c in cred]
        lines.append("")
    else:
        lines += ["Current tracked tree: 0 credential findings.", ""]
    lines += [
        "## Per-image disposition",
        "",
        "| Image | Dockerfile | Context | Env findings | Dockerignore |",
        "|---|---|---|---|---|",
    ]
    for row in rows:
        if row.get("dormant"):
            lines.append(
                f"| {row['image']} | DORMANT (no Dockerfile; "
                f"workflow-guarded) | {row['context']} | — | — |"
            )
            continue
        findings = "; ".join(row["env_findings"]) or "none"
        lines.append(
            f"| {row['image']} | {row['file']} | {row['context']} | "
            f"{findings} | {'yes' if row['dockerignore_ok'] else 'NO'} |"
        )
    lines += [
        "",
        "## Affected images — the P2-6 input",
        "",
        "Every tag published BEFORE the P1 rotations is affected (the",
        "rotations are Phase 1, pending): all current tags of all "
        f"{len(rows)}",
        "images plus their `buildcache` tags (BuildKit cache layers can",
        "retain intermediate-layer content, incl. pre-fix `.claude/`).",
        "",
        "P2-6 disposition: AFTER the rotations land (old values dead),",
        "rebuild-and-republish (or delete) every pre-rotation tag of:",
        "",
    ]
    for row in rows:
        lines.append(f"- `{row['image']}` (all tags + `:buildcache`)")
    lines += [
        "",
        "## Lane disposition (P2-6)",
        "",
        "The dormant `inference-service` lane (no Dockerfile since",
        "inception — the deploy workflow guard always skipped it) is",
        "DELETED per the delete-or-wire disposition: the workflow build",
        "lane, the disabled helm chart (`enabled: false`, replicaCount",
        "0, an image that could never be built) and its network policy",
        "are removed; the package stays in the P2-6 remediation",
        "executor's deleted-lane list so any published versions get",
        "deleted (no rebuild is possible for a lane that no longer",
        "exists). The remaining registry packages follow the",
        "rebuild-after-rotation disposition above.",
        "",
    ]
    lines += [
        "",
        "Enumeration at execution time (needs `read:packages` scope):",
        "",
        "```bash",
        "gh api 'user/packages/container/<package>/versions' \\",
        "  --paginate --jq '.[] | {name: .name, created: .created_at}'",
        "```",
        "",
    ]
    REPORT_DOC.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
