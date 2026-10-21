# Dataset version compare failure

## Symptoms

Semantic diff fails between dataset versions blocking marketplace publish.

## Debugging

1. Inspect `dataset.version_hash` + parent linkage through `VersionHistoryManager`.
2. Replay schema inference offline using stored parquet/csv snapshots.
3. Coordinate with DQ + Compliance if downstream checks reject shape drift.

## Maintenance

- **Owner**: Platform Engineering
- **Last reviewed**: 2026-05-13
- **Next review**: 2026-08-11
