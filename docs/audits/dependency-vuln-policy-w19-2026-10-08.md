# Dependency-Vulnerability Policy Audit — 2026-10-08 (G4 / W1.9)

The G4 deliverables: pip-audit blocks NEW HIGH/CRITICAL on PRs; the
`.trivyignore` backlog triaged; `audit_pinned_cves --strict` green; a
planted-vuln pin that fails the job; triage notes committed.

## 1. pip-audit blocking leg — GREEN, already wired, verified

`scripts/check_dependency_vulns.py` (GATE-47, pilot-readiness 4.2) is the
BLOCKING leg of the `dependency-audit` CI job
(`.github/workflows/ci.yml`, runs on every PR): every pip-audit finding
must be TRIAGED — fixed by a pin bump or allowlisted in
`.pip-audit-allowlist.yaml` with a rationale + review date. An untriaged
finding blocks (severity-independent — a NEW HIGH/CRITICAL is by
definition untriaged → the job fails); an allowlisted entry whose review
date passed blocks again; the full triage list prints, never truncated.

**Verified this pass:** a live `pip-audit -r requirements.txt` run
(2026-10-08) → the gate PASSES against `.pip-audit-allowlist.yaml`
(8 triaged findings, review dates 2026-11-05: DRF 3.16 contract meds,
cryptography 46.x-family major-fix highs, pyarrow<15 pin, oauthlib
transitive). Pins: `scripts/tests/test_check_dependency_vulns.py` —
untriaged vuln → exit 1 (the planted-vuln pin), expired review → exit 1,
full-triage → exit 0, unknown severity treated as blocking, missing
audit-JSON → fail (W16 raises in CI). **8/8** + `test_audit_pinned_cves.py`
**18/18** green.

## 2. .trivyignore backlog triage — 198 dead entries removed

Method: (a) a live Trivy scan of the current image — **0 of the 198
ignored CVEs are still flagged**; (b) the Debian Security Tracker data
(fetched 2026-10-08, 63k CVEs) — **155/198 resolved in the trixie suite**
(the `python:3.12-slim` base's suite); (c) Category-C count — **zero
Category-C entries** (only the header definition); every old entry was
Category-A/B and has since been fixed by trixie updates. The whole
backlog was removed.

## 3. Fresh triage wave — the new .trivyignore (94 entries, all dated)

Each entry verified against TODAY's fresh build chain, not the stale
local image:

| Layer | Method | Result |
|---|---|---|
| Base image | `python:3.12-slim` pulled 2026-10-08, scanned | 41 CVEs (7 HIGH, 34 MEDIUM) |
| apt layer | docker-built from the fresh base with the EXACT `services/api/Dockerfile` apt install, scanned | +46 CVEs → **87 OS CVEs total** (1 CRITICAL: CVE-2026-6653 libxml2, no trixie fix; build-only packages annotated Category-A, the rest Category-B "open in trixie per the Debian tracker") |
| docker-cli layer | **REMEDIATED, zero entries needed** — Dockerfile bumped docker-cli 27.3.1 → **29.8.2** + compose v2.29.1 → **v2.40.3** (the pre-bump binaries carried the whole Go/docker CVE cluster); the bumped pair scans CLEAN (verified locally on the exact binaries) |
| pip layer | trivy DB fix-versions at the current requirements.txt pins | 7 entries (cryptography ×3, DRF ×2, oauthlib ×2 — major-version-only fixes, mirroring the pip-audit allowlist rationales + review dates 2026-11-05). Transitive unpinned packages resolve to fixed versions at fresh install (GitPython→3.1.60, anyio→4.14.2, aiohttp, sqlparse, urllib3, snowflake, pillow, nltk — all verified fixed-by-resolve) |

**Verification:** re-scan of the apt-layer image WITH the new ignorefile →
**0 remaining findings** (a first pass caught a trivy-DB nondeterminism —
CVE-2025-69720 ncurses appeared in one run and not the other; the union
of two clean scans was taken, so the ignore set is exact against both).
`scripts/audit_pinned_cves.py --strict` → **exit 0** (was exit 1 with 198
overdue entries). Every entry carries an `Added:` + `Review by:` date
(2027-01-06 OS, 2026-11-05 pip) and a Category + rationale.

## 4. Deploy gate alignment

The deploy Trivy gate blocks CRITICAL,HIGH (`.github/workflows/deploy.yml`,
unconditional exit-code gate — the W11.10 audit corrected the pre-fix
MEDIUM+ claim here; MEDIUM is carried in the triage backlog instead). With the triage file verified against the
fresh build chain, the next deploy scan sees only the 94 triaged entries
(each with a rationale + review date) — the sanctioned exception path.

## 5. Follow-ups (recorded, review-dated)

* `docker compose` v5 line exists (v5.6.0) — the in-container Compose
  integration tests kept the plugin on v2.40.3; the v5 migration is its
  own lane (the compose-go CVE cluster is gone at v2.40.3 already).
* DRF 3.16 → 3.17.2 and cryptography 46.x → 48+/49+/50.0.0 are
  major/minor migrations tracked by the 2026-11-05 review dates.
* Multi-stage Dockerfile (build-only `gcc`/`unixodbc-dev` currently ship
  in the runtime image) — the Category-A entries that would vanish with
  it are annotated as such.
