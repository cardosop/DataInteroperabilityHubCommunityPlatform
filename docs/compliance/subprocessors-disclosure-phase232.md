# Sub-processor disclosure (Phase 232.0)

This note accompanies the public **`/legal/subprocessors`** UX shell introduced in Phase 232.0.

## Current posture

Customers receive the authoritative sub-processor catalogue through:

1. **Commercial agreements** — DPA annex listing vendors by function.
2. **Support / security review** — machine-readable JSON/YAML on request.
3. **In-app legal space** — `/legal/subprocessors` renders high-level summaries;
   per-tenant connector-specific names will appear inside the RoPA / processor
   register delivered in Phase `232.2+`.

Categories typically include hyperscale compute, relational + object storage,
managed Redis/queue, transactional email delivery, observability (logs + traces),
payments (Stripe Connect), AI inference partners (tenant opt-in configurations).

## Change notifications

Material sub-processor changes follow the contractual 30‑day notification window,
with supplemental email plus optional webhook `processor.sub_processor.updated`
(slotted for Phase **232.2** once workflow tables exist).

## Related code

Static authority metadata feeds from `data/regulation_authorities.yaml`; runtime
business rules derive from `hub.apps.regulation_policies.registry`.

## Phase 232.8 closeout — vendor stubs (engineering)

| Role | Vendor / service | Typical processing | Note |
| --- | --- | --- | --- |
| Object storage | Amazon S3 (or compatible) | DSAR bundles, RoPA exports, breach proofs | Phase **232.8.20** compliance buckets via IRSA |
| Transactional email | Amazon SES (or equivalent) | OTP, DSAR, breach notifications | Monitor bounces / suppression |
| Identity verification | **TBD — IDV vendor when 232.2b ships** | Optional subject verification | Replace TBD in public copy when live |

Update SPA strings under `public.legal.subprocessors.*` when any row is finalised.
