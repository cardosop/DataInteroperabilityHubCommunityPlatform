# Phase 232 privacy-counsel sign-off ledger

**Phase:** 232.DoD.1 (closure of `D232.14` privacy-review gate)
**Owner:** DPO (custodian) / EM (approver)
**Last reviewed:** 2026-05-05

Phase 232.DoD.1 conditions production rollout on Legal Counsel + DPO
sign-off for each subsystem's user-facing copy / templates. This is the
authoritative in-repo record of those attestations; the
[scripts/check_phase232_production_flip_gate.py](../../scripts/check_phase232_production_flip_gate.py)
machine-enforces the gate at PR time so a `compliance_*_enabled=True`
flag flip in production helm values cannot land before the matching
attestation is recorded here.

## Schema (machine-readable)

The gate script parses this file by anchor — each subsystem block must
start with the `## Subsystem: <name>` heading shown below, and must
contain the structured fields (`status`, `legal_signoff`, `dpo_signoff`,
`commit`) verbatim. Adding free-form prose around them is fine.

`status` is one of:

* `signed-off` — both signatures present + dated; gate allows the
  production flip.
* `pending` — review in progress; gate blocks the production flip.
* `rejected` — review found a blocking issue; gate blocks until status
  flips back to `signed-off` after re-review.

`commit` is the git short-SHA of the PR/commit that landed the
artefact reviewed (banner copy / template / form). When the artefact
changes after the sign-off, the status MUST drop back to `pending`.

## Sub-phase mapping

| Sub-phase | Subsystem | Artefact reviewed | Tasks.md row |
|---|---|---|---|
| `consent` | 232.1 Consent management | `frontend/packages/meshant-consent-banner/ConsentBanner.tsx` (banner copy + flow) | 232.1.14 |
| `dsar` | 232.2 DSAR workflow | `/legal/dsar` public form + response packaging templates | 232.2.20 |
| `breach` | 232.3 Breach notification | per-regulator notification templates in `hub/apps/breach/` | 232.3.18 |
| `ropa` | 232.4 RoPA generator | per-regulation RoPA templates (PDF/CSV/JSON/DOCX) | 232.4.17 |
| `dpia` | 232.5 DPIA tooling | DPIA wizard template + reviewer prompts | 232.5.13 |

## Subsystem ledger

### Subsystem: consent

```
status: pending
legal_signoff:
  name: _to be filled_
  date: _YYYY-MM-DD_
  evidence: _PR review approval URL or transcribed attestation_
dpo_signoff:
  name: _to be filled_
  date: _YYYY-MM-DD_
  evidence: _link_
commit: _short-SHA of the latest banner-copy commit reviewed_
```

Production-flip gate keys: `compliance_consent_enabled`,
`compliance_consent` (capability).

### Subsystem: dsar

```
status: pending
legal_signoff:
  name: _to be filled_
  date: _YYYY-MM-DD_
  evidence: _link_
dpo_signoff:
  name: _to be filled_
  date: _YYYY-MM-DD_
  evidence: _link_
commit: _short-SHA_
```

Production-flip gate key: `compliance_dsar_enabled`.

### Subsystem: breach

```
status: pending
legal_signoff:
  name: _to be filled_
  date: _YYYY-MM-DD_
  evidence: _link_
dpo_signoff:
  name: _to be filled_
  date: _YYYY-MM-DD_
  evidence: _link_
commit: _short-SHA_
```

Production-flip gate key: `compliance_breach_enabled`.

### Subsystem: ropa

```
status: pending
legal_signoff:
  name: _to be filled_
  date: _YYYY-MM-DD_
  evidence: _link_
dpo_signoff:
  name: _to be filled_
  date: _YYYY-MM-DD_
  evidence: _link_
commit: _short-SHA_
```

Production-flip gate key: `compliance_ropa_enabled`.

### Subsystem: dpia

```
status: pending
legal_signoff:
  name: _to be filled_
  date: _YYYY-MM-DD_
  evidence: _link_
dpo_signoff:
  name: _to be filled_
  date: _YYYY-MM-DD_
  evidence: _link_
commit: _short-SHA_
```

Production-flip gate key: `compliance_dpia_enabled`.

## Maintenance

* **Adding a subsystem**: add a new `## Subsystem: <name>` block AND add
  a row to the sub-phase mapping. Update the gate script's
  `SUBSYSTEM_TO_FLAGS` table to map the new subsystem to the matching
  helm flag.
* **Re-review after artefact change**: if a banner / template changes
  after sign-off, drop `status` back to `pending`. The gate script
  will block production flips until the new commit-SHA review is
  recorded.
* **Removing**: don't. Keep history; if a subsystem is sunset, set its
  status to `signed-off` with a note attesting the artefact has been
  removed from production.
