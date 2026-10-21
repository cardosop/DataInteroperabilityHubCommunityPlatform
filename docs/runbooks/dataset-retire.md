# Dataset retirement

## When

Dataset superseded / regulatory obligation to minimise copies.

## Flow

1. Bump dataset status / retire flags per business rules.
2. Snapshot lineage graph for Legal.
3. Remove derived semantic artefacts (`SearchIndexer` eviction).
4. Tombstone object storage references after retention window satisfies GDPR Art 5(1)(e).

## Maintenance

- **Owner**: Platform Engineering
- **Last reviewed**: 2026-05-13
- **Next review**: 2026-08-11
