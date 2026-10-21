# W11.8 — ASVS V12 File-Upload Abuse Matrix

**Change:** `openspec/changes/oss-release-remediation` — W11.8
**Date:** 2026-10-16
**Register rows closed:** 3 (XSS via unsafe output sinks — the unicode/overlong
filename half) and 14 (path traversal / file-upload validation gaps — the
magic-byte, content-type, zip, oversized, presigned-replay half)
**ASVS mapping:** V12.1 (size/type/content validation), V12.2 (archive
validation), V12.3 (filename sanitization), V12.5 (malware/content checks),
V1.12.2 (atomic file handling — the staging copy).

Every cell carries ONE named test against the REAL stack (real MinIO, real
presigned URLs, real HTTP — no mocks; the storage guard follows the
files-suite convention). Verified mechanically by
`scripts/tests/test_w118_upload_abuse_veracity.py`.

| # | Abuse class | Named test | Expected |
|---|---|---|---|
| 1.1 | Magic-byte bypass — PE payload declared `text/csv` (view-level complete) | `hub/apps/files/tests/test_w118_upload_abuse.py::UploadAbuseViewTest::test_magic_byte_bypass_pe_as_csv_rejected_at_complete` | 400 `FILE_FORMAT_MISMATCH`, row FAILED, object deleted (no orphan) |
| 1.2 | Magic-byte — every binary disguise prefix rejected (unit, parametrized) | `hub/apps/files/tests/test_magic_bytes.py::test_each_binary_prefix_rejected_for_text_csv` | `FILE_FORMAT_MISMATCH` |
| 1.3 | Magic-byte default-ON (settings) | `test_magic_bytes.py::TestDefaultEnabled::*` | gate fires under the default |
| 2.1 | Content-type spoof — ZIP payload declared `text/csv` | `hub/apps/files/tests/test_w118_upload_abuse.py::UploadAbuseViewTest::test_content_type_spoof_zip_as_csv_rejected` | 400 `FILE_FORMAT_MISMATCH` |
| 2.2 | Content-type spoof — compliance-service PK prefixes | `services/compliance-service/tests/test_file_type_validation.py::TestBannedBinaryPrefixes` | 415 |
| 3.1 | Zip-bomb / zip-slip — NO extraction exists anywhere (AST gate over the non-test tree) | `scripts/tests/test_w118_upload_abuse_veracity.py::test_no_archive_extraction_anywhere_in_the_non_test_tree` | zero `extractall`/`ZipFile.extract`/`unpack_archive`/`tarfile.open`-read sites |
| 3.2 | The one read-side ZipFile is namelist/read-only | `test_the_drill_script_zip_is_namelist_read_only` | pinned |
| 3.3 | Worker inference rejects archive extensions | `hub/apps/files/tests/test_w118_upload_abuse.py::IngestionFormatGateTest::test_worker_inference_rejects_archive_extensions` | `.zip/.gz/.tar/.exe` → None (rejected) |
| 3.4 | Legacy workflow had a CSV-default gap — now strict | `IngestionFormatGateTest::test_legacy_workflow_has_no_csv_default` | source pin: the default is gone, strict inference live |
| 3.5 | Dataset format map had a CSV-default gap — now exhaustive + typed rejection | `IngestionFormatGateTest::test_dataset_format_map_has_no_csv_default` | source pin: no default, xlsx MIMEs mapped, `UNSUPPORTED_FORMAT` on unresolvable pairs |
| 4.1 | Oversized — validator + init-API | `hub/apps/files/tests/test_file_size_limits.py` | SDK/global/browser caps enforced, multipart exemption bounded |
| 4.2 | Oversized — worker internal path | `hub/apps/scheduled_ingestion/tests/test_internal_worker_api.py::InternalWorkerFileHardeningTest::test_oversized_file_rejected` | 400 `FILE_TOO_LARGE` |
| 5.1 | Unicode names — overlong (300-char) rejected, never silently truncated | `hub/apps/files/tests/test_w118_upload_abuse.py::UploadAbuseViewTest::test_unicode_overlong_and_rtl_names_roundtrip` | 400 `VALIDATION_ERROR` |
| 5.2 | Unicode names — RTL/bidi name roundtrips init → detail | (same test) | 201 + byte-identical name |
| 5.3 | Unicode names — NFC normalization + 8 locale scripts | `hub/apps/files/tests/test_locale_filename_roundtrip.py` | roundtrip |
| 5.4 | Traversal names — `../../etc/passwd`, backslash, null byte | `hub/apps/files/tests/test_file_security.py` | rejected / basename-only |
| 6.1 | **Presigned replay — re-PUT after completion cannot serve as CLEAN** (the W1.12 fix, shipped in this change) | `hub/apps/files/tests/test_presigned_replay_w112.py::PresignedReplayPinTest::test_replay_put_after_completion_cannot_serve_as_clean` | final key serves the verified content; the replay is an orphan staging object |
| 6.2 | Multipart part-URL replay dead after compose | `test_multipart_part_url_replay_cannot_touch_final_key` | part URL rejected; final key untouched |
| 6.3 | Production fails closed on a missing staging object | `test_completion_without_staging_object_fails_closed_in_production` | 400 `FILE_OBJECT_MISSING` |
| 6.4 | Staging design live in source | `scripts/tests/test_w118_upload_abuse_veracity.py::test_staging_design_is_live_in_the_source` | `upload_staging_key` + `copy_object` + the two new codes |
| 7.1 | Production-deploy magic-byte posture | `test_helm_and_settings_magic_byte_posture_agree` | settings default True AND helm `"true"` (the pre-fix helm `"false"` finding) |

