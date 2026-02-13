# GDPR Erasure (Right to be Forgotten)

**Last Updated**: 2026-02-03

This document describes the data erasure feature (GDPR Article 17 - Right to be Forgotten).

---

## Overview

Users can request deletion or anonymization of their personal data. The platform provides an erasure workflow that handles PII deletion/anonymization while respecting legal and compliance retention requirements.

---

## Requesting Erasure

### User Self-Service

**POST** `/api/v1/users/me/request-erasure/`

Creates an erasure request for the authenticated user.

**Authentication**: Required (user must be authenticated)

**Response**:
```json
{
  "request_id": "uuid",
  "status": "COMPLETED",
  "requested_at": "2026-02-03T12:00:00Z",
  "completed_at": "2026-02-03T12:00:01Z"
}
```

### Platform Admin

**POST** `/api/v1/platform/users/{user_id}/request-erasure/`

Platform admins can create erasure requests for any user.

**Authentication**: Required (platform admin)

---

## Erasure Process

### 1. Request Creation

- Erasure request created with status `PENDING`
- Audit event logged: `ERASURE_REQUESTED`

### 2. Execution

Erasure is executed immediately (or queued for async processing):

1. **User Profile Anonymization**:
   - Email: Anonymized to `deleted-{user_id}@deleted.local`
   - Display name: Set to "Deleted User"
   - Other PII fields: Anonymized or removed

2. **Session Revocation**:
   - All user sessions revoked and deleted
   - User logged out from all devices

3. **API Key Revocation**:
   - All API keys deactivated
   - API access revoked

4. **Audit Event Anonymization**:
   - Actor references anonymized in audit events
   - Email addresses in event details anonymized

### 3. Completion

- Request status set to `COMPLETED`
- Completion timestamp recorded
- Audit event logged: `ERASURE_COMPLETED`

---

## What is Deleted vs Anonymized

### Deleted

- **Sessions**: All user sessions deleted
- **API Keys**: API keys deactivated (soft delete)

### Anonymized

- **User Profile**: Email and display name anonymized
- **Audit Events**: Actor references and email addresses anonymized

### Retained (Retention Exceptions)

Some data may be retained for legal/compliance reasons:

- **Audit Events**: Audit events retained (with anonymized references)
- **Compliance Records**: Compliance-related records may be retained
- **Legal Holds**: Data subject to legal holds retained

**Note**: Retention exceptions are documented in the erasure request record.

---

## Erasure Request Status

Erasure requests can have the following statuses:

- **PENDING**: Request created, waiting to be processed
- **PROCESSING**: Erasure is being executed
- **COMPLETED**: Erasure completed successfully
- **FAILED**: Erasure failed, error message available

---

## Checking Request Status

### User Self-Service

**GET** `/api/v1/users/me/erasure-requests/{request_id}/`

Returns erasure request status and details.

### Platform Admin

**GET** `/api/v1/platform/users/{user_id}/erasure-requests/`

Returns all erasure requests for a user.

---

## Erasure Details

Completed erasure requests include:

- **anonymized_fields**: List of fields that were anonymized
- **deleted_resources**: List of resource types that were deleted
- **retention_exceptions**: List of resources retained due to legal/compliance requirements

**Example Response**:
```json
{
  "request_id": "uuid",
  "status": "COMPLETED",
  "anonymized_fields": ["email", "display_name"],
  "deleted_resources": ["sessions", "api_keys"],
  "retention_exceptions": ["audit_events"],
  "requested_at": "2026-02-03T12:00:00Z",
  "completed_at": "2026-02-03T12:00:01Z"
}
```

---

## Retention Policy

### Audit Events

- **Retention**: Audit events retained for compliance
- **Anonymization**: Actor references anonymized
- **Purpose**: Legal compliance and audit trail

### Compliance Records

- **Retention**: Compliance-related records may be retained
- **Purpose**: Regulatory compliance requirements

### Legal Holds

- **Retention**: Data subject to legal holds retained
- **Purpose**: Legal proceedings and investigations

---

## Timeline

### Request Processing

- **Immediate**: Erasure executed immediately upon request
- **Async option**: In production, erasure may be queued for async processing
- **Completion**: Typically completes within seconds

### Data Removal

- **Immediate**: User profile anonymized immediately
- **Sessions**: Sessions revoked immediately
- **API Keys**: API keys deactivated immediately
- **Audit**: Audit events anonymized immediately

---

## Limitations

### Partial Erasure

- **Tenant data**: User data within tenant context is erased
- **Cross-tenant**: Data shared across tenants may not be fully erased
- **Aggregated data**: Aggregated or derived data may not be erased

### Retention Exceptions

- **Legal requirements**: Data retained for legal compliance
- **Audit trail**: Audit events retained (anonymized)
- **Compliance**: Compliance records may be retained

---

## Privacy and Security

### Access Control

- **User-only**: Users can only request erasure for themselves
- **Platform admin**: Platform admins can request erasure for any user
- **Authenticated**: Authentication required for all erasure operations

### Audit Trail

- **Request logged**: Erasure request logged in audit trail
- **Completion logged**: Erasure completion logged in audit trail
- **Anonymized references**: Audit events use anonymized user references

### Data Protection

- **Secure deletion**: Deleted data securely removed from database
- **Anonymization**: PII anonymized rather than deleted where retention required
- **Encryption**: Data encrypted at rest and in transit

---

## Use Cases

### GDPR Compliance

- **Right to be forgotten**: Users can request deletion of their data
- **Data minimization**: Supports data minimization principles
- **User control**: Users have control over their personal data

### Account Deletion

- **Account closure**: Users can delete their accounts
- **Data cleanup**: Automatic cleanup of user data
- **Privacy**: Ensures user privacy after account deletion

---

## Related Documentation

- `docs/DATA_PORTABILITY.md` - Right to data portability
- `docs/TENANT_ISOLATION.md` - Tenant isolation and data scoping
- GDPR compliance documentation
