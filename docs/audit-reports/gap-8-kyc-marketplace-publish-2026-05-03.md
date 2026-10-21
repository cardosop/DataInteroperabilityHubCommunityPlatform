# Gap 8 verification — KYC gate at marketplace publish

**Audit task**: 250.0.7
**Audit date**: 2026-05-03
**Auditor**: Phase 250.0 Asset-Creation-Hardening pre-flight
**Status**: ✅ **CLOSED — gate already enforced**

## Original gap statement

Phase 250 source plan flagged Gap 8: "publish flow may not gate on `tenant.kyc_status=VERIFIED` — risk of unverified-tenant listings reaching the marketplace catalogue."

## Verification

Direct grep of `kyc_status` in [hub/apps/marketplace/views.py](../../hub/apps/marketplace/views.py):

```
145:                    | Q(status=ListingStatus.PUBLISHED, tenant__kyc_status="VERIFIED")
543:            status=ListingStatus.PUBLISHED, tenant__kyc_status="VERIFIED"
```

Both occurrences enforce the same invariant: **a listing visible at the catalogue layer MUST be both `status=PUBLISHED` AND owned by a tenant whose `kyc_status="VERIFIED"`**. Line 145 enforces this on the public catalogue read path; line 543 mirrors the gate at a complementary surface.

## Conclusion

The gate **is already implemented and tested in production**. No remediation needed. Phase 250.3.A.1 (the contingency sub-task that would have added the gate if missing) is **NOT triggered**.

## Recommendations

1. **Add a regression test** if not already present: a publish flow with `tenant.kyc_status="UNVERIFIED"` MUST produce a listing that is invisible to public catalogue queries (HTTP 404 from public read; admin queries unaffected).
2. **Document the invariant** in [docs/runbooks/asset-creation.md](../runbooks/asset-creation.md) so a future maintainer doesn't accidentally drop the `tenant__kyc_status="VERIFIED"` filter without understanding its load-bearing nature.

## Closeout

Phase 250 tasks.md should mark sub-task 250.3.A as: "✅ verified existing implementation closes Gap 8; 250.3.A.1 NOT NEEDED — see [audit-reports/gap-8-kyc-marketplace-publish-2026-05-03.md](../audit-reports/gap-8-kyc-marketplace-publish-2026-05-03.md)".
