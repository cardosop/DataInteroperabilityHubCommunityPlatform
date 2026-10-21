# Home Dashboard Widgets — Phase 278.R.6

Per-persona widget directories for the home dashboard. Each directory holds
React components that render persona-specific cards, charts, and actionable
items on `HomePage.tsx`.

## Directory convention

```
widgets/
├── de/       # Data Engineer — ingestion status, contract health, pipeline health
├── dpo/      # Data Protection Officer — compliance posture, DSAR queue, breach alerts
├── cpo/      # Chief Product Officer — pending approvals, billing, tenant health
├── dc/       # Data Consumer — orders, entitlements, saved searches
├── mpa/      # Marketplace Platform Admin — listing volume, order volume, onboarding
├── dev/      # Developer — API keys, SDK usage, rate limits
└── default/  # Fallback — quick start, getting started
```

## Integration pattern

1. Each widget is a self-contained React component exported from its directory.
2. `HomePage.tsx` imports widgets based on `usePersona()` return value.
3. Widgets use existing data hooks (`useAssets`, `useOrders`, etc.) gated behind
   `enabled: !!user && persona === '<persona>'`.
4. When no persona-specific widget exists for a section, the default dashboard
   layout (Recent Assets / Datasets / Jobs) renders as the fallback.

## Status

Directories created 2026-05-13 (Phase 278.R.6). Widget component implementation
is deferred to a follow-up sprint — the structure is ready for contributors to
drop in components per the specs below.
