# Orphan object cleanup

## Symptoms

Dashboard shows MinIO/AWS objects without matching `files_file` rows (inventory drift).

## Actions

1. Freeze tenant uploads if corruption suspected.
2. Run forensic SQL listing `storage_path` NULL rows vs bucket inventory CSV.
3. DELETE orphan keys via curated script with dual-control approval.
4. Post-incident ADR updates if systemic bug discovered.

## Maintenance

- **Owner**: Platform Engineering
- **Last reviewed**: 2026-05-13
- **Next review**: 2026-08-11
