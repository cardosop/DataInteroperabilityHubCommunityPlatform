# Breaking Change Policy

**Version**: 1.0 | **Owner**: Platform Engineering
**Aligned with**: ADR-API-VER-001 (API Versioning)

## Policy

All breaking changes to the public API, SDK, or CLI MUST follow a 90-day deprecation window before removal.

### Definition of Breaking Change

A change is **breaking** if it causes existing consumers to fail without code changes:

- Removing or renaming an API endpoint, field, or query parameter
- Changing a field type (e.g. `string` → `integer`)
- Changing response format (e.g. `200` → `204` for same operation)
- Removing a CLI command or flag
- Changing SDK method signatures
- Removing a supported authentication method
- Changing a required field to optional in a request body

### Definition of Non-Breaking Change

These are safe to deploy without deprecation:

- Adding a new endpoint, field, or query parameter (additive only)
- Adding a new CLI flag or SDK method
- Relaxing validation (e.g. increasing max length)
- Fixing a bug that returns an incorrect status code (if it was documented wrong)
- Adding a new enum value

## 90-Day Deprecation Window

1. **Day 0 — Announce**: Mark the endpoint/field/method as deprecated in code and docs
2. **Day 0 — Sunset header**: Add `Sunset: <ISO 8601 date>` header to all affected endpoints (date = Day 90)
3. **Day 0 — Migration guide**: Publish a migration guide in `docs/api/migration-guides/`
4. **Day 0–90 — Coexistence**: Old and new APIs coexist; deprecation warnings emitted
5. **Day 90 — Removal**: Remove the deprecated surface; consumers who haven't migrated will break

## Sunset Header

Every deprecated API endpoint MUST return:

```
Deprecation: true
Sunset: Tue, 01 Dec 2026 00:00:00 GMT
```

Implementation: add to DRF response via middleware or `@extend_schema` `deprecated=True`.

## Migration Guide Requirements

Each breaking change MUST include a migration guide with:

1. What changed (old API → new API)
2. Code examples showing before/after
3. Timeline (deprecation date, sunset date)
4. Contact for questions

Template: see `docs/api/migration-guides/graphene-to-strawberry.md`

## Versioning

- **API versions**: `/api/v1/`, `/api/v2/` — major versions have independent deprecation windows
- **SDK versions**: semantic versioning (`MAJOR.MINOR.PATCH`); breaking changes increment MAJOR
- **CLI**: `--deprecated` flag on old commands; new commands follow `datahub <resource> <action>` convention

## Exceptions

Emergency security fixes may bypass the 90-day window with CTO approval. Post-fix: publish a retroactive migration guide within 5 business days.
