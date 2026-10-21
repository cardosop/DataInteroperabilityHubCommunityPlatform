#!/usr/bin/env python3
"""
P2-0 (close-oss-release-conditions) — rewrite-input reconstruction.
The G2 fix: the W0.4 rewrite inputs (the verifier's secret-fragments
file + filter-repo's ``--replace-text`` file) were transient ``/tmp``
files and are gone. This tool makes them REPRODUCIBLE from the
repository itself, so the loss cannot recur:

- ``scan`` — the REAL gitleaks binary enumerates candidate secret
  values over EVERY commit reachable from any ref of the current
  refs (``--log-opts=--all``) with the EXHAUSTIVE view of the house
  config (every rule kept, every allowlist stripped — the candidate
  pass must never be narrower than the policy).  Findings are deduped
  by value; the operator-facing candidates file (values included) is
  written to the out-dir with 0600, OUTSIDE the repository — stdout
  carries counts only, NEVER values (the W0.2 redaction contract).
  The hash-keyed ledger (no values) is the build's input.

- ``build`` — a committed, hash-keyed classification file resolves
  every candidate: ``filtered`` (reason tag — placeholder/fixture/
  doc-example/…), ``dead`` (rotation-dead — evidence tag resolving in
  the rotation records), ``blocked`` (real secret, rotation pending).
  The build then regenerates ``fragments.txt`` (the verifier's
  ``git log --all -S`` sweep list) and ``replace.txt`` (filter-repo
  ``--replace-text``, ``value==>REDACTED``) and enforces the
  completeness assertion: EVERY candidate is filtered or
  rotation-dead.  Any unclassified candidate, any dead value without
  evidence, or any blocked (still-live) value REFUSES the build —
  nothing is written.  Multi-line values cannot ride the line-based
  replace format: they must be dropped by the exclusion-paths file or
  the build refuses (unscrubbable).  ``--house-report`` adds the
  P2-1-proof coherence check: every candidate the REAL house config
  still flags must be scrub-covered, path-covered, or classified
  config-suppressed — the rewritten history must pass the verifier's
  gitleaks-over-history pass.

The committed artifacts (``scripts/rewrite_input_classifications.tsv``
+ ``scripts/rewrite_inventory.json``) are hash-keyed — no values — and
are the reconciliation anchor pinned by
``scripts/tests/test_p20_rewrite_input_reconstruction.py``.  Values
are regenerated from history by re-running the scan; the chain is
fully reproducible from the repo + the committed classification.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tomllib
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DEFAULT = _ROOT / ".gitleaks.toml"
PATHS_DEFAULT = _ROOT / "scripts/history_rewrite_paths.txt"
CLASSIFICATIONS_DEFAULT = _ROOT / "scripts/rewrite_input_classifications.tsv"
RECORD = (
    "openspec/changes/oss-release-remediation/history-rewrite-2026-10-06.md"
)

# The W0.2 HIGH-class / live-infrastructure credential rules: a
# rule-level default classification on these could silently filter a
# real credential — forbidden by the build.
SECRET_CLASS_RULES = frozenset(
    {
        "aws-access-token",
        "databricks-api-token",
        "azure-ad-client-secret",
        "stripe-access-token",
        "private-key",
        "anthropic",
        "gcp-api-key",
        "gcp-service-account",
        "kubernetes-secret-yaml",
    }
)

REPLACEMENT = "REDACTED"


def _run(
    args: list[str],
    *,
    cwd: Path | None = None,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args, capture_output=True, text=True, check=check, cwd=cwd
    )


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return _run(["git", "-C", str(repo), *args])


def _repo_toplevel(repo: Path) -> str:
    out = _git(repo, "rev-parse", "--show-toplevel")
    return out.stdout.strip() if out.returncode == 0 else ""


def _refuse_inside_repo(out_dir: Path, repo: Path) -> str | None:
    """Value-bearing outputs must never sit where a commit could pick
    them up: the out-dir must live OUTSIDE the repository work tree."""
    top = _repo_toplevel(repo)
    if not top:
        return f"{repo} is not a git repo"
    root = Path(top).resolve()
    target = out_dir.resolve()
    if target == root or target.is_relative_to(root):
        return (
            f"out-dir {out_dir} is inside the repository work tree "
            f"({root}) — value-bearing outputs must live outside the repo"
        )
    return None


def assert_exhaustive_config(source: Path, derived: Path) -> None:
    """The derived candidate config keeps every rule and strips every
    allowlist (top-level and per-rule). A dropped rule is a silent
    candidate gap — the W0.2 vacuity class. Raises AssertionError."""
    src = tomllib.loads(source.read_text(encoding="utf-8"))
    der = tomllib.loads(derived.read_text(encoding="utf-8"))
    assert src.get("rules"), f"{source} carries no rules"
    src_ids = [r["id"] for r in src["rules"]]
    der_ids = [r["id"] for r in der["rules"]]
    assert src_ids == der_ids, (
        f"rule set changed: {len(src_ids)} -> {len(der_ids)} rules "
        f"(missing: {sorted(set(src_ids) - set(der_ids))[:5]})"
    )
    assert "allowlist" not in der, "derived config must strip the allowlist"
    for rule in der["rules"]:
        assert "allowlist" not in rule, (
            f"rule {rule['id']} keeps a per-rule allowlist in the derived config"
        )


def escape_replace_needle(value: str) -> str:
    """filter-repo's ``--replace-text`` splits each line on ``==>``; a
    literal ``==>`` in the needle must be escaped as ``\\==>``."""
    return value.replace("==>", "\\==>")


def _load_paths(paths_file: Path) -> list[str]:
    entries = [
        line.strip()
        for line in paths_file.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]
    if not paths_file.exists():
        raise SystemExit(f"excluded-paths file missing: {paths_file}")
    return entries


def _path_covered(file_path: str, entries: list[str]) -> bool:
    """filter-repo's literal semantics, exactly: a trailing-slash entry
    covers everything below it; a bare entry is an exact file name."""
    return any(
        file_path.startswith(entry) if entry.endswith("/") else file_path == entry
        for entry in entries
    )


def _derive_exhaustive_config(config: Path, out: Path) -> Path:
    """Every rule kept, every allowlist stripped — the candidate view."""
    try:
        import tomli_w
    except ImportError:
        raise SystemExit(
            "tomli_w is required to write the derived gitleaks config "
            "(pip install tomli_w)"
        ) from None
    data = tomllib.loads(config.read_text(encoding="utf-8"))
    if "rules" not in data or not data["rules"]:
        raise SystemExit(f"config {config} carries no rules — refusing a vacuous scan")
    data.pop("allowlist", None)
    rules = []
    for rule in data["rules"]:
        rule.pop("allowlist", None)
        rules.append(rule)
    data["rules"] = rules
    derived = out / "config-exhaustive.toml"
    derived.write_text(tomli_w.dumps(data), encoding="utf-8")
    os.chmod(derived, 0o600)
    return derived


def scan(args: argparse.Namespace) -> int:
    repo = Path(args.repo)
    problems: list[str] = []
    if _git(repo, "rev-parse", "--git-dir").returncode != 0:
        problems.append(f"{repo} is not a git repo")
    config = Path(args.config)
    if not config.exists():
        problems.append(f"gitleaks config missing: {config}")
    binary = args.gitleaks or shutil.which("gitleaks")
    if not binary or not Path(binary).exists():
        problems.append(
            "gitleaks binary not found — the candidate pass cannot be "
            "skipped (a reconstruction without the real scan is no "
            "reconstruction)"
        )
    out = Path(args.out_dir)
    problem = _refuse_inside_repo(out, repo)
    if problem:
        problems.append(problem)
    if problems:
        for problem in problems:
            print(f"FAIL: {problem}")
        return 1
    out.mkdir(parents=True, exist_ok=True)
    os.chmod(out, 0o700)
    derived = _derive_exhaustive_config(config, out)
    report = out / "report.json"
    result = _run(
        [
            binary,
            "detect",
            "--source",
            str(repo),
            "--log-opts=--all",
            "--config",
            str(derived),
            "--report-format",
            "json",
            "--report-path",
            str(report),
            "--no-banner",
            "--log-level=warn",
        ]
    )
    if result.returncode not in (0, 1):
        detail = result.stderr.strip().splitlines()
        tail = detail[-1] if detail else "no output"
        print(f"FAIL: gitleaks failed (exit {result.returncode}): {tail[:200]}")
        return 1
    try:
        findings = json.loads(report.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        print("FAIL: gitleaks produced no readable report")
        return 1
    os.chmod(report, 0o600)

    by_value: dict[str, dict] = {}
    for finding in findings:
        value = finding.get("Match", "")
        key = hashlib.sha256(value.encode("utf-8", "surrogateescape")).hexdigest()
        row = by_value.setdefault(
            key,
            {
                "value": value,
                "rule": finding.get("RuleID", "?"),
                "count": 0,
                "files": [],
                "commits": [],
                "multiline": "\n" in value,
            },
        )
        row["count"] += 1
        if finding.get("File") not in row["files"]:
            row["files"].append(finding.get("File", "?"))
        if finding.get("Commit") not in row["commits"]:
            row["commits"].append(finding.get("Commit", "?"))

    head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    version = _run([binary, "version"]).stdout.strip()
    ledger = {
        "generated_at": datetime.now(timezone.utc).isoformat(),  # noqa: UP017
        "repo": str(repo),
        "repo_head": head,
        "gitleaks_version": version,
        "config": str(config),
        "config_sha256": hashlib.sha256(
            config.read_bytes()
        ).hexdigest(),
        "derived_config": "config-exhaustive.toml",
        "findings_total": len(findings),
        "values_total": len(by_value),
        "values": {
            key: {k: v for k, v in row.items() if k != "value"}
            for key, row in by_value.items()
        },
    }
    (out / "candidates-ledger.json").write_text(
        json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.chmod(out / "candidates-ledger.json", 0o600)

    # operator review file — the ONLY artifact carrying the values.
    lines = []
    for key in sorted(by_value):
        row = by_value[key]
        escaped = (
            row["value"].replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n")
        )
        lines.append(
            f"{key}\t{row['count']}\t{row['rule']}\t"
            f"{','.join(row['files'])}\t{escaped}"
        )
    (out / "candidates.tsv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.chmod(out / "candidates.tsv", 0o600)

    per_rule: dict[str, int] = {}
    for row in by_value.values():
        per_rule[row["rule"]] = per_rule.get(row["rule"], 0) + row["count"]
    print(f"SCAN OK: {len(findings)} findings, {len(by_value)} unique values")
    for rule, count in sorted(per_rule.items(), key=lambda kv: -kv[1]):
        print(f"  {count:5d}  {rule}")
    print(f"candidates + ledger written to {out}")
    return 0


_scan_value_cache_store: dict[str, dict[str, str]] = {}


def _scan_value_cache(tsv: Path) -> dict[str, str]:
    if str(tsv) in _scan_value_cache_store:
        return _scan_value_cache_store[str(tsv)]
    cache: dict[str, str] = {}
    if tsv.exists():
        for line in tsv.read_text().splitlines():
            parts = line.split("\t", 4)
            if len(parts) == 5:
                cache[parts[0]] = (
                    parts[4]
                    .replace("\\t", "\t")
                    .replace("\\n", "\n")
                    .replace("\\\\", "\\")
                )
    _scan_value_cache_store[str(tsv)] = cache
    return cache


def _recover_value(ledger_path: Path, key: str) -> str:
    """The ledger intentionally omits values; the build re-reads the
    scan's candidates.tsv (hash-keyed, value-bearing, 0600, sitting
    NEXT TO the ledger) to recover them — the values never travel
    through the classification file or the committed artifacts."""
    tsv = ledger_path.parent / "candidates.tsv"
    cache = _scan_value_cache(tsv)
    if key not in cache:
        raise SystemExit(
            f"candidates.tsv ({tsv}) does not carry {key[:16]}… — the value "
            f"cannot be recovered; re-run `scan`"
        )
    return cache[key]


def _write_0600(path: Path, content: str) -> None:
    fd = os.open(path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(content)


def _load_classifications(path: Path) -> tuple[dict, list[str]]:
    entries: dict[str, tuple[str, str, str]] = {}
    errors: list[str] = []
    seen: set[str] = set()
    for number, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            errors.append(f"{path}:{number}: need selector<TAB>status<TAB>tag")
            continue
        selector, status, tag = parts[0].strip(), parts[1].strip(), parts[2].strip()
        reason = "\t".join(parts[3:]).strip()
        if status not in ("filtered", "dead", "blocked"):
            errors.append(f"{path}:{number}: unknown status {status!r}")
            continue
        if not tag:
            errors.append(f"{path}:{number}: {status} entry needs an evidence/reason tag")
            continue
        if selector in seen:
            errors.append(f"{path}:{number}: duplicate selector {selector}")
            continue
        seen.add(selector)
        if selector.startswith("rule:"):
            rule = selector[5:]
            if rule in SECRET_CLASS_RULES:
                errors.append(
                    f"{path}:{number}: rule-level default forbidden on the "
                    f"secret-class rule {rule} (a mass filter on a live-"
                    f"credential rule is the silent-gap failure mode)"
                )
        entries[selector] = (status, tag, reason)
    return entries, errors


def build(args: argparse.Namespace) -> int:
    repo = Path(args.repo)
    ledger_path = Path(args.ledger)
    classes_path = Path(args.classifications)
    out = Path(args.out_dir)
    problems: list[str] = []
    problem = _refuse_inside_repo(out, repo)
    if problem:
        problems.append(problem)
    if not ledger_path.exists():
        problems.append(f"candidate ledger missing: {ledger_path}")
    if not classes_path.exists():
        problems.append(f"classifications file missing: {classes_path}")
    ledger: dict = {}
    ledger_loaded = False
    if ledger_path.exists():
        try:
            ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
            ledger_loaded = True
        except (OSError, json.JSONDecodeError):
            problems.append(f"unreadable candidate ledger: {ledger_path}")
    values: dict[str, dict] = ledger.get("values", {})
    if ledger_loaded and not values:
        problems.append("the candidate ledger carries no values")
    if problems:
        for problem in problems:
            print(f"FAIL: {problem}")
        return 1

    classes, class_errors = _load_classifications(classes_path)
    known_hashes = set(values)
    known_rules = {row["rule"] for row in values.values()}
    errors = list(class_errors)
    for selector in classes:
        if selector.startswith("sha256:"):
            if selector[7:] not in known_hashes:
                errors.append(
                    f"classification for unknown candidate hash "
                    f"{selector[7:][:16]}… (drift: the scan never saw it)"
                )
        elif selector.startswith("rule:"):
            if selector[5:] not in known_rules:
                errors.append(
                    f"classification for rule {selector[5:]} with no "
                    f"candidates (drift)"
                )
        else:
            errors.append(f"unknown selector {selector!r}")

    resolved: dict[str, tuple[str, str, str]] = {}
    unclassified: list[str] = []
    for key, row in values.items():
        entry = classes.get(f"sha256:{key}") or classes.get(f"rule:{row['rule']}")
        if entry is None:
            unclassified.append(key)
        else:
            resolved[key] = entry
    if unclassified:
        errors.append(
            f"completeness assertion failed: {len(unclassified)} candidate(s) "
            f"unclassified (hashes only — classify in {classes_path}): "
            + ", ".join(f"{key[:16]}…" for key in sorted(unclassified)[:20])
            + (" …" if len(unclassified) > 20 else "")
        )
    blocked = [
        key for key, (status, _tag, _reason) in resolved.items() if status == "blocked"
    ]
    blocked_tags = sorted({resolved[key][1] for key in blocked})

    paths = _load_paths(Path(args.paths_file))

    multi_line_errors = [
        f"multi-line value {key[:16]}… ({row['rule']}) in kept file(s): "
        + ", ".join(
            f for f in row["files"] if not _path_covered(f, paths)
        )[:300]
        for key, row in values.items()
        if key in resolved
        and resolved[key][0] == "dead"
        and row["multiline"]
        and any(not _path_covered(f, paths) for f in row["files"])
    ]
    errors.extend(multi_line_errors)

    if args.house_report:
        try:
            house = json.loads(
                Path(args.house_report).read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError):
            errors.append(f"unreadable house report: {args.house_report}")
            house = []
        house_keys = {
            hashlib.sha256(f.get("Match", "").encode("utf-8", "surrogateescape")).hexdigest()
            for f in house
        }
        for key in sorted(house_keys & known_hashes):
            if key not in resolved:
                # already reported by the completeness assertion
                continue
            row = values[key]
            status, tag, _reason = resolved[key]
            scrub_covered = status == "dead" and not row["multiline"]
            path_covered = all(_path_covered(f, paths) for f in row["files"])
            config_suppressed = status == "filtered" and tag.startswith(
                "config-suppressed:"
            )
            if not (scrub_covered or path_covered or config_suppressed):
                errors.append(
                    f"P2-1-proof coherence: candidate {key[:16]}… "
                    f"({row['rule']}) is still flagged by the house config "
                    f"after the rewrite inputs as classified (status={status}) "
                    f"— it must be scrub-covered, path-covered, or "
                    f"config-suppressed"
                )
        for key in sorted(house_keys - known_hashes):
            errors.append(
                f"house report carries a candidate missing from the "
                f"exhaustive ledger: {key[:16]}… (reports disagree)"
            )

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        print(f"BUILD REFUSED: {len(errors)} problem(s) — nothing was written")
        return 1

    # ---- emit (deterministic: hash order everywhere) ----
    out.mkdir(parents=True, exist_ok=True)
    os.chmod(out, 0o700)
    fragment_lines: list[str] = []
    replace_lines: list[str] = []
    rows: list[dict] = []
    for key in sorted(values):
        row = values[key]
        status, tag, reason = resolved[key]
        in_fragments = status == "dead" and not row["multiline"]
        in_replace = status == "dead" and not row["multiline"]
        rows.append(
            {
                "hash": key,
                "rule": row["rule"],
                "status": status,
                "tag": tag,
                "reason": reason,
                "count": row["count"],
                "files": row["files"],
                "commits": row["commits"],
                "multiline": row["multiline"],
                "in_fragments": in_fragments,
                "in_replace": in_replace,
                "paths_covered": all(_path_covered(f, paths) for f in row["files"]),
            }
        )
        if in_fragments:
            fragment_lines.append(_recover_value(ledger_path, key))
        if in_replace:
            replace_lines.append(
                f"{escape_replace_needle(_recover_value(ledger_path, key))}==>{REPLACEMENT}"
            )
    inventory = {
        "generated_at": datetime.now(timezone.utc).isoformat(),  # noqa: UP017
        "tool": "scripts/reconstruct_rewrite_inputs.py",
        "record": RECORD,
        "repo_head": ledger.get("repo_head"),
        "config": Path(ledger.get("config", "")).name or ".gitleaks.toml",
        "gitleaks_version": ledger.get("gitleaks_version"),
        "classifications": str(classes_path),
        "findings_total": ledger.get("findings_total"),
        "values_total": len(values),
        "statuses": {
            status: sum(1 for r in rows if r["status"] == status)
            for status in ("filtered", "dead", "blocked")
        },
        "fragments_count": len(fragment_lines),
        "replace_count": len(replace_lines),
        "blocked_tags": blocked_tags,
        "completeness": True,
        "values": rows,
    }
    # the commit-safe reconciliation anchor is written even while the
    # live-secret gate refuses the value-bearing files: the blocked
    # state is the honest current record
    _write_0600(
        out / "inventory.json",
        json.dumps(inventory, indent=2, sort_keys=True) + "\n",
    )
    if blocked:
        print(
            "live-secret gate: the build refuses the value-bearing outputs "
            "while real secrets await rotation evidence (Phase 2 "
            f"sequencing) — blocked on: {', '.join(blocked_tags)}"
        )
        print(
            f"inventory.json (hash-keyed, no values) written to {out} — "
            f"re-run after the rotations land"
        )
        return 1
    _write_0600(
        out / "fragments.txt",
        "# P2-0 reconstruction — secret fragments for "
        "scripts/verify_history_rewrite.py (git log --all -S sweep).\n"
        "# Generated by scripts/reconstruct_rewrite_inputs.py build.\n"
        + "\n".join(fragment_lines)
        + ("\n" if fragment_lines else ""),
    )
    _write_0600(
        out / "replace.txt",
        "# P2-0 reconstruction — git filter-repo --replace-text entries.\n"
        "# Generated by scripts/reconstruct_rewrite_inputs.py build.\n"
        + "\n".join(replace_lines)
        + ("\n" if replace_lines else ""),
    )
    print(
        f"BUILD OK: {len(fragment_lines)} fragment(s), "
        f"{len(replace_lines)} replace entrie(s), "
        f"{inventory['statuses']['filtered']} filtered, "
        f"{inventory['statuses']['dead']} dead, "
        f"{inventory['statuses']['blocked']} blocked"
    )
    print(f"outputs written to {out}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    scan_p = sub.add_parser("scan", help="enumerate candidate secret values")
    scan_p.add_argument("--repo", type=Path, required=True)
    scan_p.add_argument("--config", type=Path, default=CONFIG_DEFAULT)
    scan_p.add_argument("--out-dir", type=Path, required=True)
    scan_p.add_argument("--gitleaks", type=str, default=None)
    scan_p.set_defaults(func=scan)

    build_p = sub.add_parser("build", help="regenerate fragments + replace")
    build_p.add_argument("--repo", type=Path, required=True)
    build_p.add_argument("--ledger", type=Path, required=True)
    build_p.add_argument(
        "--classifications", type=Path, default=CLASSIFICATIONS_DEFAULT
    )
    build_p.add_argument("--out-dir", type=Path, required=True)
    build_p.add_argument("--paths-file", type=Path, default=PATHS_DEFAULT)
    build_p.add_argument("--house-report", type=Path, default=None)
    build_p.set_defaults(func=build)

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
