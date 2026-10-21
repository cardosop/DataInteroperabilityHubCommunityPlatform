# Meshant MVP Personas

This document defines the 13 personas used in Meshant's user journey framework (D145). Each persona maps to a set of roles in the RBAC system and drives specific E2E test journeys.

## Core Personas (MVP)

### 1. First-Time Visitor (FTV)
Unauthenticated user exploring the platform. Can view public marketplace listings and register for an account.
- **Roles**: none (unauthenticated)
- **Journeys**: JOURNEY-AUTH-001 (Register), JOURNEY-AUTH-004 (Public Resources)

### 2. Authenticated User (AU)
Basic authenticated user with default permissions. Starting point for all registered users.
- **Roles**: `USER`
- **Journeys**: JOURNEY-AUTH-002 (Login), JOURNEY-AUTH-003 (Password Reset)

### 3. Data Provider / Owner (DPO)
Creates, publishes, and manages data assets. The primary data-producing persona.
- **Roles**: `USER`, `DATA_PROVIDER`
- **Journeys**: JOURNEY-DPO-001 (Onboard Asset), JOURNEY-DPO-002 (Publish to Marketplace), JOURNEY-DPO-003 (Asset Lifecycle), JOURNEY-DPO-004 (Quality Monitoring), JOURNEY-DPO-005 (Data Contracts), JOURNEY-DPO-006 (Marketplace Listings)

### 4. Data Consumer (DC)
Discovers and subscribes to data assets via the marketplace. Reads data via contracts.
- **Roles**: `USER`, `DATA_CONSUMER`
- **Journeys**: JOURNEY-DC-001 (Discover Assets), JOURNEY-DC-002 (Subscribe to Asset)

### 5. Data Engineer (DE)
Programmatic user who interacts via CLI/SDK. Builds pipelines and configures quality/compliance.
- **Roles**: `USER`, `DATA_ENGINEER`
- **Journeys**: JOURNEY-DE-001 (Contract-First Onboarding), JOURNEY-DE-003 (Data Quality), JOURNEY-DE-004 (Compliance Scanning)

### 6. Compliance Officer (CPO)
Reviews compliance scan results, manages retention policies, handles GDPR requests.
- **Roles**: `USER`, `COMPLIANCE_OFFICER`
- **Journeys**: JOURNEY-CPO-001 (Compliance Scan), JOURNEY-CPO-006 (Automated Compliance), JOURNEY-CPO-007 (Right to be Forgotten), JOURNEY-CPO-008 (Consent Tracking), JOURNEY-CPO-009 (Retention), JOURNEY-CPO-010 (Retention Reports)

### 7. Tenant Admin (TA)
Manages tenant settings, users, billing, and platform configuration.
- **Roles**: `USER`, `TENANT_ADMIN`
- **Journeys**: JOURNEY-TA-001 (Invite Users), JOURNEY-TA-002 (Manage Roles), JOURNEY-TA-003 (Billing)

### 8. Platform Admin (PA)
Super-admin with access to Django admin panel and cross-tenant operations.
- **Roles**: `USER`, `TENANT_ADMIN`, `is_staff=true`
- **Journeys**: JOURNEY-PA-001 (Django Admin), JOURNEY-PA-002 (Cross-Tenant View)

## Post-MVP Personas

### 9. Data Steward (DS)
Manages data mesh domains, policies, and governance rules. Gated behind `mesh/` prefix.
- **Roles**: `USER`, `DATA_STEWARD`

### 10. ML Engineer (MLE)
Trains models, manages experiments, deploys inference endpoints. Gated behind `ml/` prefix.
- **Roles**: `USER`, `ML_ENGINEER`

### 11. Integration Developer (ID)
Configures BaaS API keys and third-party connectors. Gated behind `baas/`, `integrations/` prefixes.
- **Roles**: `USER`, `INTEGRATION_DEVELOPER`

### 12. Transformation Author (TRA)
Creates and manages data transformation pipelines. Gated behind `transformation/` prefix.
- **Roles**: `USER`, `TRANSFORMATION_AUTHOR`

### 13. Community Member (CM)
Uses social features: comments, likes, follows. Gated behind `social/` prefix.
- **Roles**: `USER`

## E2E Test Users

The E2E test suite provisions these persona-specific test accounts (see `frontend/e2e/fixtures/auth.ts`):

| Function | Persona | Email Pattern |
| --- | --- | --- |
| `getTestUser()` | Authenticated User | `e2e_test@meshant.com` |
| `getTenantAdminUser()` | Tenant Admin | `e2e_admin@meshant.com` |
| `getComplianceOfficerUser()` | Compliance Officer | `e2e_cpo@meshant.com` |

## References

- RBAC implementation: `hub/apps/users/models.py` (roles field)
- Journey definitions: `docs/CRITICAL_UC_JOURNEY_IDS.yaml`
- E2E persona setup: `frontend/e2e/fixtures/auth.ts`
- MVP gating: `docs/MVP_FEATURES.md`
