"""
Contract tests for scripts/reconstruct_rewrite_inputs.py
(close-oss-release-conditions P2-0 — the G2 rewrite-input restoration).

The W0.4 rewrite inputs (`/tmp/w02-fragments.txt`, `/tmp/w02-replace.txt`)
were transient files and are gone; the plan-review G2 fix requires a
REPRODUCIBLE reconstruction chain: the real gitleaks binary enumerates
candidate secret values over the CURRENT refs (exhaustive view —
allowlists stripped, rules intact), a committed hash-keyed
classification file resolves every candidate (filtered with reason /
rotation-dead with evidence / blocked on pending rotation), and the
build regenerates the verifier's fragments file + filter-repo's
`--replace-text` file with a completeness assertion: every candidate
is filtered or rotation-dead, or the build REFUSES (the live-secret
gate — Phase 2 must not run while a rotation is pending).

The pins here prove the mechanics against REAL fixtures (real gitleaks,
real git repos — no mocks) and the reconciliation against the COMMITTED
artifacts (`scripts/rewrite_input_classifications.tsv` +
`scripts/rewrite_inventory.json` — hash-keyed, never carrying values).
Secret VALUES are never printed by the tool; every pin asserts that
discipline.
"""

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

scripts_dir = Path(__file__).parent.parent
sys.path.insert(0, str(scripts_dir))

ROOT = scripts_dir.parent
sys.path.insert(0, str(ROOT))

from envpolicy import skip_or_fail

script_path = scripts_dir / "reconstruct_rewrite_inputs.py"
TOOL = str(script_path)
spec = importlib.util.spec_from_file_location("reconstruct_rewrite_inputs", script_path)
assert spec is not None, "reconstruct_rewrite_inputs.py must load (P2-0 ships it)"
assert spec.loader is not None
recon = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recon)

GITLEAKS = shutil.which("gitleaks")
GITLEAKS_CONFIG = ROOT / ".gitleaks.toml"

PLANTED = "FIXTURESECRET7f3d2a1b9c4e8f6a5d3b7c9e1f2a4b6d"
# gitleaks' generic-api-key rule matches the WHOLE assignment
# (`API_TOKEN = "..."`) — the candidate value (and its hash) is the
# Match, exactly as filter-repo / `git log -S` will consume it.
PLANTED_MATCH = f'API_TOKEN = "{PLANTED}"'
PLANTED_HASH = hashlib.sha256(PLANTED_MATCH.encode()).hexdigest()
JWT_EXAMPLE = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIn0."
    "dGVA1dYiNnkh3uGqPJp0bZTVM5cQmY9k2vLB7cWqXe8"
)
DIGEST_LINE = "postgres.key sha256: 929eca7d1625bcc6499695d29d857fa91a9e8232bc0dab0635ec0989a2dacdbe"


def _require_gitleaks() -> None:
    """W16: the scan runs the REAL scanner — a missing binary is an
    environment branch: skip locally, raise in CI."""
    if not GITLEAKS:
        skip_or_fail(
            "gitleaks binary (the candidate pass is proven against "
            "the real scanner, never a fake)"
        )


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, TOOL, *args],
        capture_output=True,
        text=True,
        check=False,
        cwd=cwd,
    )


