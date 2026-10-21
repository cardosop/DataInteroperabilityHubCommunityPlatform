# RB-SOCIAL-001 — Social Data Failure

**Owner:** platform-eng@meshant.com | **Created:** 2026-05-20

## 1. Overview
Social features (ratings, reviews, comments, communities) enable tenant users to rate and review data products. Failures include content moderation issues, community access problems, and data consistency errors.

## 2. Symptoms
| Symptom | Likely Cause |
|---------|-------------|
| Rating/review creation returns 403 | User lacks tenant membership or content moderation flag |
| Community access denied | User not a community member |
| Duplicate rating detected | Unique constraint violation; user already rated |
| Content moderation flag triggered | Automated moderation detected prohibited content |

## 3. Investigation
1. Check user tenant membership and roles
2. Verify community membership: `GET /api/v1/social/communities/{id}/members/`
3. Check audit events for moderation actions
4. Verify RLS policy is active on social tables

## 4. Remediation
- **Access denied:** Add user to community or verify tenant membership
- **Duplicate rating:** Update existing rating via PATCH
- **Moderation:** Review flagged content; appeal if false positive

## 5. Recovery
1. Identify the access or data issue
2. Apply role/membership fix
3. Retry the operation
4. Verify audit event emitted correctly

## 6. Escalation
| Priority | Condition | Contact |
|----------|-----------|---------|
| P3 | Single user access issue | Tenant admin |
| P2 | Content moderation false positive wave | platform-eng@meshant.com |
| P1 | Social data corruption across tenants | SEV1 — data-platform on-call |

## 7. Related
- `hub/apps/social/models.py`
- `hub/apps/social/views.py`
- `hub/apps/social/migrations/0005_enable_rls_social.py`
