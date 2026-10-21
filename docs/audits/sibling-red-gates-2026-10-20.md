# Sibling-Red-Gates Re-Run — P3-2 Battery Record (2026-10-20)

`openspec/changes/close-oss-release-conditions` — P3-2 (condition
`sibling-red-gates`) EXECUTED 2026-10-20. The W10.1 full-CI attribution
recorded GATE-05/06/07/54/58/59 + the ZAP AUDITOR baseline RED as
in-flight sibling-lane state; this is the re-run after those lanes
landed (W11.3/W12.5/W12.10/W11.11 + the 2026-10-18/20 consolidations).

## The battery (all green, same session)

| Gate | Script | Result |
|------|--------|--------|
| GATE-05 | `check_time_sleep_in_tests.py` | PASS — 424 sleep calls, 0 unannotated |
| GATE-06 | `check_no_reverse_match.py` | PASS (after the root fix below) |
| GATE-07 | `check_pytest_skip_in_body.py` | PASS — no in-body `pytest.skip()` |
| GATE-54 | `check_provider_boundary.py` | PASS — boundary clean |
| GATE-54 growth | `--check-allowlist-growth` | PASS — allowlist only shrinks |
| GATE-58 check | `check_exception_ratchet.py --check` | PASS — 2,161 sites, 0 bare excepts |
| GATE-58 growth | `--check-growth` | PASS (vs the reviewed re-baseline) |
| GATE-58 noqa | `--check-noqa` | PASS — 1,046 noqas recorded |
| GATE-58 noqa growth | `--check-noqa-growth` | PASS |
| GATE-59 | `check_orphan_scripts.py --check` | PASS — 133 wired / 56 deleted |
| GATE-64 (ZAP AUDITOR) | `check_zap_delta.py --verify-baselines` | PASS — TENANT_ADMIN 125 / DATA_PROVIDER 144 / DATA_CONSUMER 28 / AUDITOR 145 alert-identity pairs |

Pin suites re-run green in the same session:
`test_check_exception_ratchet.py` 25/25,
`test_check_time_sleep_in_tests.py`,
`test_check_provider_boundary.py`,
`test_check_orphan_scripts.py` (65 passed combined, 0 failed).

## Root fixes landed (RED → GREEN, not suppressed)

1. **GATE-06** — `tests/security/test_w113_asvs_v4_access_control.py`:
   the matrix's `try/except NoReverseMatch` URL-builder fallback was
   DEAD CODE — no matrix route ever sets `url_mode="reverse"` (the
   only two `url_mode` references in the file are the check itself and
   the probe-dict pass-through), so the branch could never run.
   Removed per the gate's philosophy (URL-name bugs surface); the
   `NoReverseMatch`/`reverse` import went with it.
2. **GATE-58** — both baselines rotted under the 2026-10-18/20
   consolidations (40 dead noqa anchors + moved file paths). Every new
   site was reviewed and classified before the sanctioned `--update`:
   BLE001 boundary catches (the Phase-273 best-effort audit contract,
   cache/metrics boundaries — the repo's own CLAUDE.md pattern),
   PLR0911 complexity suppressions, F401/E402/N802 test conventions,
   UP017 datetime deprecations. Net: the noqa baseline SHRINKS by 10
   files (dead anchors outnumber new sites); the exception baseline
   records the 8 reviewed boundary sites (command_audit,
   deduplication, idor_inventory, generate_idor_probes,
   files/throttles + one each in auth/views, baas/throttles,
   webhooks/service). The pre-commit growth signal was the review
   trigger; post-commit the CI growth legs compare against this
   reviewed baseline.
3. **GATE-59** was already green (the P2-5 lane wired
   `check_public_resync_diff.py` + restored the P2-4 anchor earlier
   the same day) — re-run and recorded here.

## Attribution of the original W10.1 redness (for the ledger)

- GATE-54: resolved 2026-10-18 (P0-4 — the IDOR estate import rides
  the registry-inversion seam) — re-run green here.
- GATE-05: resolved 2026-10-18 (P0-5 — 21 sleeps annotated) — re-run
  green here.
- GATE-06/07: the W10.1 skip sites in sibling files; GATE-06's last
  remaining site was the dead branch removed above.
- GATE-58/59: the W12.3/W12.5 ratchets — re-baselined above after the
  consolidations; GATE-59 green.
- ZAP AUDITOR baseline: the W11.11 baselines verify against the
  current tree.

Condition `sibling-red-gates`: CLOSED with this record. The ledger row
flips to executed-with-citation.
