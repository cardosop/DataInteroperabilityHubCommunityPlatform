# RB-GRAPHQL-001 — GraphQL Endpoint Failure

**Owner:** platform-eng@meshant.com | **Created:** 2026-05-20

## 1. Overview
GraphQL endpoints (Strawberry `graphql/` and Graphene `graphql_graphene/` [deprecated, sunset 2026-09-01]) serve API consumers with query complexity limits and error handling. Failures include query timeouts, complexity exceedances, and Strawberry resolver errors.

## 2. Symptoms
| Symptom | Likely Cause |
|---------|-------------|
| `QUERY_COMPLEXITY_EXCEEDED` | Query exceeds depth=10 or complexity=1000 limit |
| `QUERY_DEPTH_EXCEEDED` | Nested query depth > 10 |
| GraphQL endpoint returns 500 | Unhandled resolver exception |
| Slow query responses | N+1 resolver problem; missing DataLoader |
| `deprecated` header on graphene endpoint | Sunset 2026-09-01; migrate to `graphql/` |

## 3. Investigation
1. Check error extensions for `code` and `path`
2. Review query complexity score vs limit
3. Check Strawberry resolver logs for exceptions
4. Verify `graphql_graphene` deprecation status

## 4. Remediation
- **Complexity exceeded:** Simplify query; split into multiple requests
- **Depth exceeded:** Reduce nesting; use fragments
- **Resolver error:** Fix resolver logic; add error boundary
- **Deprecated:** Migrate to Strawberry `graphql/` endpoint

## 5. Recovery
1. Fix query structure or resolver issue
2. Re-submit GraphQL request
3. Verify response returns expected data

## 6. Escalation
| Priority | Condition | Contact |
|----------|-----------|---------|
| P3 | Single complex query rejected | API consumer (self-serve fix) |
| P2 | All queries failing for a tenant | platform-eng@meshant.com |
| P1 | GraphQL endpoint down | SEV1 — platform-eng on-call |

## 7. Related
- `hub/apps/graphql/views.py`
- `hub/apps/graphql/error_handler.py`
- `hub/apps/graphql_graphene/__init__.py` (deprecated)
- `docs/runbooks/RB-SEM-001-graphql-ld.md`
