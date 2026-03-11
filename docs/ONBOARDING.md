# Self-Service Tenant Onboarding

**Last Updated**: 2026-02-03

This document describes the self-service tenant onboarding process.

---

## Overview

New tenants can create accounts and start using the platform through a self-service onboarding process. The onboarding creates a tenant, first user (tenant admin), and assigns a default plan.

---

## Onboarding Endpoint

### Create Tenant with First User

**POST** `/api/v1/tenants/onboarding/` (also available at `/api/v1/tenants/config/onboarding/`)

Creates a new tenant with first user (tenant admin).

**Authentication**: Not required (public endpoint)

**Request Body**:
```json
{
  "name": "My Company",
  "slug": "my-company",
  "plan_slug": "free",
  "first_user": {
    "email": "admin@example.com",
    "password": "securepassword123",
    "display_name": "Admin User"
  },
  "region": "us-east-1"
}
```

**Response**:
```json
{
  "tenant": {
    "id": "uuid",
    "name": "My Company",
    "slug": "my-company",
    "status": "ACTIVE",
    "plan": "plan-uuid"
  },
  "user": {
    "id": "uuid",
    "email": "admin@example.com",
    "display_name": "Admin User",
    "status": "ACTIVE"
  },
  "subscription_id": "uuid",
  "plan": {
    "slug": "free",
    "name": "Free Plan",
    "tier": "FREE"
  }
}
```

---

## Request Fields

### Required Fields

- **name**: Tenant name (e.g., "My Company")
- **slug**: URL-safe tenant identifier (e.g., "my-company")
- **first_user.email**: Email address for first user
- **first_user.password**: Password for first user

### Optional Fields

- **plan_slug**: Plan slug (defaults to "free")
- **first_user.display_name**: Display name for first user (defaults to email username)
- **region**: Cloud region (optional, informational)

---

## Validation

### Email Uniqueness

- Email must be unique across the platform
- If email already exists, returns `400 Bad Request` with code `EMAIL_EXISTS`

### Slug Uniqueness

- Slug must be unique across all tenants
- If slug already exists, returns `400 Bad Request` with code `SLUG_EXISTS`

### Slug Format

- Slug must contain only lowercase letters, numbers, hyphens, and underscores
- Automatically converted to lowercase

---

## What Gets Created

### Tenant

- **Status**: `ACTIVE`
- **KYC Status**: `UNVERIFIED`
- **Plan**: Assigned plan (defaults to FREE)
- **Region**: Optional region (informational)

### First User

- **Email**: Provided email address
- **Password**: Hashed and stored securely
- **Display Name**: Provided display name or email username
- **Status**: `ACTIVE`
- **Role**: `TENANT_ADMIN` (full tenant access)

### Tenant Configuration

- **Default DQ Profile**: Platform default
- **Allowed Compliance Regimes**: Platform defaults
- **Rate Limits**: Platform defaults
- **Job Concurrency**: Platform defaults

### Subscription

- **FREE Plan**: Subscription created without Stripe
- **PRO/ENTERPRISE Plans**: Stripe customer and subscription created (with trial if PRO)

---

## Plan Selection

### Default Plan

- **Default**: FREE plan if `plan_slug` not specified
- **Available Plans**: FREE, PRO, ENTERPRISE

### Plan Features

See `docs/BILLING.md` for plan details and limits.

---

## Post-Onboarding

### Login

After onboarding, the first user can log in:

**POST** `/api/v1/auth/login/`

```json
{
  "email": "admin@example.com",
  "password": "securepassword123"
}
```

### Access

- **Tenant Admin**: Full access to tenant resources
- **Plan Limits**: Subject to plan limits (see `docs/BILLING.md`)
- **API Access**: Can create API keys for programmatic access

---

## Rate Limiting

- **Public Endpoint**: Onboarding endpoint is public (no authentication required)
- **Rate Limiting**: May be rate-limited to prevent abuse
- **IP-based**: Rate limiting may be IP-based

---

## Security Considerations

### Password Requirements

- **Minimum length**: Check password requirements
- **Complexity**: Follow platform password policy
- **Storage**: Passwords hashed using secure hashing algorithm

