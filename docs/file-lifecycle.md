# File Lifecycle

## Purpose

Define the canonical state machine for `File.status` and the contract for
callers that consume uploaded files (including data-first asset creation).

## States

- `PENDING`: file record created; upload has not started.
- `UPLOADING`: multipart upload in progress.
- `COMPLETED`: upload finalized successfully (canonical terminal success state).
- `ACTIVE`: legacy success state retained for backward compatibility.
- `FAILED`: upload/verification failure.
- `DELETED`: file retired or removed.

## Canonical Success State

`COMPLETED` is the canonical success state for newly completed uploads.
`ACTIVE` is treated as a legacy alias during migration windows only.

## Transition Rules

- `PENDING -> UPLOADING` for multipart upload start.
- `PENDING -> COMPLETED` for single-part upload completion.
- `UPLOADING -> COMPLETED` for multipart completion.
- `PENDING|UPLOADING -> FAILED` on terminal upload failure.
- `COMPLETED|ACTIVE|FAILED -> DELETED` on delete/retire actions.

## Data-First Contract

`POST /api/v1/assets/data-first/` accepts only files with
`status == COMPLETED`. Files still in `ACTIVE` are considered legacy and must
be migrated/backfilled.
