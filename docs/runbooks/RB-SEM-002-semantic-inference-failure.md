# RB-SEM-002 — Semantic Inference Failure

**Owner:** semantic-eng@meshant.com | **Created:** 2026-05-18

## 1. Overview
Semantic inference materialises inferred triples via the reasoner when `semantic_inference_enabled=True`. Failures can cause SPARQL queries to return incomplete results or timeout.

## 2. Symptoms
| Symptom | Likely Cause |
|---------|-------------|
| SPARQL query timeout with inference ON | Reasoner expanding large ontology; complex inference chain |
| Inference returns 0 triples | `semantic_inference_enabled=False`; ontology not activated |
| Query results differ with inference ON vs OFF | Ontology rules applying unexpected inferences |
| Inference job stuck in PENDING | `SEMANTIC_SNAPSHOT` queue backlog; Fuseki unavailable |

## 3. Investigation
1. Check flag: `GET /api/v1/admin/tenants/{id}/feature-flags/`
2. Check Fuseki: `curl http://fuseki:3030/$/ping`
3. Query without inference: toggle `semantic_inference_enabled=False` → compare results
4. Check ontology: `GET /api/v1/semantic/ontologies/` → active ontologies

## 4. Remediation
- **Timeout:** Simplify query; add LIMIT; disable inference for this query
- **0 triples:** Enable `semantic_inference_enabled`; activate ontology
- **Unexpected inferences:** Review ontology rules; deactivate conflicting ontology
- **Fuseki:** Restart Fuseki; check PV disk space

## 5. Recovery
1. Fix root cause
2. Re-run query with inference enabled
3. Verify results include expected inferred triples

## 6. Escalation
- **P3:** Single query timeout with inference
- **P2:** All inference queries failing for a tenant
- **P1:** Fuseki down — all semantic operations failing
- **Contact:** semantic-eng@meshant.com

## 7. Related
- `docs/runbooks/semantic-inference.md`
- `docs/runbooks/semantic-degraded.md`
- `docs/runbooks/fuseki-pv-migration.md`
