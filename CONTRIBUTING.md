# Contributing to DataInteroperabilityHub (core)

Thanks for contributing! This is the open-source core of the Meshant
Data Interoperability Hub. Before opening a PR, please read the
[open-core boundary](README.md#open-core-boundary-please-read-before-contributing):
the semantic layer, marketplace, billing/BaaS, ML/AI, and social
features are hosted-SaaS capabilities and are **not open to
contribution** in this repository.

## Getting started

1. Fork and clone the repo.
2. `make quickstart` — brings up the core stack and seeds a demo tenant.
3. `make test-core` — runs the core-only backend suite (<15 min).

## Developer Certificate of Origin (DCO)

All commits must be signed off:

```
Signed-off-by: Your Name <you@example.com>
```

`git commit -s` adds this automatically. By signing off, you certify
the [Developer Certificate of Origin](https://developercertificate.org)
(DCO 1.1).

## How to extend the platform

The core is designed around extension points — prefer these over
editing core code directly:

- **Business-rules chains** — `hub/apps/core/business_rules/chain_registry.py`
- **Job handlers** — `hub/apps/core/job_handlers.py`
- **Event subscribers** — `hub/apps/core/events/subscriber.py`
- **Commercial hooks** — `hub/apps/core/commercial_hooks.py`
  (core-owned; the paid layer registers providers at runtime)

## Review process

- Open an issue first for anything non-trivial; maintainers triage
  weekly.
- PRs are reviewed within 2 weeks. CI must be green
  (GATE-29 boundary check, core test suite, lint, docs build).
- Keep the `scripts/core_boundary_allowlist.txt` ratchet from growing —
  core code must never import paid apps.

## Code style

Python: ruff + black (line length 100). TypeScript: prettier + ESLint.
Run `pre-commit install` — the repo's hooks run the pinned toolchain.
