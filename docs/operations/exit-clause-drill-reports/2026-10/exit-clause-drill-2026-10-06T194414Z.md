# Pilot Exit-Clause Drill — 2026-10-06

| Field | Value |
|---|---|
| Status | **PASSED** |
| Tenant | `pilot-exit-drill` |
| Operator | `ph` |

## Stages

- **reset**: {"reset": true}
- **seed**: {"seeded": "pilot-exit-drill", "output": ["Drill tenant ready: pilot-exit-drill (bbbbbbb1-0001-4001-8001-000000000001) admin=pilot_exit_admin@example.com asset=exit-drill-dataset file=exit-drill-repor
- **export**: {"sha256_ok": true, "user_archives": 1, "files_listed": 1, "storage_key": "data-exports/bbbbbbb1-0001-4001-8001-000000000001/tenant-export/2026-10-06T194356Z.zip"}
- **soft_delete**: {"scheduled_for_deletion_at": "2026-10-06T19:43:57.341998+00:00"}
- **guardrails**: {"guardrail": "legal_hold_active", "proven": true}
- **hard_delete**: {"sweep_summary": {"dry_run": false, "grace_window_days": 0, "drill_skip_grace": true, "evaluated_count": 1, "hard_deleted_count": 1, "hard_deleted": [{"tenant_id": "bbbbbbb1-0001-4001-8001-0000000000
- **verify**: {"tenants": 0, "users": 0, "assets": 0, "files": 0, "audit_rows": 6, "deleted_audit_tenant_null": 6, "object_state": "201 objects imported automatically (use -v 2 for details).\n\nGONE"}
