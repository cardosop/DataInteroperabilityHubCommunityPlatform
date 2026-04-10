# UC-CM-001: Manage Data Community

**Persona:** [Marketplace Platform Admin (MPA)](../personas/marketplace-platform-admin/index.md)
**MVP Tier:** :white_check_mark:
**Phase 216 Test:** `cli/tests/integration/test_commands_real_api.py::test_community_management`

## Description

A Marketplace Platform Admin creates and configures community spaces
within the Meshant platform. Communities group related assets, users,
and discussions around a domain or topic, enabling knowledge sharing,
asset discovery, and collaboration between data producers and consumers.

## Preconditions

- The user is authenticated and holds the `MARKETPLACE_ADMIN` or
  `PLATFORM_ADMIN` role.
- The tenant's community feature is enabled in the platform
  configuration.
- At least one published asset or domain exists to associate with the
  community (recommended but not required).

## Steps

1. MPA navigates to "Communities > Create New" or calls
   `POST /api/v1/communities` with
   `{ name, description, domain, visibility, guidelines }`.
2. The API validates the payload (unique name within tenant, valid
   domain reference) and creates the community record in `ACTIVE`
   status. Returns `201 Created` with the `community_id`.
3. MPA configures community settings:
   - **Membership model:** Open (anyone can join) or invite-only.
   - **Moderation level:** Pre-moderation (all posts reviewed) or
     post-moderation (flagged content reviewed).
   - **Linked domains/tags:** Assets matching these criteria are
     auto-surfaced in the community feed.
4. MPA invites initial members or data stewards via
   `POST /api/v1/communities/{community_id}/members`
   with `{ user_ids[], role }`.
5. MPA pins a welcome post or guidelines document to the community
   landing page.
6. MPA reviews the community dashboard showing member count, recent
   activity, and linked assets.

## Expected Outcome

- A `Community` record exists with the configured settings and is
  visible to members (or publicly, depending on visibility).
- Invited members receive notifications and can access the community.
- Assets matching the linked domains/tags appear automatically in the
  community's asset catalog.
- An `AUDIT_COMMUNITY_CREATED` event is recorded in the
  [audit log](../../concepts/audit-events.md).

## Error Handling

| Condition | Expected Response |
|-----------|-------------------|
| Duplicate community name | `409 Conflict` |
| Invalid domain reference | `422 Unprocessable Entity` |
| Community feature disabled | `403 Forbidden` with `FEATURE_DISABLED` code |
| Exceeded community limit per tenant | `422` with `LIMIT_REACHED` code |

## Related

- Concepts: [Assets](../../concepts/assets.md), [Tenants](../../concepts/tenants.md), [Search](../../concepts/search.md)
- Journeys: [JOURNEY-PA-001 -- Onboard Marketplace Instance](../journeys/JOURNEY-PA-001.md)
- Personas: [Marketplace Platform Admin](../personas/marketplace-platform-admin/index.md)
