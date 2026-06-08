# RB-MESH-001 — Cross-Domain Policy Conflict

**Feature:** Data Mesh (CANARY, `data_mesh_enabled`)
**Owner:** mesh-eng@meshant.com
**Created:** 2026-05-17 (Phase 285.5.6)

## Symptom Index

| Symptom | Likely cause | First checks |
|---------|-------------|--------------|
| Asset activation blocked by mesh policy | Conflicting policies from parent + child domains | `DataMeshDomain` hierarchy; `MeshGovernanceViewSet.check_compliance()` |
| Policy inherited from unexpected domain | Domain hierarchy misconfigured; orphan domain | Domain parent chain; `domain.parent_id` traversal |
| Domain-level quota exceeded | Child domains consuming parent quota; quota misattribution | `PlanLimitService.check_limit("mesh_domains", tenant_id)` |
| Cross-domain lineage broken | Asset moved between domains without lineage update | Lineage edge source/target domain fields |

## Metrics

- **Dashboard:** `monitoring/grafana/dashboards/data-mesh.json`
- **Primary:** `mesh_policy_conflict_total{domain_id, policy_type}`
- **Quota:** `mesh_domain_quota_usage{domain_id}`
- **Audit:** `MESH_POLICY_CONFLICT_DETECTED`, `MESH_DOMAIN_QUOTA_EXCEEDED`

## Investigation Checklist

1. Identify conflicting domains: `GET /api/v1/mesh/domains/{id}/policies/`
2. Check domain hierarchy: `domain.parent_id` chain to root
3. Review conflicting policies: quality gate, compliance threshold, retention
4. Check `MeshGovernanceViewSet.check_compliance()` output for conflict details
5. Audit log: search for `MESH_POLICY_CONFLICT_DETECTED` events

## Resolution

- **Policy precedence:** Child domain policy overrides parent (most specific wins)
- **Manual override:** `PUT /api/v1/mesh/domains/{id}/policies/{policy_id}/` → set `override=true`
- **Escalation to parent:** Set `inherit=false` on child domain to break inheritance
- **Quota resolution:** `PlanLimitService` enforces per-domain quota; parent quota is shared pool

## Escalation

- **P3:** Single asset blocked by resolvable policy conflict
- **P2:** Domain hierarchy broken — multiple assets blocked
- **P1:** Quota enforcement blocking production assets across multiple domains

## Related

- `hub/apps/mesh/models.py` — DataMeshDomain model
- `hub/apps/billing/services.py` — PlanLimitService
- `docs/runbooks/RB-COMP-001-compliance-fail-closed.md` — compliance gate investigation

## Maintenance

- **Owner:** Mesh Engineering
- **Last reviewed:** 2026-05-17
- **Next review:** 2026-08-17
