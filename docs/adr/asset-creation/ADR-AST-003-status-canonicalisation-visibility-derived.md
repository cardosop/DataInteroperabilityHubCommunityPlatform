# ADR-AST-003 — `Asset.status` is canonical; `Asset.visibility` becomes a derived `@property`

**Status**: Accepted
**Date**: 2026-05-03
**Phase**: 250.3.B + 250.3.C
**Decision in design.md**: D250.4
**Owners**: Asset-Creation Eng, API Eng, External Integrators

## Context

`Asset` today carries two semi-overlapping fields:

- `status` ∈ {DRAFT, PENDING_APPROVAL, ACTIVE, PUBLIC, ARCHIVED, …}
- `visibility` ∈ {PRIVATE, PUBLIC, FEDERATED, …}

`status=PUBLIC` and `visibility=PUBLIC` are nearly synonymous; the distinction is historical (workflow state vs reader-visibility). Drawbacks:

1. **Drift risk** — code paths that set one but not the other; queries that filter on the wrong field; "active but private" vs "public but draft" become impossible-but-representable states.
2. **Test surface** — every behaviour has to be tested against the cartesian product of `status × visibility` even though most combinations are nonsense.
3. **External contract** — public API exposes both; integrators may build dashboards keyed on one or the other.

## Decision

`status` is the canonical state; `visibility` becomes a `@property` derived from `status`:

```python
class Asset(models.Model):
    status = models.CharField(max_length=32, choices=AssetStatus.choices, ...)

    @property
    def visibility(self) -> str:
        if self.status == AssetStatus.PUBLIC:
            return "PUBLIC"
        elif self.status == AssetStatus.FEDERATED:
            return "FEDERATED"
        else:
            return "PRIVATE"

    # NO setter — writes to `visibility` log a deprecation warning
    # via __setattr__ override and emit ASSET_VISIBILITY_WRITE_DEPRECATED audit.
```

### Two-phase deprecation (D250.4)

**Phase 1 (250.3.B — current release)**: `Asset.visibility` becomes property. Existing code paths that write `visibility` get a DeprecationWarning + audit event but continue to work (writes silently re-route to `status` updates). Migration nulls the `visibility` column to remove storage.

**Phase 2 (250.3.C — three release cycles later, gated on green telemetry)**: drop the `visibility` column entirely. PATCH requests with `visibility=...` return HTTP 400 with `{"code": "ASSET_VISIBILITY_FIELD_REMOVED", "remediation": "use status field"}`.

## Consequences

### Positive

- Single source of truth.
- Impossible-but-representable states eliminated.
- Less test surface.

### Negative

- External integrators may have built dashboards on `visibility`. Mitigation: 3-release-cycle deprecation window; CHANGELOG entry; pre-merge announcement (250.0.18 protocol); deprecation warning on every read (logged to subscriber's webhook payload).
- Frontend `AssetCreatePage.tsx` no longer has a `visibility` form field — UX team must update label + tooltip on the existing `status` field to communicate visibility implications. Figma sign-off required per F2-7.

### Backwards-compat shim (Phase 1 → Phase 2)

```python
# Hub-side serializer for transition window
class AssetSerializer(serializers.ModelSerializer):
    visibility = serializers.SerializerMethodField()  # READ-only

    def get_visibility(self, obj):
        return obj.visibility  # the @property

    class Meta:
        # In Phase 1: include visibility in fields for read-back
        # In Phase 2: drop visibility from fields entirely
        fields = [..., "status", "visibility"]
```

PATCH writes to `visibility` are stripped from the validated_data with DeprecationWarning emitted in Phase 1; PATCH writes return 400 in Phase 2.

## Alternatives considered

1. **Keep both fields but document precedence** — rejected; doesn't eliminate drift; only postpones the issue.
2. **Drop `status` and keep `visibility`** — rejected; `status` carries more state (DRAFT, PENDING_APPROVAL, ARCHIVED); `visibility` is a subset.
3. **Single-phase deletion** — rejected; insufficient deprecation window for external integrators.

## Verification

- Unit: `test_visibility_derived_from_status` — every status value produces deterministic visibility.
- Unit: `test_visibility_write_emits_deprecation_warning_and_audit`.
- Integration: in Phase 1, PATCH with `visibility="PUBLIC"` succeeds (logs warning); in Phase 2, returns 400.
- Migration safety: `visibility` column nulled in Phase 1 migration (atomic = False; uses `RunPython` with `noop` reverse for safety).
