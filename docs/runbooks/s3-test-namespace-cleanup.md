# S3 test data namespace hygiene (Phase 260.0.24)

## Convention

Automated uploads from Playwright/pytest SHOULD prefix keys with `e2e-<RUN_ID>/` propagated via env `AWS_S3_TEST_PREFIX`.

## Garbage collection

Operators run a nightly job (or cron task) invoking `aws s3api list-objects-v2 --prefix e2e-` + delete markers for objects older than **24h** in non-prod buckets.

## Safety

Never target `hub-files-prod-*` prefixes from cleaning scripts. Dry-run with `--page-size 100` first.

## Implementation note

Hook this task into the next Phase 260.1 automation PR once presign helper exposes shared prefix builder.

## Maintenance

- **Owner**: Platform Engineering
- **Last reviewed**: 2026-05-13
- **Next review**: 2026-08-11
