# JOURNEY-AUTH-001: First-Time Visitor Registers

**Persona:** Any (unauthenticated visitor)
**Use Cases:** UC-AUTH-001, UC-AUTH-002

## Overview

A first-time visitor discovers Meshant, creates an account, verifies
their email address, and lands on the tenant dashboard ready to explore
the platform. This journey covers every step from initial landing page
impression through a fully authenticated first session.

## Journey Steps

1. **Land on homepage** — The visitor arrives at `meshant.com` (or a
   tenant-branded subdomain) and sees the public marketing page with
   value propositions, trust indicators, and a prominent "Get Started"
   call-to-action.

2. **Click Register** — The visitor clicks the registration button,
   which opens the sign-up form. Social sign-in options (Google, GitHub)
   are displayed alongside the email/password form.

3. **Fill registration form** — The visitor provides their full name,
   email address, and password (minimum 12 characters, at least one
   uppercase, one digit, one special character). Optionally they select
   an organization or create a new [tenant](../concepts/tenants.md).

4. **Submit and receive verification email** — On submit the platform
   creates a pending [user](../concepts/users-and-roles.md) record and
   sends a verification email containing a time-limited token (valid for
   24 hours). The visitor sees a confirmation screen instructing them to
   check their inbox.

5. **Verify email** — The visitor clicks the verification link. The
   platform validates the token, marks the account as `active`, and
   redirects to the login page with a success banner.

6. **First login** — The visitor logs in with their new credentials.
   The platform issues a JWT access token (15-minute expiry) and a
   refresh token (7-day expiry). The session is recorded as an
   [audit event](../concepts/audit-events.md).

7. **Explore dashboard** — The authenticated user lands on the tenant
   dashboard showing quick-start cards, empty-state prompts for
   uploading a first [asset](../concepts/assets.md), and links to
   documentation.

## Success Criteria

- User account exists in `active` state with a verified email.
- JWT and refresh tokens are issued and stored client-side.
- An `auth.register` audit event is recorded.
- The user can navigate the tenant dashboard without errors.
- Subsequent logins succeed without re-verification.

## Related

- Concepts: [Users and Roles](../concepts/users-and-roles.md), [Tenants](../concepts/tenants.md), [Audit Events](../concepts/audit-events.md)
- How-To: [Data Product Owner Quickstart](../personas/data-product-owner/quickstart.md), [Data Consumer Quickstart](../personas/data-consumer/quickstart.md)
- Journeys: [JOURNEY-AUTH-002](JOURNEY-AUTH-002.md) (Login), [JOURNEY-AUTH-004](JOURNEY-AUTH-004.md) (Unauthenticated Access)
