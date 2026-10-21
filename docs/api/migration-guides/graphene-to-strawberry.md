# Migration Guide: Graphene → Strawberry GraphQL

**Deprecation**: 2026-06-01  
**Sunset**: 2026-12-01  
**New API**: `POST /api/v1/graphql/` (Strawberry-based)  
**Old API**: `POST /graphql-graphene/` (Graphene-based, deprecated)

## What Changed

The GraphQL engine was migrated from Graphene-Django to Strawberry GraphQL for better type safety, performance, and maintainability.

## Timeline

| Date | Event |
|------|-------|
| 2026-06-01 | Strawberry endpoint live at `/api/v1/graphql/` |
| 2026-06-01 | Graphene endpoint emits `Deprecation` + `Sunset` headers |
| 2026-09-01 | Graphene mutations disabled (read-only mode) |
| 2026-12-01 | Graphene endpoint removed |

## Schema Changes

### Query Naming

**Graphene (old)**:
```graphql
query {
  allAssets { id name status }
}
```

**Strawberry (new)**:
```graphql
query {
  assets { id name status }
}
```

### Field Naming

- `snake_case` fields remain `snake_case` (no change)
- `all<Resource>` → `<resource>` (plural) for list queries
- Filter arguments use `where:` input type instead of individual args

### Error Format

**Old**: Graphene errors in `errors[].message` with string messages  
**New**: Strawberry errors in `errors[].extensions.code` with structured error codes

### Rate Limiting

- Old: Unthrottled
- New: `graphql` scope (30 req/min per user)

## Migrating Your Queries

### Step 1: Update endpoint URL

```
OLD: POST /graphql-graphene/
NEW: POST /api/v1/graphql/
```

### Step 2: Update query names

Replace `all<Resource>` with `<resource>`:

```diff
- query { allAssets { id name } }
+ query { assets { id name } }
```

### Step 3: Update filter arguments

```diff
- query { allAssets(status: "ACTIVE") { id name } }
+ query { assets(where: { status: "ACTIVE" }) { id name } }
```

### Step 4: Verify

Run your queries against the new endpoint. If you get `QUERY_COMPLEXITY_EXCEEDED`, reduce nesting depth or paginate with `first:`/`after:`.

## Help

- CLI: `datahub graphql test --query 'query { assets { id } }'`
- Contact: `platform-eng@meshant.com`
- Template: use this guide as a template for future migration guides
