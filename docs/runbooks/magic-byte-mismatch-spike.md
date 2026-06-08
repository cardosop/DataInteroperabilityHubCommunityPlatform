# Magic-byte mismatch spike

## Detection

Sudden uptick of `datasets_files_magic_byte_mismatch_total` alerts.

## Response

1. Correlate releases / upstream publisher changes.
2. Validate MIME sniff library version pinned in compliance microservice.
3. Sample offending uploads into isolated bucket for DFIR.

## Maintenance

- **Owner**: Platform Engineering
- **Last reviewed**: 2026-05-13
- **Next review**: 2026-08-11