### Email Verification

- **Optional**: Email verification may be required (check configuration)
- **Invitation**: First user created as ACTIVE (not INVITED)

### Tenant Isolation

- **Immediate isolation**: Tenant data isolated immediately upon creation
- **Scoping**: All operations scoped to tenant

---

## Error Handling

### Validation Errors

- **400 Bad Request**: Invalid input data
- **Error codes**: `EMAIL_EXISTS`, `SLUG_EXISTS`, `PLAN_NOT_FOUND`

### Stripe Errors

- **Non-blocking**: Stripe subscription creation failures don't block tenant creation
- **Logged**: Stripe errors logged for investigation
- **Fallback**: FREE plan subscription created if Stripe fails

---

## Use Cases

### New Customer Signup

- **Self-service**: Customers can sign up without manual intervention
- **Immediate access**: Access granted immediately after signup
- **Plan selection**: Customers can choose plan during signup

### Trial Signup

- **PRO Plan**: Customers can sign up for PRO plan with trial
- **Trial period**: 14-day trial for PRO plan
- **Conversion**: Trial converts to paid subscription after trial period

---

---

## Personal Tenant (Self-Service Registration)

**Endpoint**: `POST /api/v1/auth/register/`

When a user registers **without** providing `tenant_id`, the system creates a **personal tenant** for that user. This enables self-service onboarding: visitors can sign up and immediately use the platform without an invite or manual tenant assignment.

### Behavior

- **tenant_id omitted**: System creates a personal tenant (name: `Personal - {email}`, slug: `personal-{uuid8}`), assigns FREE plan, creates TenantConfig and Subscription, assigns `DATA_PROVIDER` and `DATA_CONSUMER` roles, and returns `tenant_id` in the response.
- **tenant_id provided**: User is associated with that tenant (unchanged behavior).

### What Gets Created

- **Tenant**: ACTIVE, KYC UNVERIFIED, FREE plan
- **TenantConfig**: Platform defaults
- **Subscription**: ACTIVE, FREE plan
- **User roles**: DATA_PROVIDER, DATA_CONSUMER

### Post-Registration

The user can immediately:
- Create assets in their personal tenant
- Access marketplace listings (as DATA_CONSUMER)
- Use platform features subject to FREE plan limits

### Feature Flag

`PERSONAL_TENANT_ON_REGISTRATION` (default: True). When False, legacy behavior: user created with `tenant=None`.

### Troubleshooting

See [Personal tenant creation failures](RUNBOOKS.md#personal-tenant-creation-failures) runbook for FREE plan missing, slug collision, and subscription creation failures.

---

## Tenant Switch

Users with multiple tenants (e.g. personal tenant + org tenant via invitation) can switch active tenant context without re-login.

### How It Works

- **GET /auth/me/tenants/** — Returns list of tenants the user has membership in
- **POST /auth/switch-tenant/** — Validates membership and returns updated me summary with `tenant_id` overridden
- **X-Tenant-Id header** — Clients send this header on subsequent requests to scope operations to the switched tenant

### Prerequisites

- User has membership in at least two tenants (UserTenantMembership)
- `FEATURE_TENANT_SWITCH_ENABLED` is true (default)

### Feature Flag

`FEATURE_TENANT_SWITCH_ENABLED` (default: True). When False, tenant switch API returns 403 and X-Tenant-Id is rejected.

See [TENANT_SWITCH_PLAN.md](TENANT_SWITCH_PLAN.md) for production migration and rollback. See [Tenant switch failures](RUNBOOKS.md#tenant-switch-failures) runbook for troubleshooting.

---

## Related Documentation

- `docs/BILLING.md` - Plans, limits, and billing
- `docs/TENANT_ISOLATION.md` - Tenant isolation and multi-tenancy
- `docs/DATA_RESIDENCY.md` - Data residency and regional considerations
- `docs/API_REFERENCE.md` - POST /auth/register/, tenant switch endpoints
- `docs/TENANT_SWITCH_PLAN.md` - Tenant switch migration and rollback
