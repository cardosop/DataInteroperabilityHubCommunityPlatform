# Image Remediation Record — P2-6 (G5)

Affected-image remediation evidence (close-oss-release-conditions). Input: docs/operations/image-context-audit-2026-10-19.md.

## Rotation gate (GATE-65)

REFUSED — the rotation gate is red:
- FAIL: class 'azure-sp-secret' is PENDING — dead-value evidence required before Phase 2
- FAIL: class 'stripe-test-key' is PENDING — dead-value evidence required before Phase 2
- FAIL: class 'anthropic-auth-token' is PENDING — dead-value evidence required before Phase 2

## Rotation window close

NOT SET — every published version is pre-rotation (affected)

## Execution: REFUSED_ROTATION_GATE

### datainteroperabilityhub-api-service

ENUMERATION FAILED: gh api failed for package 'datainteroperabilityhub-api-service': gh: You need at least read:packages scope to get a package's versions. (HTTP 403)

### datainteroperabilityhub-compliance-service

ENUMERATION FAILED: gh api failed for package 'datainteroperabilityhub-compliance-service': gh: You need at least read:packages scope to get a package's versions. (HTTP 403)

### datainteroperabilityhub-datacontract-service

ENUMERATION FAILED: gh api failed for package 'datainteroperabilityhub-datacontract-service': gh: You need at least read:packages scope to get a package's versions. (HTTP 403)

### datainteroperabilityhub-dq-service

ENUMERATION FAILED: gh api failed for package 'datainteroperabilityhub-dq-service': gh: You need at least read:packages scope to get a package's versions. (HTTP 403)

### datainteroperabilityhub-frontend

ENUMERATION FAILED: gh api failed for package 'datainteroperabilityhub-frontend': gh: You need at least read:packages scope to get a package's versions. (HTTP 403)

### datainteroperabilityhub-inference-service

ENUMERATION FAILED: gh api failed for package 'datainteroperabilityhub-inference-service': gh: Package not found. (HTTP 404)

### datainteroperabilityhub-prefect-integration-service

ENUMERATION FAILED: gh api failed for package 'datainteroperabilityhub-prefect-integration-service': gh: You need at least read:packages scope to get a package's versions. (HTTP 403)

### datainteroperabilityhub-product-site

ENUMERATION FAILED: gh api failed for package 'datainteroperabilityhub-product-site': gh: You need at least read:packages scope to get a package's versions. (HTTP 403)

### datainteroperabilityhub-semantic-service

ENUMERATION FAILED: gh api failed for package 'datainteroperabilityhub-semantic-service': gh: You need at least read:packages scope to get a package's versions. (HTTP 403)

### datainteroperabilityhub-worker-service

ENUMERATION FAILED: gh api failed for package 'datainteroperabilityhub-worker-service': gh: You need at least read:packages scope to get a package's versions. (HTTP 403)

