# UC-CM-002: Moderate Reviews and Ratings

**Persona:** [Marketplace Platform Admin (MPA)](../personas/marketplace-platform-admin/index.md)
**MVP Tier:** :white_check_mark:
**Phase 216 Test:** `cli/tests/integration/test_commands_real_api.py::test_review_moderation`

## Description

A Marketplace Platform Admin reviews, approves, or rejects user-submitted
reviews and ratings on marketplace listings. Moderation ensures that
reviews are constructive, accurate, and free of abuse, maintaining trust
in the marketplace's quality signals.

## Preconditions

- At least one marketplace listing has received a user review (submitted
  via `POST /api/v1/marketplace/listings/{id}/reviews`).
- The user is authenticated and holds the `MARKETPLACE_ADMIN` role.
- Moderation is enabled for the tenant (either pre-moderation or
  post-moderation mode).

## Steps

1. MPA opens the moderation queue via "Marketplace > Moderation" or
   calls `GET /api/v1/marketplace/reviews?status=pending_review` to
   list reviews awaiting moderation.
2. The API returns a paginated list of reviews with fields: `review_id`,
   `listing_id`, `author`, `rating` (1-5), `comment`, `submitted_at`,
   and optional `flagged_reason`.
3. MPA clicks a review to inspect the full content, listing context,
   and author history.
4. MPA takes one of the following actions:
   - **Approve:** `PATCH /api/v1/marketplace/reviews/{review_id}`
     with `{ status: "APPROVED" }`. The review becomes publicly visible
     and the listing's aggregate rating is recalculated.
   - **Reject:** `PATCH` with `{ status: "REJECTED", reason: "..." }`.
     The review is hidden. The author receives a notification explaining
     the rejection.
   - **Flag for follow-up:** `PATCH` with
     `{ status: "FLAGGED", reason: "..." }`. The review remains hidden
     while escalated to senior moderation.
5. After processing, the review moves out of the moderation queue.
6. MPA reviews the moderation dashboard for aggregate stats: reviews
   processed today, approval rate, average rating trend.

## Expected Outcome

- Approved reviews are visible on the listing detail page and
  contribute to the aggregate rating.
- Rejected reviews are hidden; the author is notified with the reason.
- The listing's `average_rating` and `review_count` are updated
  whenever a review status changes.
- An `AUDIT_REVIEW_MODERATED` event is recorded in the
  [audit log](../../concepts/audit-events.md) with the action taken.

## Error Handling

| Condition | Expected Response |
|-----------|-------------------|
| Review already moderated | `409 Conflict` |
| Review not found | `404 Not Found` |
| Insufficient role | `403 Forbidden` |
| Invalid status transition | `422 Unprocessable Entity` |

## Related

- Concepts: [Marketplace Listings](../../concepts/marketplace-listings.md), [Audit Events](../../concepts/audit-events.md)
- Journeys: [JOURNEY-MPA-005 -- Marketplace Admin Journey](../journeys/JOURNEY-MPA-005.md)
- Personas: [Marketplace Platform Admin](../personas/marketplace-platform-admin/index.md)
