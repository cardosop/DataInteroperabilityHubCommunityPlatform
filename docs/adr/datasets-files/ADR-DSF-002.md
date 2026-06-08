# ADR-DSF-002 — Upload surface & CORS allow-list posture

**Status**: Accepted (Phase 260.0)

## Decision

SPA presigned uploads hit the Terraform `hub-files-*` bucket (`aws_s3_bucket_cors_configuration.files` in [`infrastructure/terraform/modules/s3-buckets/main.tf`](../../../infrastructure/terraform/modules/s3-buckets/main.tf)); `file_storage.tf` is not used.

## Consequences

Origins are variable-driven; infra changes pair with security review.

