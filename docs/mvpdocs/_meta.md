# MVP Documentation Overlay Model

## What Is This?

`docs/mvpdocs/` is an **overlay directory** (D152) that sits alongside
the existing `docs/` tree.  It does not replace or move existing
documentation — it adds MVP-specific entry points and fills gaps.

## Design Principles

1. **Self-contained** — mvpdocs is the single source of truth for all
   MVP documentation. It does not link to external doc files.
2. **Persona-first IA** (D155) — six product-canonical personas drive
   the navigation.
3. **Auto-generated reference** (D156) — API, CLI, and SDK reference
   pages are generated from source, not hand-written.
4. **MVP boundary enforced** (D157) — `scripts/check_mvp_doc_boundary.py`
   fails CI if user-facing pages reference post-MVP features without
   a `[Post-MVP]` badge.

## Directory Layout

```
docs/mvpdocs/
  index.md              — landing page (4 audience entry points)
  _audit/               — classification.yaml, api-audit-consolidated.md
  _meta/                — persona-mapping.yaml
  _meta.md              — this file
  _assets/              — shared images, diagrams
  personas/             — one subdir per product-canonical persona
  use-cases/            — one page per MVP UC (stable IDs)
  journeys/             — one page per MVP journey (stable IDs)
  concepts/             — domain entity explainers
  api-reference/        — auto-generated from OpenAPI
  cli-reference/        — auto-generated from Click tree
  sdk-reference/python/ — auto-generated from docstrings
  reference/            — hand-written common reference
  operations/           — operator runbooks + config reference
  product/              — features, roadmap, glossary
  compliance/           — regulations, audit trail, GDPR
  integrators/          — integrator landing page
```
