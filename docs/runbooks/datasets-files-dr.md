# Datasets & Files — disaster recovery rehearsal

## Cadence

Quarterly tabletop + annual restore test.

## Script

1. Identify latest snapshot for `hub-files-*` bucket + RDS metadata.
2. Restore to isolated account; run smoke tests (`manage.py check --deploy`).
3. Validate ClamAV handshake + distributed lock behaviour on fresh Redis.
4. Document RTO/RPO actuals vs [`docs/capacity-planning.md`](../capacity-planning.md).

## Maintenance

- **Owner**: Platform Engineering
- **Last reviewed**: 2026-05-13
- **Next review**: 2026-08-11