## Root fixes shipped by this suite (TDD, RED-first)

1. **Presigned-replay (W1.12/R2-S5) — the fix was ABSENT, the pins RED.** The
   presigned URL covered the FINAL storage key: a replayed PUT after completion
   overwrote the scanned CLEAN object. The staging-key design is now LIVE:
   `init_upload` presigns a staging key (`{storage_path}.staging`, recorded in
   `metadata_json["upload_staging_key"]`), multipart parts/compose run on the
   staging key, `complete_upload` verifies (existence/size/SHA/magic-bytes) the
   staging object and the SERVER copies staging → final (`S3StorageClient.copy_object`)
   then deletes the staging object — the client's write capability dies with it.
   Production fails closed with the new `FILE_OBJECT_MISSING`; copy failure is
   the new `STORAGE_COPY_FAILED` (both catalogued). The three committed-but-RED
   pins went GREEN.
2. **helm shipped `MAGIC_BYTE_VALIDATION_ENABLED: "false"`** while the Python
   default was True — production silently ran with the gate off. Flipped to
   `"true"` + the agreement pin (settings default AND helm value).
3. **Legacy orchestration workflow defaulted unknown extensions to CSV**
   (the register row 14 class — `.zip`/`.exe` silently garbage-parsed). Now the
   strict `_infer_format_from_path` + typed rejection (the W1.14 worker
   contract).
4. **Dataset-creation format map defaulted unmapped content types to CSV**
   (an xlsx-declared file was inferred CSV). The map is now exhaustive
   (xlsx/xls MIMEs added), the filename is the fallback, and an unresolvable
   pair is rejected `UNSUPPORTED_FORMAT` — never silently defaulted.

## Recorded (not fixed — deliberate)

* The browser-PUT presigned branch ignores `max_size` at S3 (the POST branch
  has `content-length-range`); the server-side complete-time size check
  (stored_size vs declared → 400 + delete) is the enforcement.
* Magic-byte storage-read failures FAIL OPEN (warned) — the SHA-256 full-content
  compare earlier in the same request covers integrity; the trade-off is
  documented in `magic_bytes.py`.
* XLSX/XLS are zip containers parsed in-memory by openpyxl/pandas, bounded by
  the 1GB inference cap — no extraction, no zip-slip surface.