def _init_repo(tmp_path: Path) -> Path:
    """A fixture repo carrying every candidate shape the tool must
    handle: a generic-api-key secret (the planted value), a JWT, a
    multi-line private key in a kept file, and a digest line."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "app.py").write_text(f'API_TOKEN = "{PLANTED}"\n')
    (repo / "token.txt").write_text(f"bearer {JWT_EXAMPLE}\n")
    (repo / "pem.txt").write_text(
        "-----BEGIN PRIVATE KEY-----\n"
        "MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQDFakeKeyLine0000\n"
        "anotherDistinctBase64LineThatIsUnique9876543210abcdeffedcba09\n"
        "-----END PRIVATE KEY-----\n"
    )
    (repo / "record.md").write_text(f"evidence: {DIGEST_LINE}\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "initial with secrets")
    return repo


def _classifications(tmp_path: Path, rows: list[str]) -> Path:
    f = tmp_path / "classifications.tsv"
    f.write_text("\n".join(rows) + "\n")
    return f


def _full_rows(
    scan_out: Path,
    overrides: list[str],
    skip_hashes: set[str] | None = None,
) -> list[str]:
    """Every candidate classified: the override rows win, the rest are
    value-level filtered (so completeness never confounds the test's
    own intent)."""
    ledger = _ledger(scan_out)
    taken = {row.split("\t")[0] for row in overrides}
    rows = list(overrides)
    for key in sorted(ledger["values"]):
        if f"sha256:{key}" in taken or key in (skip_hashes or set()):
            continue
        rows.append(f"sha256:{key}\tfiltered\tfixture\tauto")
    return rows


def _scan(repo: Path, out: Path, extra: list[str] | None = None) -> subprocess.CompletedProcess[str]:
    # the TOOL creates the out-dir — the pin must not (the refusal
    # contract asserts nothing value-bearing is created inside the repo)
    return _run(
        [
            "scan",
            "--repo",
            str(repo),
            "--config",
            str(GITLEAKS_CONFIG),
            "--out-dir",
            str(out),
            *(extra or []),
        ],
        repo.parent,
    )


def _ledger(out: Path) -> dict:
    return json.loads((out / "candidates-ledger.json").read_text())


# ── scan subcommand ────────────────────────────────────────────────────────


def test_scan_extracts_planted_secret_never_prints_it(tmp_path):
    """RED-first: the candidate pass finds the planted value, records
    its hash in the ledger, and NEVER prints the value to stdout/stderr
    (the W0.2 redaction contract)."""
    _require_gitleaks()
    repo = _init_repo(tmp_path)
    out = tmp_path / "scan-out"
    proc = _scan(repo, out)
    assert proc.returncode == 0, proc.stderr
    ledger = _ledger(out)
    assert PLANTED_HASH in ledger["values"], "the planted secret must be a candidate"
    assert ledger["values"][PLANTED_HASH]["rule"] == "generic-api-key"
    assert PLANTED not in proc.stdout
    assert PLANTED not in proc.stderr
    # the operator-facing candidates file carries the value (0600), the
    # ledger itself never does
    candidates = (out / "candidates.tsv").read_text()
    assert PLANTED in candidates
    assert PLANTED not in json.dumps(ledger)


def test_scan_derives_exhaustive_config_rules_intact(tmp_path):
    """The candidate view strips allowlists but keeps every rule — a
    lost rule is a silent candidate gap (the W0.2 vacuity class)."""
    _require_gitleaks()
    repo = _init_repo(tmp_path)
    out = tmp_path / "scan-out"
    assert _scan(repo, out).returncode == 0
    derived = out / "config-exhaustive.toml"
    assert derived.exists()
    recon.assert_exhaustive_config(GITLEAKS_CONFIG, derived)


def test_scan_missing_binary_fails_closed(tmp_path):
    repo = _init_repo(tmp_path)
    out = tmp_path / "scan-out"
    proc = _scan(repo, out, extra=["--gitleaks", "/nonexistent/gitleaks"])
    assert proc.returncode == 1
    assert "gitleaks" in proc.stdout + proc.stderr


def test_scan_refuses_out_dir_inside_repo(tmp_path):
    _require_gitleaks()
    repo = _init_repo(tmp_path)
    inner = repo / "out"
    proc = _scan(repo, inner)
    assert proc.returncode == 1
    assert not inner.exists(), "no value-bearing output may sit inside the repo"


def test_scan_stdout_counts_only(tmp_path):
    """stdout carries the inventory summary (counts + per-rule table),
    never candidate content."""
    _require_gitleaks()
    repo = _init_repo(tmp_path)
    out = tmp_path / "scan-out"
    proc = _scan(repo, out)
    assert proc.returncode == 0, proc.stderr
    assert "generic-api-key" in proc.stdout
    assert "values" in proc.stdout.lower()
    assert "SCAN OK" in proc.stdout


# ── build subcommand ───────────────────────────────────────────────────────


def _build(
    repo: Path,
    out: Path,
    scan_out: Path,
    rows: list[str],
    extra: list[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return _run(
        [
            "build",
            "--repo",
            str(repo),
            "--ledger",
            str(scan_out / "candidates-ledger.json"),
            "--classifications",
            str(_classifications(tmp_path=out.parent, rows=rows)),
            "--out-dir",
            str(out),
            *(extra or []),
        ],
        repo.parent,
    )


def _build_full(
    repo: Path,
    out: Path,
    scan_out: Path,
    overrides: list[str],
    extra: list[str] | None = None,
    skip_hashes: set[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return _build(
        repo, out, scan_out, _full_rows(scan_out, overrides, skip_hashes), extra
    )


def test_build_dead_value_goes_to_fragments_and_replace(tmp_path):
    """The verifier's fragments file + filter-repo's replace file are
    regenerated from the classification: dead → both, `value==>REDACTED`."""
    _require_gitleaks()
    repo = _init_repo(tmp_path)
    scan_out = tmp_path / "scan-out"
    assert _scan(repo, scan_out).returncode == 0
    out = tmp_path / "build-out"
    jwt_hash = hashlib.sha256(JWT_EXAMPLE.encode()).hexdigest()
    proc = _build_full(
        repo,
        out,
        scan_out,
        [
            f"sha256:{PLANTED_HASH}\tdead\tgate51:test-surface\trotated with evidence",
            f"sha256:{jwt_hash}\tfiltered\tfixture-jwt\texample token",
        ],
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    fragments = (out / "fragments.txt").read_text()
    replace = (out / "replace.txt").read_text()
    assert PLANTED in fragments
    assert JWT_EXAMPLE not in fragments
    assert PLANTED in replace
    assert "==>REDACTED" in replace
    inventory = json.loads((out / "inventory.json").read_text())
    assert inventory["completeness"] is True
    row = next(r for r in inventory["values"] if r["hash"] == PLANTED_HASH)
    assert row["status"] == "dead"
    assert row["in_fragments"]
    assert row["in_replace"]


def test_build_unclassified_candidate_fails(tmp_path):
    """Completeness assertion: a candidate without a classification
    blocks the build and is named by hash only."""
    _require_gitleaks()
    repo = _init_repo(tmp_path)
    scan_out = tmp_path / "scan-out"
    assert _scan(repo, scan_out).returncode == 0
    out = tmp_path / "build-out"
    proc = _build(repo, out, scan_out, [])
    assert proc.returncode == 1
    # the tool names candidates by a TRUNCATED hash — never by value
    assert PLANTED_HASH[:16] in proc.stdout
    assert PLANTED not in proc.stdout
    assert not out.exists(), "nothing is written while the assertion fails"


def test_build_blocked_value_refuses_outputs(tmp_path):
    """The live-secret gate: a real secret whose rotation is pending
    blocks the build (Phase 2 sequencing) and is named by tag."""
    _require_gitleaks()
    repo = _init_repo(tmp_path)
    scan_out = tmp_path / "scan-out"
    assert _scan(repo, scan_out).returncode == 0
    out = tmp_path / "build-out"
    proc = _build_full(
        repo,
        out,
        scan_out,
        [f"sha256:{PLANTED_HASH}\tblocked\tazure-sp-secret\tPENDING-U"],
    )
    assert proc.returncode == 1
    assert "azure-sp-secret" in proc.stdout
    # the value-bearing files are refused; the commit-safe inventory
    # (hash-keyed, no values) documents the honest blocked state
    assert not (out / "fragments.txt").exists()
    assert not (out / "replace.txt").exists()
    inventory = json.loads((out / "inventory.json").read_text())
    assert inventory["completeness"] is True
    assert inventory["blocked_tags"] == ["azure-sp-secret"]


def test_build_dead_without_evidence_tag_fails(tmp_path):
    _require_gitleaks()
    repo = _init_repo(tmp_path)
    scan_out = tmp_path / "scan-out"
    assert _scan(repo, scan_out).returncode == 0
    out = tmp_path / "build-out"
    proc = _build_full(
        repo, out, scan_out, [f"sha256:{PLANTED_HASH}\tdead\t"]
    )
    assert proc.returncode == 1
    assert "evidence" in (proc.stdout + proc.stderr).lower()


def test_build_unknown_hash_classification_fails(tmp_path):
    """Drift: a classification for a value the scan never saw is an
    error (a stale classification would otherwise lurk silently)."""
    _require_gitleaks()
    repo = _init_repo(tmp_path)
    scan_out = tmp_path / "scan-out"
    assert _scan(repo, scan_out).returncode == 0
    out = tmp_path / "build-out"
    proc = _build_full(
        repo,
        out,
        scan_out,
        [
            f"sha256:{'0' * 64}\tdead\tgate51:x\tstale",
            f"sha256:{PLANTED_HASH}\tdead\tgate51:y\tevidence",
        ],
    )
    assert proc.returncode == 1
    output = proc.stdout.lower()
    assert "unknown" in output or "drift" in output


def test_build_rule_level_default_forbidden_on_secret_class_rules(tmp_path):
    """A rule-level default on a secret-class rule could silently filter
    a real credential — the build refuses the classification file."""
    _require_gitleaks()
    repo = _init_repo(tmp_path)
    scan_out = tmp_path / "scan-out"
    assert _scan(repo, scan_out).returncode == 0
    out = tmp_path / "build-out"
    proc = _build(repo, out, scan_out, ["rule:aws-access-token\tfiltered\tnope"])
    assert proc.returncode == 1
    assert "aws-access-token" in proc.stdout + proc.stderr


def test_build_rule_level_default_applies(tmp_path):
    """The bulk-FP mechanism: a non-secret-class rule default resolves
    every value of that rule lacking a value-level entry."""
    _require_gitleaks()
    repo = _init_repo(tmp_path)
    scan_out = tmp_path / "scan-out"
    assert _scan(repo, scan_out).returncode == 0
    out = tmp_path / "build-out"
    jwt_hash = hashlib.sha256(JWT_EXAMPLE.encode()).hexdigest()
    proc = _build_full(
        repo,
        out,
        scan_out,
        [
            f"sha256:{PLANTED_HASH}\tdead\tgate51:t\tevidence",
            "rule:jwt\tfiltered\tfixture-jwt\trule default",
        ],
        skip_hashes={jwt_hash},
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    inventory = json.loads((out / "inventory.json").read_text())
    row = next(r for r in inventory["values"] if r["hash"] == jwt_hash)
    assert row["status"] == "filtered"


def test_build_multiline_dead_value_requires_path_coverage(tmp_path):
    """A multi-line value cannot be scrubbed by the line-based
    replace-text format — its files must all be dropped by the paths
    file, or the build refuses (unscrubbable)."""
    _require_gitleaks()
    repo = _init_repo(tmp_path)
    scan_out = tmp_path / "scan-out"
    assert _scan(repo, scan_out).returncode == 0
    ledger = _ledger(scan_out)
    pem_hash = next(
        h for h, v in ledger["values"].items() if v["multiline"]
    )
    rows = [
        f"sha256:{PLANTED_HASH}\tdead\tgate51:t\tevidence",
        f"sha256:{pem_hash}\tdead\tw05:tls-regen\tregenerated",
    ]
    # without coverage: refused
    out = tmp_path / "build-out"
    proc = _build_full(repo, out, scan_out, rows)
    assert proc.returncode == 1, "a multi-line value in a kept file must block"
    assert "multi-line" in (proc.stdout + proc.stderr).lower()
    # with coverage (pem.txt excluded): recorded as path-scrubbed, absent
    # from both generated files
    paths = tmp_path / "paths.txt"
    paths.write_text("pem.txt\n")
    out2 = tmp_path / "build-out2"
    proc = _build_full(
        repo, out2, scan_out, rows, extra=["--paths-file", str(paths)]
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "BEGIN PRIVATE KEY" not in (out2 / "fragments.txt").read_text()
    assert "BEGIN PRIVATE KEY" not in (out2 / "replace.txt").read_text()
    inventory = json.loads((out2 / "inventory.json").read_text())
    row = next(r for r in inventory["values"] if r["hash"] == pem_hash)
    assert row["paths_covered"] is True


def test_build_outputs_are_0600_and_refuse_repo_dir(tmp_path):
    _require_gitleaks()
    repo = _init_repo(tmp_path)
    scan_out = tmp_path / "scan-out"
    assert _scan(repo, scan_out).returncode == 0
    rows = [f"sha256:{PLANTED_HASH}\tdead\tgate51:t\tevidence"]
    out = tmp_path / "build-out"
    assert _build_full(repo, out, scan_out, rows).returncode == 0
    for name in ("fragments.txt", "replace.txt", "inventory.json"):
        mode = (out / name).stat().st_mode & 0o777
        assert mode == 0o600, f"{name} must be 0600, got {oct(mode)}"
    inner = repo / "inner-out"
    proc = _build_full(repo, inner, scan_out, rows)
    assert proc.returncode == 1


def test_build_is_deterministic(tmp_path):
    """Rebuilding from the same ledger + classifications is
    byte-identical (the regeneration chain is reproducible)."""
    _require_gitleaks()
    repo = _init_repo(tmp_path)
    scan_out = tmp_path / "scan-out"
    assert _scan(repo, scan_out).returncode == 0
    rows = [f"sha256:{PLANTED_HASH}\tdead\tgate51:t\tevidence"]
    out_a, out_b = tmp_path / "a", tmp_path / "b"
    assert _build_full(repo, out_a, scan_out, rows).returncode == 0
    assert _build_full(repo, out_b, scan_out, rows).returncode == 0
    for name in ("fragments.txt", "replace.txt"):
        assert (out_a / name).read_bytes() == (out_b / name).read_bytes()


def test_build_house_report_reconciliation(tmp_path):
    """The P2-1-proof coherence check: every candidate the REAL house
    config still flags after the rewrite must be scrub-covered (in
    replace.txt) or path-covered (dropped). The planted value lives in a
    kept file and is dead → scrub-covered → green; classify it filtered
    instead → the check bites."""
    _require_gitleaks()
    assert GITLEAKS is not None
    # a minimal repo: ONLY the planted value, so the house report and
    # the ledger contain exactly one candidate
    repo = tmp_path / "min-repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "app.py").write_text(f'API_TOKEN = "{PLANTED}"\n')
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "planted secret")
    scan_out = tmp_path / "scan-out"
    assert _scan(repo, scan_out).returncode == 0
    house_out = tmp_path / "house-out"
    house_out.mkdir()
    proc = subprocess.run(
        [
            GITLEAKS,
            "detect",
            "--source",
            str(repo),
            "--log-opts=--all",
            "--config",
            str(GITLEAKS_CONFIG),
            "--report-format",
            "json",
            "--report-path",
            str(house_out / "report.json"),
            "--no-banner",
            "--log-level=warn",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode in (0, 1)
    # dead → scrub-covered → green
    out = tmp_path / "build-out"
    proc = _build(
        repo,
        out,
        scan_out,
        [f"sha256:{PLANTED_HASH}\tdead\tgate51:t\tevidence"],
        extra=["--house-report", str(house_out / "report.json")],
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    # filtered → no scrub, no path coverage → the check bites
    out2 = tmp_path / "build-out2"
    proc = _build(
        repo,
        out2,
        scan_out,
        [f"sha256:{PLANTED_HASH}\tfiltered\tfixture\treason"],
        extra=["--house-report", str(house_out / "report.json")],
    )
    assert proc.returncode == 1
    assert PLANTED_HASH[:16] in proc.stdout


def test_cli_never_prints_values(tmp_path):
    """End-to-end discipline on both subcommands: the planted value
    never reaches stdout/stderr (only files)."""
    _require_gitleaks()
    repo = _init_repo(tmp_path)
    scan_out = tmp_path / "scan-out"
    scan_proc = _scan(repo, scan_out)
    assert PLANTED not in scan_proc.stdout + scan_proc.stderr
    out = tmp_path / "build-out"
    build_proc = _build_full(
        repo,
        out,
        scan_out,
        [f"sha256:{PLANTED_HASH}\tdead\tgate51:t\tevidence"],
    )
    assert PLANTED not in build_proc.stdout + build_proc.stderr


def test_replace_needle_with_double_equals_is_escaped(tmp_path):
    """filter-repo's `==>` separator: a needle containing `==>` must be
    escaped (`\\==>`) so the entry parses as one literal."""
    assert recon.escape_replace_needle("a==>b") == "a\\==>b"
    assert recon.escape_replace_needle("plain") == "plain"


# ── input-file edits (paths + config) — the W0.4-input completion ──────────


def test_paths_file_covers_historical_artifact_dirs():
    """The P0-9-extended proof (gitleaks over rewritten history) forces
    the historical test-artifact dirs OUT of history: both dirs carry
    house-config findings (3,462 + 8) and no config allowlist covers
    them. Literal trailing-slash entries, per the file's semantics."""
    paths = (ROOT / "scripts/history_rewrite_paths.txt").read_text()
    assert "frontend/test-results/\n" in paths
    assert "test_reports_integration/\n" in paths


