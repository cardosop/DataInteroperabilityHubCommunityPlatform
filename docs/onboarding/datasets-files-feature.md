# Onboarding — Datasets & Files feature pack (Phase 260 / D260.5)

## Malware test fixtures (D260.5 / Phase 260.2.D)

- `tests/fixtures/eicar.txt` contains the **EICAR standard test string**. It is **not** live malware but WILL trip AV engines (ClamAV, Windows Defender, etc.).
- **Do not** run host-resident antivirus recursive scans against the working tree without excluding `tests/fixtures/eicar.txt` (and other test fixtures). Prefer scanning inside **ephemeral** Docker sandboxes (e.g. `clamav-test` in `docker-compose.test.yml`).
- **Backend E2E (pytest):** set `RUN_FILE_VIRUS_SCAN_E2E=1` and start ClamAV with  
  `docker compose -f docker-compose.test.yml --profile clamav-test up -d clamav-test`  
  The API container must reach `CLAMAV_HOST` (default `clamav-test` on `hub-test-net`). Marker: `requires_file_virus_scan_e2e`. Implementation: `hub/apps/files/tests/test_virus_scan_e2e.py`.
- **Playwright:** same env flag — `RUN_FILE_VIRUS_SCAN_E2E=1`; spec: `frontend/e2e/features/file-virus-scan.spec.ts`.
- **Compose image:** `clamav/clamav:1.5` (legacy tags such as `1.3` were removed upstream — keep pinned minor aligned with Helm `clamav.image.tag`).

## CI / runner hygiene

- **GitHub-hosted runners:** Avoid invoking Defender / macOS Gatekeeper full-disk scans over `GITHUB_WORKSPACE` during jobs that materialise `tests/fixtures/eicar.txt`. Prefer leaving detection to isolated compose stacks or nightly workflows that mount fixtures inside ClamAV-only containers.
- **Self-hosted / golden AMI builders:** Add AV exclusions for the repo checkout path **or** for `**/tests/fixtures/eicar.txt` before recursive scans — documented here per Phase 260.2.D.3.
- Phased lint gates and merge-matrix expectations: [`docs/ci/datasets-files-phase260-ci-matrix.md`](../ci/datasets-files-phase260-ci-matrix.md).

## Local development

1. Start MinIO + api stack via compose (`docker-compose.test.yml` or developer profile).
2. Verify presigned uploads against `http://localhost:9010` per Terraform module parity.
3. Read ADR-DSF-002 before editing CORS origins.
