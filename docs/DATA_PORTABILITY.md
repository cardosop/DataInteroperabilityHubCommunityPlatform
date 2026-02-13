# Data Portability

**Last Updated**: 2026-02-03

This document describes the data portability feature (GDPR Article 20 - Right to Data Portability).

---

## Overview

Users can request a copy of their personal data in a machine-readable format. The platform provides a data export feature that collects user data and provides it as a downloadable archive.

---

## Requesting Data Export

### API Endpoint

**POST** `/api/v1/users/me/export-data/`

Creates a data export job and returns job information.

**Authentication**: Required (user must be authenticated)

**Response**:
```json
{
  "job_id": "uuid",
  "status": "COMPLETED",
  "download_url": "https://...",
  "download_url_expires_at": "2026-02-04T12:00:00Z",
  "created_at": "2026-02-03T12:00:00Z"
}
```

### Job Status

Data export jobs can have the following statuses:

- **PENDING**: Job created, waiting to be processed
- **PROCESSING**: Job is being processed
- **COMPLETED**: Job completed, download URL available
- **FAILED**: Job failed, error message available

### Checking Job Status

**GET** `/api/v1/users/me/export-jobs/{job_id}/`

Returns job status and download URL if completed.

---

## Export Contents

The export archive (ZIP file) contains:

### user_data.json

Main data file containing:

- **user_profile**: User account information (email, display name, status, timestamps)
- **audit_events**: Recent audit events (last 1000) where user was the actor
- **assets**: Assets created by user (metadata only)
- **datasets**: Datasets created by user (metadata only)
- **contracts**: Contracts created by user (metadata only)

### README.txt

Information about the export contents and format.

---

## Data Included

### User Profile

- User ID
- Email address
- Display name
- Account status
- Created/updated timestamps

### Audit Events

- Event ID
- Resource type and ID
- Action performed
- Event details
- Timestamp

### Resources (Metadata Only)

- Asset metadata (name, description, status)
- Dataset metadata (name, description, status)
- Contract metadata (name, status)

**Note**: Actual file contents are not included in the export for privacy and storage reasons. Contact support if you need file contents.

---

## Download URL

### Expiry

Download URLs expire after **24 hours** from generation.

### Access

Download URLs are:
- **Signed**: Cryptographically signed for security
- **Short-lived**: Expire after 24 hours
- **Single-use**: Not intended for multiple downloads (though not enforced)

### Regeneration

If download URL expires, request a new export:

**POST** `/api/v1/users/me/export-data/`

---

## Rate Limiting

- **One export per user**: Only one export job can be in progress at a time
- **Rate limit**: Additional rate limiting may apply (check rate limit headers)

---

## Privacy and Security

### Data Access

- **User-only**: Users can only export their own data
- **Tenant-scoped**: Export only includes data from user's tenant
- **Authenticated**: Authentication required for all export operations

### Data Storage

- **Temporary**: Export archives stored temporarily in S3/MinIO
- **Automatic cleanup**: Old exports may be automatically deleted (retention policy)
- **Secure storage**: Exports stored in private S3 buckets with access controls

### Download Security

- **Signed URLs**: Download URLs are cryptographically signed
- **Expiry**: URLs expire after 24 hours
- **HTTPS**: Downloads use HTTPS (in production)

---

## Limitations

### Metadata Only

- **No file contents**: Actual file contents are not included
- **No sensitive data**: Sensitive data (passwords, API keys) are never included
- **Aggregated data**: Some aggregated or derived data may not be included

### Retention

- **Audit events**: Limited to recent 1000 events
- **Historical data**: Very old data may not be included

### Format

- **JSON format**: Data provided as JSON
- **ZIP archive**: Multiple files packaged as ZIP
- **Machine-readable**: Structured format for easy processing

---

## Use Cases

### GDPR Compliance

- **Right to data portability**: Users can obtain their data in a portable format
- **Data migration**: Users can migrate data to another service
- **Data backup**: Users can create backups of their data

### Data Analysis

- **Personal analytics**: Users can analyze their own usage patterns
- **Data processing**: Users can process their data with external tools

---

## Related Documentation

- `docs/GDPR_ERASURE.md` - Right to be Forgotten (data erasure)
- `docs/TENANT_ISOLATION.md` - Tenant isolation and data scoping
- GDPR compliance documentation