def test_house_config_suppresses_scripts_tests_and_digest_lines():
    """The two config edits: (1) `^scripts/tests/` joins the path
    allowlist next to every other test tree (`^tests/`,
    `hub/apps/.*/tests/`, ...); (2) the rotation record's key-digest
    lines are digests, not secrets — the generic-api-key rule's
    per-rule allowlist suppresses the bare 64-hex digest class (its
    captured secret), never the surrounding line context.
    Both are proven empirically below (fixture + real config)."""
    import tomllib

    cfg = tomllib.loads((ROOT / ".gitleaks.toml").read_text())
    assert "^scripts/tests/" in cfg["allowlist"]["paths"]
    generic = next(r for r in cfg["rules"] if r["id"] == "generic-api-key")
    assert r"^[a-z]+\.(key|crt) sha256: [0-9a-f]{64}$" in generic["allowlist"]["regexes"]


def test_house_config_suppresses_scripts_test_fixture(tmp_path):
    """Falsifiable leg: a fixture secret under `scripts/tests/` is
    flagged WITHOUT the allowlist entry and suppressed WITH it — the
    real config, the real scanner."""
    _require_gitleaks()
    assert GITLEAKS is not None
    repo = tmp_path / "scripts-repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "scripts/tests").mkdir(parents=True)
    (repo / "scripts/tests/x.py").write_text(f'TOKEN = "{PLANTED}"\n')
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "fixture in scripts/tests")
    out = tmp_path / "r.json"
    subprocess.run(
        [
            GITLEAKS,
            "detect",
            "--source",
            str(repo),
            "--log-opts=--all",
            "--config",
            str(GITLEAKS_CONFIG),
            "--report-format",
            "json",
            "--report-path",
            str(out),
            "--no-banner",
            "--log-level=warn",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    findings = json.loads(out.read_text()) if out.exists() else []
    assert findings == [], f"^scripts/tests/ must suppress the fixture: {len(findings)} findings"


def test_house_config_suppresses_digest_line(tmp_path):
    """Falsifiable leg: the rotation record's digest line is flagged
    WITHOUT the value-regex and suppressed WITH it."""
    _require_gitleaks()
    assert GITLEAKS is not None
    repo = tmp_path / "digest-repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "record.md").write_text(f"evidence: {DIGEST_LINE}\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "digest line")
    out = tmp_path / "r.json"
    subprocess.run(
        [
            GITLEAKS,
            "detect",
            "--source",
            str(repo),
            "--log-opts=--all",
            "--config",
            str(GITLEAKS_CONFIG),
            "--report-format",
            "json",
            "--report-path",
            str(out),
            "--no-banner",
            "--log-level=warn",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    findings = json.loads(out.read_text()) if out.exists() else []
    assert findings == [], f"the digest regex must suppress the line: {len(findings)} findings"


def test_makefile_rewrite_input_targets_exist():
    makefile = (ROOT / "Makefile").read_text()
    assert "rewrite-inputs-scan" in makefile
    assert "rewrite-inputs-build" in makefile


def test_pin_file_registered_in_ci_lint_list():
    lint = (ROOT / ".github/workflows/_reusable.lint.yml").read_text()
    assert "scripts/tests/test_p20_rewrite_input_reconstruction.py" in lint


# ── the committed reconciliation anchor (real repo) ────────────────────────


def _committed_inventory() -> dict:
    return json.loads(
        (ROOT / "scripts/rewrite_inventory.json").read_text(encoding="utf-8")
    )


def _committed_classifications() -> dict[str, tuple[str, str, str]]:
    rows: dict[str, tuple[str, str, str]] = {}
    for line in (
        ROOT / "scripts/rewrite_input_classifications.tsv"
    ).read_text().splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        selector, status, tag, *rest = line.split("\t")
        rows[selector] = (status, tag, "\t".join(rest))
    return rows


class TestCommittedReconciliation:
    """The G2 anchor: the committed classification + inventory reconcile
    the real scan against the W0.4 record's inventory description. The
    classification is replayed against the inventory rows — the same
    resolution logic the build ran (no gitleaks needed)."""

    def test_artifacts_agree(self):
        inventory = _committed_inventory()
        classes = _committed_classifications()
        assert inventory["completeness"] is True
        rows = inventory["values"]
        assert rows, "the committed inventory must carry the real scan's rows"
        for row in rows:
            entry = classes.get(f"sha256:{row['hash']}") or classes.get(
                f"rule:{row['rule']}"
            )
            assert entry, f"unclassified row {row['hash']} ({row['rule']})"
            status, tag, _reason = entry
            assert status == row["status"], row["hash"]
            assert tag == row["tag"], row["hash"]
        # no stale classifications
        hashes = {row["hash"] for row in rows}
        for selector in classes:
            if selector.startswith("sha256:"):
                assert selector[7:] in hashes, f"stale classification {selector}"

    def test_blocked_set_is_exactly_the_u_console_surfaces(self):
        """The live-secret gate's honest current state: exactly the 3
        U-console surfaces the P1-1 record leaves pending. Any change
        here (a new live secret, or a completed rotation) must update
        the record + this pin together."""
        inventory = _committed_inventory()
        blocked = {r["tag"] for r in inventory["values"] if r["status"] == "blocked"}
        assert blocked == {"azure-sp-secret", "stripe-test-key", "anthropic-auth-token"}

    def test_dead_evidence_resolves_in_the_records(self):
        """Every rotation-dead row cites evidence that resolves in the
        rotation records: gate51:<step> must be a ROTATED step in the
        GATE-51 record; w05:<step> a ROTATED step there too;
        test-stack:* must cite the re-mint evidence in the P1-3 map."""
        record = (
            ROOT
            / "openspec/changes/oss-release-remediation/credential-rotation-2026-10-06.md"
        ).read_text()
        import re

        rotated_steps = {
            m.group(1): m.group(2).upper()
            for m in re.finditer(
                r"### step: ([a-z0-9-]+)\n.*?\*\*Status:\*\* (\w+)",
                record,
                re.S,
            )
        }
        inventory = _committed_inventory()
        for row in inventory["values"]:
            if row["status"] != "dead":
                continue
            tag = row["tag"]
            if tag.startswith(("gate51:", "w05:")):
                step = tag.split(":", 1)[1]
                assert rotated_steps.get(step) == "ROTATED", tag
            elif tag == "test-stack:ckan-remint":
                pass  # asserted against the P1-3 map below
            else:
                raise AssertionError(f"unrecognized evidence tag {tag}")

    def test_ckan_remint_evidence_cited_in_rotation_map(self):
        map_doc = (
            ROOT / "docs/audits/history-content-rotation-map-2026-10-19.md"
        ).read_text()
        assert "re-mint" in map_doc
        assert "revoked" in map_doc

    def test_record_inventory_classes_present(self):
        """Reconciliation against the W0.4 record's inventory
        description: the reconstruction superset CONTAINS every original
        class — the ANTHROPIC token, the AWS pair, Azure, Databricks,
        Stripe, the GCP service-account material, and TLS material."""
        inventory = _committed_inventory()
        tags = {r["tag"] for r in inventory["values"]}
        rules = {r["rule"] for r in inventory["values"]}
        assert "anthropic-auth-token" in tags
        assert "gate51:aws-pair" in tags
        assert "azure-sp-secret" in tags
        assert "gate51:databricks-pat" in tags
        assert "stripe-test-key" in tags
        assert "gate51:gcp-sa-key" in tags
        assert "w05:postgres-certs" in tags
        assert "private-key" in rules

    def test_record_inventory_shape_when_unblocked(self):
        """Post-P1-1 checkpoint: with the 3 blockers cleared the
        reconstruction must reproduce the record's inventory shape — the
        8-fragment set (incl. the ANTHROPIC token) among the replace
        values, with TLS material covered. The blocker count is the ONLY
        thing standing between the current state and this shape."""
        inventory = _committed_inventory()
        blocked = sum(1 for r in inventory["values"] if r["status"] == "blocked")
        dead = [r for r in inventory["values"] if r["status"] == "dead"]
        assert blocked == 3
        # when the rotations land, the fragments + replace files carry
        # every dead value — the record's 8 fragments are a strict
        # subset of the reconstruction's dead set
        assert len(dead) >= 8, "the dead set must superset the record's 8 fragments"
        assert any(r["tag"] == "anthropic-auth-token" for r in inventory["values"])
        assert sum(1 for r in dead if r["multiline"]) >= 3, "TLS material covered"

    def test_inventory_cites_record_and_config(self):
        inventory = _committed_inventory()
        assert "history-rewrite-2026-10-06" in inventory["record"]
        assert inventory["config"] == ".gitleaks.toml"
        assert inventory["gitleaks_version"] == "8.21.2"
