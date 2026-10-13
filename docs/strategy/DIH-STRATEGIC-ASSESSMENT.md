# STRATEGIC ARCHITECTURE & CAREER ASSESSMENT — Data Interoperability Hub (DIH / "Meshant")

*Prepared 2026-09-12. Evidence base: 8 parallel code/doc/test investigations of this repository (2026-09-11), plus external grounding of the ODCS spec and the 2026 Unity Catalog baseline. All repo paths are relative to this repo root.*

**Evidence tags**: `[CODE]` fact from code · `[DOC]` fact from documentation · `[INFER]` inference · `[ASPIR]` aspirational/claimed · `[UNKNOWN]` not established.
**Maturity scale**: PROD-SHAPED (deep tests + walkable E2E) / IMPLEMENTED / PARTIAL / STUB / DEAD / DOC-ONLY / PLANNED.

**Section → requested-part mapping**: §1 Executive Context · §2 Capability Map + Implemented-vs-Aspirational · §3 Architectural Position + What Not To Do · §4 Databricks/UC/Control-Plane Relationship · §5 R&D Domain Model · §6 Scientific Data Contracts · §7 Digital Thread · §8 Semantic Interoperability · §9 AI/Knowledge Platform · §10 Top-15 Use Cases · §11 Adoption Options + Land-and-Expand · §12–13 Strengths / Weaknesses · §14–16 Career Risks / Opportunities / Positioning · §17 Open-Source/IP · §18–20 Research / PhD / Publications · §21 Stakeholder Map · §22 Unanswered Questions · §23 Evidence Table · Context Package for Strategic Recommendation.

---

## 1. EXECUTIVE CONTEXT

**What DIH actually is.** A private monorepo (~46,000 test sites, ~2,900 test files) implementing a multi-tenant data-interoperability platform: Django 6 monolith (56 apps under [hub/apps/](hub/apps/)) + FastAPI microservices (datacontract, dq, semantic, compliance, prefect-integration) + Apache Jena Fuseki 4.8 triplestore + Postgres (with real RLS on 98 tables) + Redis + S3-compatible storage + django-rq/Prefect execution, a React frontend (50 feature areas, ~150 routes, 458 Playwright specs), a 422-command CLI and Python/JS SDKs, Helm + 243 k8s manifests + Terraform, and ~75 CI workflows with ~40 numbered quality gates. [CODE]

**What it is *not*.** Not a storage or compute engine: contracts/lineage/catalog are its own; execution is delegated (dbt Core subprocess, Prefect, RQ, external warehouses); data bytes live in S3-compatible stores or the customer's Databricks. Its own readiness review states the OSS core is "~20% of a Databricks management plane" ([openspec/changes/add-databricks-control-plane/proposal.md](openspec/changes/add-databricks-control-plane/proposal.md)). [CODE][DOC]

**Delivery status.** Pre-beta. Phase U go/no-go is OPEN (human owner criteria unconfirmed in [docs/operations/beta-go-nogo-ledger.md](docs/operations/beta-go-nogo-ledger.md)); the target is an internal beta of 20–50 users / 2–3 tenants, staging on compose, EKS deferred [DOC]. Staging is real and exercised (Stripe, backup/restore drills, smoke tests); no production deployment evidence exists in-repo [CODE][INFER].

**Commercial reality.** DIH is the core of a SaaS product ("Meshant": free tier 10 assets/5 contracts/10K API calls, $99 Pro, Enterprise self-host AWS EKS) with a machine-enforced open-core boundary — [hub/apps/manifest.py](hub/apps/manifest.py) marks 11 of 65 apps as PAID (semantic, marketplace, billing, baas, rate_limiting, ai, ml, social, graphql×3), a public mirror is published from a sanitized tree, and `HUB_CORE_ONLY=1` boots a 42-app core. **The licensing is unresolved**: [LICENSE.txt](LICENSE.txt) says "proprietary, all rights reserved" while README claims "OSS core" and the split ADR declares Apache-2.0; no Apache license file exists. [CODE]

**The strategic question, reframed by the evidence.** DIH is a *metadata/governance/semantic layer* with genuine depth in four areas Databricks/Unity Catalog do not cover well — portable data contracts, human multi-step approval governance, tamper-evident audit, and an RDF semantic layer — plus a young but well-designed "governed front door" integration with Databricks itself. It is also a sprawling solo-led product with unresolved IP posture, zero production users, and a documented history of over-claiming (retracted features, simulated marketplace behavior, a Databricks E2E that has never passed). Both "why this could be highly differentiated" and "why this could fail" are real and evidence-backed below.

---

## 2. CURRENT APPLICATION CAPABILITY MAP

| Capability | What it does today | Maturity | Key evidence | Databricks relation |
|---|---|---|---|---|
| **ODCS data contracts** | Ingests ODCS 2.2.2/3.0.x/3.1.0, normalizes to a canonical "HubContract" (pydantic), enforces an always-on structural floor, validates via external datacontract-cli service; ACTIVE contracts immutable on 7 fields; per-asset integer versioning | PROD-SHAPED (275 test files) | [hub/apps/contracts/models.py](hub/apps/contracts/models.py), [services/contract_service.py](hub/apps/contracts/services/contract_service.py), [docs/CONTRACTS.md](docs/CONTRACTS.md) | **Complement** — Databricks has no native shareable contract artifact [external] |
| **ODPS data products** | Parses ODPS 1.x–4.2 + Bitol variants; product = linked ODPS+ODCS pair; 12-step ProductCreationWorkflow with per-step compensation; bundled JSON Schemas are self-authored placeholders (v4.2 detected, no schema shipped) | IMPLEMENTED / PARTIAL | [hub/apps/contracts/views_product.py](hub/apps/contracts/views_product.py), [marketplace/workflows/product_creation.py](hub/apps/marketplace/workflows/product_creation.py) | Complement |
| **Assets / datasets / files** | Metadata-only catalog: Asset = "logical data product (contract + dataset)"; datasets point to S3-compatible files (presigned multipart, ClamAV, lifecycle) or external refs; activation gated on contract + DQ + compliance | PROD-SHAPED | [hub/apps/assets/models.py](hub/apps/assets/models.py), [hub/apps/files/storage.py](hub/apps/files/storage.py) | Complement (catalog-of-intent above UC) |
| **Lineage** | ODCS-derived field-level lineage, SCD2 edge table, manual PATCH editor with cycle detection, time-travel, impact-analysis subscriptions; 5 technical edge types; outbound OpenLineage→Marquez; no semantic/provenance edge taxonomy | IMPLEMENTED | [hub/apps/contracts/models.py:697-890](hub/apps/contracts/models.py#L697-L890), [lineage_sync.py](hub/apps/contracts/lineage_sync.py) | Overlaps UC lineage at table level; **DIH adds manual/contract-level edges UC can't capture** |
| **Marketplace** | Full listing→order→entitlement→Stripe payment loop; 5-layer publish gates (compliance risk gate, KYC, structural floor, business rules, KYB/Stripe Connect); DB-level race constraints; 82 test files | PROD-SHAPED (deepest paid surface) | [hub/apps/marketplace/models.py](hub/apps/marketplace/models.py) | Complements UC's internal marketplace (external multi-tenant sharing + monetization) |
| **Search** | PostgreSQL websearch FTS over assets/contracts + **UC mirror feed (`types=uc`)** + ontology query-expansion (SKOS/OWL/RDFS bridging, depth ≤2); throttles/audit/metrics per contract; no embeddings/NL (deliberately sunset) | IMPLEMENTED | [hub/apps/search/views.py](hub/apps/search/views.py), [semantic_query_expansion.py](hub/apps/search/semantic_query_expansion.py) | Consumes UC metadata |
| **Semantic layer (PAID)** | Real Fuseki TDB2 + FastAPI wrapper; tenant-isolated named graphs; SPARQL endpoint (regex syntax gate, LIMIT, timeout, audit query-hash); per-tenant ontology upload (no versioning); SHACL at ingest only (3 shallow shapes); OWL/RDFS reasoning (helm-only wiring); JSON-LD context + 303 dereference; PROV-O mapping; Memento/tombstone/VoID/LDN; federation with SSRF guards; **QUDT absent; no entity resolution/alignment; metadata-scoped (contracts/assets, not data rows)** | IMPLEMENTED / PARTIAL | [hub/apps/semantic/services.py](hub/apps/semantic/services.py), [services/semantic-service/mapper.py](services/semantic-service/mapper.py), [infrastructure/fuseki/config.ttl](infrastructure/fuseki/config.ttl) | **Differentiator** — UC has no RDF/SPARQL/ontology layer (UC Metrics/glossary are nascent) |
| **Governance: ABAC** | Policy conditions (user/resource/environment), DENY short-circuit, field-level masking (REDACT/HASH/PARTIAL/FP), 5-min cache, 25+ enforcement call sites; API-level only, ad-hoc per-service (not a chokepoint); IP/location attrs documented but unimplemented | IMPLEMENTED / PARTIAL | [hub/apps/governance/abac.py](hub/apps/governance/abac.py), [data_masking.py](hub/apps/governance/data_masking.py) | **Overlaps UC** row filters/column masks/tag policies (UC enforces at engine level on stored data — DIH's version does not touch Databricks data) |
| **Governance: multi-step approval** | Row-locked double-approve guard, compliance gate (`allowed_to_store` + PLATFORM_ADMIN force-override), ABAC-on-approval, chain snapshot → `PENDING_NEXT_APPROVER`, delegation windows, comments; role enforcement partial; quorum = anti-self-dealing only | PROD-SHAPED | [hub/apps/governance/services.py:221-545](hub/apps/governance/services.py#L221-L545) | **Strongest complement** — UC has no human approval workflows for grants |
| **Audit system** | Append-only model (save/delete raise), per-tenant SHA-256 hash chain, hourly Merkle roots HMAC-signed → S3 Object Lock, per-(tenant, event) retention from regulation keys, PII redaction, FTS, RLS, 200 typed event constants + 1,490 event-bus schemas | PROD-SHAPED (standout) | [hub/apps/audit/models.py](hub/apps/audit/models.py), [event_types.py](hub/apps/audit/event_types.py) | **Stricter than UC** system-table audit (tamper-evidence, Object Lock) |
| **Tenant isolation / RLS** | 98 tables with `CREATE POLICY`, GUC-based `tenant_context` for workers/signals, BYPASSRLS admin-DB pattern, CI diff-gate pairing tenant models with policies | PROD-SHAPED | [hub/apps/tenants/request_tenant.py](hub/apps/tenants/request_tenant.py), [scripts/lint_rls_policies.py](scripts/lint_rls_policies.py) | Complement (multi-tenant SaaS governance) |
| **Business-rules chain engine** | 9 registered chains with transaction guard, OTel spans, audit; health endpoint; **`execute_chain` has ZERO production call sites** — live flows call rule classes directly; CLAUDE.md "MUST use" contract aspirational | IMPLEMENTED mechanics / DEAD in production | [hub/apps/core/business_rules/chains.py](hub/apps/core/business_rules/chains.py), [chain_registry.py](hub/apps/core/business_rules/chain_registry.py) | — |
| **Data quality** | FastAPI dq-service running Great Expectations + Soda (8 check modules), HMAC payload signature + anti-replay, fail-closed intake gate, trends/anomalies/alerting with per-channel circuit breakers + DLQ | PROD-SHAPED | [hub/apps/dq/service_client.py](hub/apps/dq/service_client.py), [services/dq-service/](services/dq-service/) | Overlaps Lakehouse Monitoring/DLT expectations for warehouse data; DIH's is engine-agnostic |
| **Databricks control plane** | P0: BYO workspace registry (lifecycle, SSRF/residency guards), encrypted credentials, hand-rolled API client (PAT/M2M/OBO, breaker, backoff, version-pinned UC endpoints); P0b: PKCE SSO + OBO vault + fail-closed hybrid identity; P1: UC read mirror (8 entities, delta-diff RQ sync), live effective-permissions browse, search feed, lineage reads; P2 engine: approval-gated UC DDL (`UCChangeRequest`) + ABAC grants bridge plan→diff→apply→verify (never OWNERSHIP); P3–P12 (compute, jobs, DLT, cost, Delta Sharing) **design-only** | IMPLEMENTED (read+govern) / PARTIAL (write) / PLANNED | [hub/apps/databricks_admin/](hub/apps/databricks_admin/), [openspec/changes/add-databricks-control-plane/design.md](openspec/changes/add-databricks-control-plane/design.md) | **Orchestrates/consumes Databricks** by design |
| **Integrations** | 7 marketplace connectors (databricks PULL via sanctioned delegation seam, snowflake, aws, gcp, azure, ckan, dados.gov.br); warehouse SQL connectors (Snowflake/BigQuery/Databricks/Athena); dlt movement (Databricks destination mapped, unwired) | IMPLEMENTED / PARTIAL | [hub/apps/integrations/connectors/](hub/apps/integrations/connectors/), [warehouses/connectors/](hub/apps/warehouses/connectors/) | Orchestrates |
| **Transformation** | JSON pipelines → dbt Core subprocess; **async dispatch broken** (no RQ TRANSFORMATION handler); DuckDB/Polars engine dead | PARTIAL | [hub/apps/transformation/dbt_executor.py](hub/apps/transformation/dbt_executor.py), [jobs/tasks_base.py](hub/apps/jobs/tasks_base.py) | Orchestrates dbt-on-Databricks (P11 planned) |
| **Virtualization / federation** | VirtualDataset SQL/SPARQL/FEDERATED/GRAPHQL/REST live-query via connector factory + in-process workflow engine; SPARQL/GraphQL connectorless | IMPLEMENTED / PARTIAL | [hub/apps/virtualization/models.py](hub/apps/virtualization/models.py) | Complement to Lakehouse Federation |
| **Orchestration / jobs** | django-rq (~50 job types, DLQ, priority queues) + home-grown saga workflow engine (13 defs) + Prefect for scheduled ingest/export; no Celery | IMPLEMENTED | [hub/apps/orchestration/](hub/apps/orchestration/), [hub/apps/jobs/models.py](hub/apps/jobs/models.py) | Orchestrates |
| **Compliance suite** | compliance-service (FastAPI PII detection), breach (72h SLA), consent (signed), DSAR, GDPR erasure/tombstones real; DPIA partial; RoPA/processor-agreements/regulation-policies thin | MIXED | [hub/apps/compliance/](hub/apps/compliance/), [services/compliance-service/](services/compliance-service/) | Complement (GDPR-class workflows UC doesn't provide) |
| **AI / ML** | NL search + AI schema matching = real LLM endpoints (OpenAI-compatible, gpt-4 default) but sunset-scheduled and still serving (documented 410 never landed in code); auto-classification + AI-app anomaly detection = **stubs**; real anomaly detection in observability (z-score); ML app = registry/training/inference bridge to external ODH; **no embeddings/vector search, no NL→SQL/SPARQL** | PARTIAL / STUB | [hub/apps/ai/views.py](hub/apps/ai/views.py), [hub/apps/ml/](hub/apps/ml/), [docs/AI_SEARCH_SUNSET.md](docs/AI_SEARCH_SUNSET.md) | Mosaic AI covers execution; DIH could own governed context |
| **SaaS rails** | Stripe subscriptions + Connect + metering (FLSC), BaaS API keys/usage (docs understate code), webhooks (HMAC-signed, retried, SSRF-guarded, includes `databricks.uc_change.*` events), SSE notifications, observability (OTel/Prometheus, freshness/volume/schema-drift/incidents) | PROD-SHAPED | [hub/apps/billing/](hub/apps/billing/), [hub/apps/webhooks/](hub/apps/webhooks/), [hub/apps/observability/](hub/apps/observability/) | — |
| **Frontend / CLI / SDK / Ops** | 150 routes incl. lineage editor, approval inbox, DQ pages, DPIA wizard, Databricks catalog browser; 422 CLI commands; Python+JS SDKs; helm/k8s/terraform; ~40 CI gates incl. a11y, k6 load, mutmut | PROD-SHAPED | [frontend/src/app/routes/routes.tsx](frontend/src/app/routes/routes.tsx), [helm/](helm/), [.github/workflows/ci.yml](.github/workflows/ci.yml) | — |

### 2.1 IMPLEMENTED VS ASPIRATIONAL — known debt / honesty gaps

All [CODE] unless noted:
- Marketplace Databricks `_download_table` and PUSH raise `NotImplementedError`; `_consume_share` fabricates its recipient result.
- The Databricks E2E is recorded as SKIP ([docs/runbooks/REAL_MARKETPLACE_E2E.md](docs/runbooks/REAL_MARKETPLACE_E2E.md)) and all Databricks tests run against local HTTP servers (one real-network test proves only a 401).
- `contract.publish` / `asset.activate` / `marketplace.listing.publish` chains are registered but never invoked in production flows.
- Transformation async dispatch is broken (missing RQ handler).
- `docs/AI_SEARCH_SUNSET.md` promises "2026-09-01: ai/ endpoints return 410 Gone" — the 410 is not in code; endpoints still serve.
- ~3,540 skip sites; only 20 carry the mandated `TICKET=`/`EXPIRES=` annotation.
- Bundled ODPS JSON Schemas are self-authored placeholders; v4.2 is detected but has no schema shipped.
- `docs/EVENT_TYPES_REFERENCE.md` documents 22 events; code has 200 audit constants + 1,490 event-bus schemas.
- Retracted claims (recorded in-repo, P.9 verdicts): the semgrep `prefer-chain` rule "describes enforcement that does not exist"; per-tenant chain enablement (274.16.13) was "prose with no field, migration, or runtime check".
- Provenance of some documented behavior is doc-ahead-of-code: OAuth M2M/SP promised in one spec but not implemented; dlt Databricks destination mapped but unwired.

---

## 3. BEST ARCHITECTURAL POSITION FOR DIH

| Identity | Fit | Overlap w/ Databricks | Differentiation | Adoption difficulty | Technical feasibility | R&D value | Defensibility | Verdict |
|---|---|---|---|---|---|---|---|---|
| Data control plane | Weak | **Total** — the org already has one; DIH is "20% of a management plane" | Low | High | Medium | Medium | Low | **REJECT** — directly collides with both Databricks and the org's control plane |
| Metadata control plane | Medium | High (UC = metadata plane) | Medium | Medium | High | Medium | Low-Med | Partial — only where UC doesn't reach (cross-estate, contracts, semantics) |
| **Interoperability control plane** | **Strong** | Low (UC has no contract/semantic interop) | **High** — ODCS/ODPS artifacts, RDF/SPARQL, ontology mapping | Medium | High (exists) | High | **High** (standards network effects) | **PRIMARY** |
| **Data-product governance layer** | Strong | Medium (UC marketplace exists but no approval workflows/contracts) | High — multi-step approval + delegation + compliance gates + tamper-evident audit | Medium | High (exists) | High | Medium-High | **PRIMARY** |
| Semantic interoperability layer | Strong | Low (UC Metrics nascent, Databricks-bound) | High — real Fuseki/SPARQL/JSON-LD/PROV-O | High (needs QUDT, alignment, SHACL depth) | Medium-High | High | High | **PRIMARY (after gap-fill)** |
| Knowledge interoperability layer | Medium | Low | High | High | Medium (alignment absent) | High | High | Later-stage evolution |
| Policy/governance execution layer | Strong | Medium (UC tag policies) | High for human-in-the-loop | Low-Med | High (exists) | High | Medium (UC closing) | **SECONDARY** |
| Scientific data-product platform | Strong | Low | High | Medium | Medium (domain model absent) | High | High | **Aspirational north star** |
| Scientific knowledge graph | Medium | None | High | High | Medium | High | Medium | Component of the above |
| Data marketplace | Medium | Medium (UC marketplace, Delta Sharing) | Medium (external multi-tenant + monetization) | Low | High (exists) | Medium | Low | Keep as feature, not identity |
| Developer platform | Weak | Medium (Databricks Apps, API) | Low | Medium | Medium | Low | Low | Reject as identity |
| Integration hub | Weak | Medium (Federation, LakeFlow Connect) | Low | Medium | High | Medium | Low | Reject as identity |
| Research-data catalog | Medium | High (UC = catalog) | Low | Low | High | Medium | Low | Reject as primary |
| Digital-thread platform | Strong | Low (UC lineage is table-level, no thread semantics) | High | High (needs edge taxonomy + domain model) | Medium | High | High | **Aspirational differentiator** |
| Data control plane over BYO Databricks | Medium | High (it IS Databricks management) | Low-Med | High | Partial (P3–P12 planned) | Medium | Low | Reject as the *internal* pitch |

**Recommended position: a "semantic data-product governance and interoperability layer" — a metadata/contract/intent control plane above the lakehouse.** DIH's strongest assets are exactly the layers Databricks deliberately does not own: portable machine-readable contracts (ODCS), human approval governance with delegation and compliance gates, tamper-evident audit anchored in object storage, and an RDF semantic layer. Its weakest positions are everywhere it touches physical data or compute.

**What DIH should NOT try to become** [INFER, from overlap analysis]:
1. **A data control plane** — the org already has one, and DIH's own roadmap (P3–P12) would spend ~4 engineer-quarters rebuilding what the org's plane + Databricks already do.
2. **A storage or compute platform** — the repo delegates both, deliberately.
3. **A warehouse or BI tool** — its own docs say "NOT a data warehouse."
4. **A general-purpose data catalog** — UC + a neutral catalog vendor already occupy this; DIH's catalog is a means, not an end.
5. **An ML platform / feature store / model serving layer** — Mosaic AI + the org's stack own this.
6. **A pipeline orchestrator** — Prefect/RQ inside DIH are glue, not product.
7. **A replacement for UC's engine-level enforcement** (row filters, column masks, tag policies on stored data) — DIH's API-level ABAC would double-govern without touching the SQL engines. DIH should *generate* UC tags/grants from its policy model, not duplicate enforcement.
8. **A general marketplace competitor** — keep marketplace as the governed sharing surface, not as a commerce play.

---

## 4. DATABRICKS / UNITY CATALOG / CONTROL-PLANE RELATIONSHIP

**Unity Catalog 2026 baseline** (external): UC now spans cross-engine ABAC (GA), Managed Iceberg, UC Metrics (a semantic layer), AI decision lineage, agent governance, an internal marketplace, Lakehouse Federation with metadata inheritance, and Delta Sharing for Iceberg. Criticisms: governance bounded to the Databricks estate + a single-region metastore; one-directional interop; lock-in concerns. **UC is moving into "context layer" territory — the window for generic catalog/governance differentiation is closing; semantic and contract differentiation is the durable bet.**

**Division of labor — evidence-based:**

| Area | Keep native to Databricks | DIH orchestrates | DIH consumes metadata | DIH adds semantics | DIH generates config | DIH = policy/intent source |
|---|---|---|---|---|---|---|
| Storage/tables (Delta/Iceberg) | ✅ | | | | | |
| Compute (SQL WH, jobs, DLT) | ✅ | ✅ (P3/P4 planned) | | | | |
| Physical lineage (table/column) | ✅ | | ✅ (UC lineage reads shipped) | | | |
| Fine-grained access enforcement | ✅ (row filters, masks, tag policies) | | | | ✅ (grants bridge ships it — plan→diff→apply→verify, never OWNERSHIP) | ✅ (ABAC policy model) |
| Data quality execution | ✅ (Lakehouse Monitoring, DLT expectations) | ✅ (DIH DQ is engine-agnostic; can trigger DLT) | ✅ | | ✅ (generate expectation sets from contract quality rules) | ✅ (contract quality thresholds) |
| Contracts | — (none native) | | | ✅ (ODCS artifacts + scientific extensions) | ✅ (contract → schema/table spec) | ✅ |
| Human approval workflows | — (none native) | ✅ (multi-step approval + delegation over UC grants/DDL) | | | | ✅ |
| Audit | ✅ (system tables) | | ✅ (mirror) | | | ✅ (tamper-evident chain + Object Lock as compliance record) |
| Semantic layer | (UC Metrics nascent) | | | ✅ (RDF/SPARQL/ontologies/PROV-O — the one place DIH is strictly ahead) | ✅ (semantic types → UC tags/comments) | ✅ |
| Marketplace / sharing | ✅ (internal marketplace, Delta Sharing) | ✅ (external multi-tenant marketplace, connector harvest) | ✅ | | ✅ (share/recipient provisioning — planned P5) | ✅ (listing + entitlement policy) |
| Cost/usage | ✅ (system.billing) | ✅ (P7 planned) | ✅ | | | |
| ML lifecycle | ✅ (Mosaic AI, MLflow, Feature Store) | ✅ (DIH ML app bridges external ODH) | ✅ | | | ✅ (governed dataset contracts for training) |

**The CONTRACT/INTENT → DIH → ENTERPRISE CONTROL PLANE → DATABRICKS architecture** [INFER, grounded in shipped code]:

1. **CONTRACT/INTENT layer (DIH)** — researchers/stewards express contracts (ODCS + scientific extensions), ontologies, approval policies, DQ thresholds, usage terms, confidentiality/IP classifications. *Exists today:* contracts, ABAC, approval, audit, semantic layer. *Gaps:* scientific profile (units/methods/provenance), alignment tooling, chain engine actually wired.
2. **DIH → ENTERPRISE CONTROL PLANE seam** — the org's existing control plane consumes DIH as its *intent source*: contract artifacts, policy bundles, approval decisions. *Exists:* none — this seam is the adoption integration work (REST/webhook; webhook catalog already includes `databricks.uc_change.*`).
3. **ENTERPRISE CONTROL PLANE → DATABRICKS** — the org's plane operationalizes intent into UC objects. *Exists in DIH:* the grants bridge and `UCChangeExecutor` demonstrate exactly this pattern (ABAC plan → UC REST PATCH → verify with OBO identity so **UC attributes the real user and enforces natively**) — i.e., DIH already implements the pattern the enterprise plane would run, which is both the proof-of-concept and the political overlap risk.
4. **DATABRICKS execution** — compute, storage, engine-level enforcement, lineage capture. DIH consumes UC system-table lineage back into its lineage/impact layer.

**Key strategic judgment**: inside this company, DIH should NOT pitch "control plane over BYO Databricks workspaces" (its own roadmap's framing) — the org already has that plane. It should pitch the *northbound half*: contracts + semantics + human-in-the-loop governance + tamper-evident audit, emitting intent that either the org's plane or DIH's own grants bridge (reused as a pattern, not as the product) turns into UC configuration.

---

## 5. R&D DOMAIN MODEL

**Current state** [CODE]: DIH's domain model is generic — `Tenant → Asset → (Contract, Dataset → File)`, `Field` inside contracts, `LineageEdge` (technical types only), ontology in the semantic layer. No chemistry/materials/lab entities exist anywhere. Everything below is therefore *design mapping onto existing extension points*, not shipped code.

**Proposed entity model and where each concept belongs** (INFER — mapping onto DIH's four real extension surfaces: contract schema fields, ontology layer, lineage edges, governance/rules):

| Layer | Concepts | DIH mechanism today |
|---|---|---|
| **Operational (stay in ELN/LIMS/MES/PLM)** | instrument, calibration, raw instrument data, lab notebook entries, MES batch records | external systems; DIH references via `ExternalResourceReference` / warehouse connections |
| **Lakehouse tables (Databricks)** | measurement rows, observation records, quality results, process parameters, pilot-run telemetry | Databricks tables; DIH contracts describe them; `types=uc` search surfaces them |
| **Metadata / contracts (DIH)** | dataset, derived dataset, contract, schema fields with semantic types, version, owner, quality thresholds, terms | [hub/apps/contracts/](hub/apps/contracts/) — fully generic, extendable |
| **Ontology / KG (DIH semantic layer, PAID)** | substance, material, formulation, ingredient, sample, batch, experiment, study, protocol, test/analytical method, property, unit, condition, researcher, laboratory, project, hypothesis, simulation, ML model, result, specification, product, prototype, process, process parameter, pilot run, manufacturing batch, failure mode, claim, evidence, publication, patent, regulatory requirement | `TenantOntology` + Fuseki named graphs + mapper ([services/semantic-service/ontology.ttl](services/semantic-service/ontology.ttl) already subclasses DCAT/PROV/FOAF) |
| **Lineage / digital thread (DIH)** | see §7 | `LineageEdge` + semantic relationships |
| **Business rules / governance (DIH)** | valid physical ranges, unit consistency, calibration validity, method-mandated conditions, regulatory classification gates, IP classification, evidence requirements for claims | ABAC policies, business-rules classes, approval chains, compliance gates |

**Core relationship graph** (design — the digital-thread spine):
`ChemicalSubstance → constitutes → Material → usedIn → Formulation → producedAs → Sample → evaluatedBy → Experiment → usesMethod → TestMethod → performedOn → Instrument (requires → Calibration) → generates → Measurement → describes → Property (has → Unit) → supports → Claim (supportedBy → Evidence) → justifies → ProductSpecification → governs → Product/Prototype → transferredTo → ManufacturingProcess → parameterizedBy → ProcessParameter → instantiatedAs → PilotRun → scalesTo → ManufacturingBatch → yields → QualityResult → references → Specification`

**Placement verdict**: operational entities stay in source systems; Databricks holds measured/physical rows; DIH holds contracts + ontology classes + typed relationships + rules. DIH's contract `Field` objects are the natural anchor: each field can carry a semantic type (ontology term + QUDT unit + method reference) — this is the column↔ontology mapping that the semantic layer currently lacks (build-time mapping only, no alignment tooling [CODE]).

---

## 6. SCIENTIFIC DATA CONTRACT OPPORTUNITY

**Can conventional ODCS contracts serve R&D? Partially.** ODCS v3.1.0 (approved 2025-12-08) supports extension via `customProperties` key–value lists, has a native `Relationship` definition, and tightened JSON Schema (`no additionalProperties` in several blocks). DIH supports 2.2.2 → 3.1.0 with `extensions` preserved in the canonical HubContract [CODE]. Note: DIH's "payload signature" is *not* an ODCS feature — it's internal HMAC transport integrity [CODE].

**Required scientific dimensions (the "Scientific Data Contract Profile")** — each maps to a *compatible* ODCS extension, no fork needed:

| Dimension | ODCS-compatible mechanism |
|---|---|
| Semantic type per field | `customProperties` per field: `{semanticType: "<ontology IRI>", ontologyVersion}` |
| Units + allowed conversions | `{unit: "qudt:MilliGM-PER-MilliL", allowedUnits: [...], conversionPolicy}` — requires adding **QUDT** (absent in DIH today [CODE]) |
| Precision / measurement uncertainty | `{uncertainty: {type, value, confidenceLevel}}` field custom property |
| Test method / instrument / conditions | `{method: {id, version, calibrationRequired}, conditions: [...]}` — or v3.1 `Relationship` to a Method contract |
| Valid physical ranges | maps to `quality` rules (`min`/`max` exist; add unit-aware rule types) |
| Provenance requirements | `{provenance: {minLevel: "sample|batch|instrument", requiredChain: [...]}}` + `Relationship` to sample/batch contracts |
| Reproducibility / FAIR metadata | `{fairs: {f1..r1.3, checksum, license, pid}}` |
| Confidentiality / IP classification | `{classification: {confidentiality, ipClass, exportControl, permittedUse}}` — note DIH already maps DPV/ODRL terms into RDF [CODE] |
| Retention / regulatory | `{retention: {period, regulationKeys}}` — DIH already derives retention from regulation keys in audit [CODE] |
| Reproducibility status | `{reproducibility: {status, referenceRun}}` |

**Assessment**: this is the single most differentiated, lowest-risk, highest-leverage idea in this entire analysis — a standards-compatible extension profile ("Scientific Data Contracts") proposed through the bitol-io TSC RFC process rather than a proprietary spec. It rides ODCS's momentum, costs DIH little (customProperties + a QUDT vocabulary + profile validation), and is simultaneously: an internal adoption wedge, an open-source positioning artifact, a publication topic, and a standards-participation credential. Confidence: HIGH that it is technically feasible; MEDIUM on community acceptance (needs engagement).

---

## 7. R&D DIGITAL THREAD OPPORTUNITY

**Gap between conventional lineage and a research→manufacturing thread** [CODE + INFER]: DIH's `LineageEdge` carries 5 *technical* edge types (`upload | transformation | derivation | export | reference`) with field-level scope and SCD2 — table-to-table lineage, like UC's. A digital thread needs **entity-level, typed relationships across six categories**:

| Relation category | Example | Mechanism |
|---|---|---|
| Technical lineage | table → table, field → field | existing `LineageEdge` + UC lineage sync [CODE] |
| Semantic relationship | Material `usedIn` Formulation; Property `describes` Material | ontology triples in Fuseki [CODE — partial] |
| Provenance | Measurement `wasGeneratedBy` Experiment, `wasAttributedTo` Instrument/Researcher | PROV-O mapping exists for metadata [CODE] |
| Evidence relationship | Claim `supportedBy` Measurement; Spec `justifiedBy` Study | new — ontology classes + links from contracts |
| Version relationship | Formulation v2 `derivedFrom` v1; Method revision chain | Dataset version tree exists [CODE]; needs entity-level generalization |
| Process relationship | PilotRun `scalesTo` ManufacturingBatch; stage transitions R&D→pilot→manufacturing | new — state machines + approval chains [CODE exists for approvals] |

**What DIH uniquely adds**: manual/curated edges (the LineageEditPage + PATCH API with cycle detection [CODE]) and contract-derived edges — humans can assert "this pilot run evidences this specification" where engines can't see. UC captures execution lineage; DIH adds *why-it-matters* relationships. The pilot wedge: one formulation → pilot → quality chain traced across Databricks tables + ELN/LIMS references.

---

## 8. SEMANTIC INTEROPERABILITY OPPORTUNITY

**Exists in DIH today** [CODE]: RDF (Fuseki TDB2), JSON-LD (context, 303 dereference, ingest/export), canonical URIs (semantic IDs as IRIs), SPARQL (with tenant scoping), ontology storage (per-tenant upload, *no versioning*), DCAT/PROV/FOAF/DQV/DPV/ODRL/schema.org vocabulary mappings, SKOS term usage in query expansion, OWL/RDFS reasoning (helm-only), SHACL (ingest-only, 3 shallow shapes), no entity resolution, no cross-ontology mapping.

**Standards evaluation for the manufacturing R&D context** (candidates marked by evidence level):

| Standard | Fit | Status in DIH | Evidence level |
|---|---|---|---|
| FAIR principles | Core narrative | partial (PIDs, metadata, licenses in contracts) | REAL — must be operationalized as machine checks |
| W3C PROV-O | Provenance | ✅ implemented in mapper | REAL |
| DCAT | Catalog interchange | ✅ implemented (hub ontology subclasses DCAT-3) | REAL |
| schema.org | Discovery | ✅ vocabulary map (declared types only) | REAL |
| **QUDT** | Units — non-negotiable for R&D | ❌ absent (zero hits repo-wide) | MISSING — top gap |
| SKOS | Vocabularies | partial (terms in expansion only) | PARTIAL |
| SHACL | Data-graph validation | token (3 shapes, ingest-only) | PARTIAL — needs shape authoring + coverage |
| OWL | Reasoning | real but config-fragile | PARTIAL |
| EMMO / Industrial Ontologies Foundry | Materials/process semantics | absent | CANDIDATE — needs investigation |
| Allotrope (ADF/ASM) | Analytical lab data | absent | CANDIDATE — strong in pharma/chem analytics; verify adoption in this org's instruments |
| SOSA/SSN | Sensors/observations | absent | CANDIDATE |
| OPC UA / AAS | Manufacturing digital twins | absent | CANDIDATE — only if manufacturing-side digital-twin program exists |
| ISA-88/95, B2MML | Batch/process | absent | CANDIDATE — relevant for process data alignment |

**Gap-fill order** [INFER]: (1) QUDT vocabulary + unit-aware contract validation; (2) SHACL shape library for the scientific profile; (3) ontology versioning + diffing; (4) mapping/alignment authoring UX + entity resolution; (5) stabilize reasoning across deployment modes; (6) SPARQL graph-level authz (currently a naming convention + regex gate — a determined tenant can address another tenant's named graph [CODE]).

---

## 9. AI / KNOWLEDGE PLATFORM OPPORTUNITY

**Evidence triangle** [CODE]: DIH's AI surface is thin (2 real sunset-bound LLM endpoints, stubs for classification/anomaly, no embeddings, no NL→SQL/SPARQL) — but its *context layer* is strong (contracts, ontology expansion search, PROV-O, audit, UC mirror). That combination defines the opportunity: **DIH should not build AI models; it should supply governed, semantically-typed, provenance-carrying context to AI systems.**

| Level | Capability | Realistic? |
|---|---|---|
| Near-term | Ontology-aware search (exists), evidence-traceable QA over experiments ("which measurements support this spec claim"), governed dataset selection for training, natural-language search over catalog+UC mirror | **Realistic 0–12 mo** — mostly composition of existing parts |
| Mid-term | GraphRAG over the Fuseki KG + contract registry; NL→SPARQL with schema validation (complexity checks already exist); AI-assisted schema→ontology mapping suggestions; contract-aware DQ explanation | **Realistic 12–24 mo** — needs embedding/LLM infra and alignment tooling |
| Frontier | Provenance-aware RAG with guarantees (answers carry PROV-O evidence chains); automated cross-ontology alignment; semantic contract synthesis from lab instruments' metadata; anomaly *explanation* over knowledge graphs | **Research** — publication-grade, needs partnerships + data |

Document-RAG vs semantic retrieval vs evidence-based AI: RAG answers from reports; KG-retrieval answers from typed relations; evidence-based scientific AI answers *with traceable measurement provenance* — the third is the defensible niche, and it is a plausible path to a strong internal AI-governance story ("every AI answer cites its evidence graph").

---

## 10. TOP 15 INDUSTRIAL R&D USE CASES

For each: problem → DIH capability → architecture → expected value → complexity → pilot.

1. **"Has anyone tried this before?" — unified experiment/material search.** Problem: repeated experiments; knowledge trapped in ELN/LIMS silos. Capability: UnifiedSearchView + UC mirror feed + ontology expansion. Architecture: contracts for ELN/LIMS extracts + `types=uc` search. Value: high (repeat-experiment cost). Complexity: low. Pilot: one lab, two source systems, 4 weeks.
2. **Unit/method-harmonized cross-lab analytics.** Problem: labs use different units/methods → incomparable results. Capability: scientific contract profile + QUDT. Architecture: per-lab contracts; unit-aware DQ rules flag non-conforming values. Value: high. Complexity: medium (QUDT integration). Pilot: one shared assay across 2 labs.
3. **Formulation provenance & claim evidence.** Problem: spec claims can't be traced to measurements. Capability: ontology relations + PROV-O + evidence edges. Architecture: KG instances over contract metadata; evidence links to Databricks measurement tables. Value: high (regulatory + speed). Complexity: medium-high. Pilot: one product line's spec → claim → measurement chain.
4. **Spec ↔ measurement traceability for product stewardship/regulatory.** Problem: audit-grade evidence assembly is manual. Capability: tamper-evident audit + approval workflows + lineage time-travel. Value: high. Complexity: medium. Pilot: one regulatory dossier.
5. **ELN/LIMS/instrument integration via contracts.** Problem: brittle point-to-point integrations. Capability: ODCS contracts as integration contracts; dlt/warehouse connectors. Value: medium-high. Complexity: medium. Pilot: one instrument type → contract → Databricks table.
6. **Experiment dedup & failure-mode library.** Problem: failed experiments not findable. Capability: ontology (FailureMode, Condition) + search + recommendations. Value: medium-high. Complexity: medium. Pilot: one synthesis domain.
7. **AI-ready curated datasets with governed provenance.** Problem: data scientists spend >50% on prep. Capability: contracts with quality thresholds + dataset versions + entitlements. Value: high. Complexity: low-medium. Pilot: one ML project's training dataset.
8. **Cross-lab semantic alignment (vocabulary governance).** Problem: "viscosity @25°C" ≠ "η" naming chaos. Capability: per-tenant ontologies + SKOS vocabularies + mapping tooling (to be built). Value: high. Complexity: high (organizational). Pilot: glossary for one material family.
9. **Digital thread pilot: formulation → pilot → manufacturing → quality.** Capability: lineage + ontology relations + process states. Value: high (transformational narrative). Complexity: high. Pilot: one product, staged over 2 quarters.
10. **IP/confidentiality-gated data sharing with external partners.** Problem: over-sharing risks IP; under-sharing stalls collaboration. Capability: ABAC + DPV/ODRL terms + approval workflows + marketplace entitlements. Value: high. Complexity: medium. Pilot: one supplier/partner collaboration.
11. **Manufacturing vs R&D identifier reconciliation.** Problem: different IDs for same substance across systems. Capability: semantic IDs + owl:sameAs + entity resolution (to be built). Value: medium-high. Complexity: high. Pilot: one substance family.
12. **Onboarding: new researchers find context fast.** Problem: knowledge in heads/documents. Capability: search + ontology expansion + curated contracts. Value: medium. Complexity: low. Pilot: onboarding package for one group.
13. **Data stewardship clarity: who owns what, who may use what.** Problem: unclear ownership/permitted use. Capability: contracts (team/roles/terms) + ODRL mapping + approvals. Value: medium-high. Complexity: low. Pilot: register 50 existing datasets.
14. **Machine-readable FAIR compliance reporting.** Problem: FAIR claims are prose. Capability: FAIR fields in contracts + machine checks. Value: medium (standards positioning high). Complexity: low. Pilot: FAIR scorecard for one domain.
15. **Governed LLM access to R&D knowledge (evidence-backed answers).** Problem: researchers distrust AI answers. Capability: KG + provenance + audit (RAG later). Value: high (differentiation). Complexity: high. Pilot: prototype after use cases 1–3 land.

---

## 11. INTERNAL ADOPTION OPTIONS (evaluated)

| Strategy | Org resistance | Political risk | Technical risk | Career upside | Career downside | IP risk | Adoption likelihood | Needs exec sponsorship | Platform-team compatibility |
|---|---|---|---|---|---|---|---|---|---|
| A. Enterprise platform pitch | Very high | Very high (overlap with existing plane) | High | High if it lands | Very high (rejection) | Medium | Low | High | Low — threatens control-plane team |
| B. Small OSS component only | Low | Low | Low | Medium | Low | Low-Med (must resolve licensing) | Medium | Low | High |
| C. Accelerator for the existing platform team | **Low** | **Low** | Low | Medium-High | Low | Low | **High** | Medium | **Very high** — additive, not competitive |
| D. Reference architecture/prototype | Low | Low | Low | Medium | Medium (perceived as "not production") | Low | Medium | Low | High |
| E. Scientific interoperability service | Medium | Low-Med | Medium | High | Medium | Medium | Medium-High | Medium | Medium — touches their turf |
| F. Semantic layer | Medium | Low-Med | Medium (gap-fill) | High | Medium | Medium | Medium | Medium | Medium |
| G. Data-contract service | Low | Low | Low | Medium | Low | Low | **High** | Low-Med | High — fills a hole Databricks doesn't cover |
| H. Research data-product catalog | Low-Med | Low | Low | Medium | Low | Low | Medium | Low | Medium |
| I. Digital-thread experiment | Medium | Low | Medium-High | High | Medium | Low-Med | Medium | Medium | Medium |
| J. Internal fork + generic OSS | Low-Med | Low | Low-Med | High | Low | **Must resolve licensing/ownership first** | Medium-High | Low | High |

**Recommended land-and-expand** [INFER]:
- **Phase 0 (before any pitch)**: resolve the license contradiction and employment-IP questions (§17); pick ONE scientist-champion in one lab.
- **Phase 1 — land (C+G, 6–10 weeks)**: pitch *not* DIH but "scientific data contracts for [one real dataset]" as an accelerator for the existing control-plane team: define contracts for 5–10 datasets, connect the UC mirror read (already shipped), demonstrate unit-aware quality rules and evidence-traced lineage. Deliverable: a working slice (contracts + search + UC mirror + approvals), zero overlap claims.
- **Phase 2 — expand (E/F, 1–2 quarters)**: add the semantic layer (ontologies + QUDT) as a "scientific interoperability service," keeping the pitch to "semantics Databricks doesn't provide, feeding UC tags."
- **Phase 3 — differentiate (I)**: digital-thread pilot across one product's research→pilot→manufacturing chain.
- **Explicitly avoid**: pitching "enterprise platform," "control plane," or "replace catalog" language; avoid the marketplace/commerce surface internally at first (sensitive with procurement/legal).

---

## 12. PERSON'S STRENGTHS (evidence-based)

| Strength | Evidence |
|---|---|
| Data architecture & platform engineering | 56-app Django 6 monolith + FastAPI services, Postgres RLS, Redis, S3, Fuseki, RQ/Prefect, Helm/k8s/Terraform, PgBouncer, observability stack — a complete enterprise-grade architecture, solo-built [CODE] |
| Data governance depth | Multi-step approval with delegation, compliance gates, ABAC, tamper-evident audit chain with Merkle roots + S3 Object Lock, regulation-derived retention — beyond what most platform teams ship [CODE] |
| Data contracts & data products | Full ODCS 2.2.2→3.1.0 + ODPS/Bitol implementation with normalization, structural floor, versioning, validation pipelines; 5,400 tests in contracts alone [CODE] |
| Semantic technologies | Working Fuseki/SPARQL/JSON-LD/PROV-O/SHACL/Memento/LDN stack — rare, real, tested (~930 semantic test functions) [CODE] |
| Databricks integration design | Version-pinned UC REST client, OBO/SSO hybrid identity, UC mirror + grants bridge, provider-boundary discipline; understanding of where UC enforces vs where it doesn't [CODE] |
| Software engineering rigor | ~46k test sites, ~40 CI gates with debt ratchets, mutmut, k6, a11y gates, no-mocks test conventions, 36 ADRs, migration reversibility checks [CODE] |
| Technical leadership/delivery discipline | 181-phase ledger, openspec changes with task evidence, retractions honestly recorded (P.9 verdicts), staging bring-up, backup/restore drills, go/no-go machinery [DOC][CODE] |
| Product thinking | SaaS positioning, free/pro/enterprise tiers, metering (FLSC), marketplace monetization, personas, i18n, e2e journey coverage [CODE][DOC] |
| AI platform awareness | LLM endpoints, circuit-breakered clients, ML registry bridge, and the maturity to *sunset* embedding search when it didn't pan out [CODE][DOC] |

## 13. PERSON'S WEAKNESSES / GAPS (deliberately not softened)

| Gap | Class | Evidence | Mitigation |
|---|---|---|---|
| **No production users; zero external validation** | **CRITICAL** | U.8 go/no-go OPEN; no production artifacts; Databricks E2E never passed (SKIP); "Meshant" has no public footprint [CODE][DOC] | Get ANY real user (internal pilot first); publish the mirror; a reference customer beats all docs |
| **Unresolved IP/licensing posture** | **CRITICAL** | LICENSE.txt proprietary vs README "OSS core" vs ADR Apache-2.0; no Apache file [CODE] | Legal review before any external pitch (see §17) |
| **Breadth-over-depth sprawl; solo bus-factor** | **CRITICAL** | 65 apps, 56 services, ~100 `test-batch-*` targets; thin suites in 15 apps; bus-factor-mitigation doc exists = acknowledged risk [CODE][DOC] | Ruthlessly shrink the internal pitch to the 3–4 differentiated slices; recruit co-maintainers |
| **Over-documentation / under-verification pattern** | IMPORTANT | Retractions (semgrep "enforcement that does not exist", per-tenant chains), simulated marketplace behavior presented as real, sunset doc ahead of code, docs/EVENT_TYPES_REFERENCE stale vs 200 constants [CODE][DOC] | Habit change: verify-then-claim; this pattern is the biggest credibility risk with skeptics |
| **No evidence of chemistry/materials/lab domain depth** | **CRITICAL for R&D positioning** | Zero lab-domain entities in the model; QUDT absent; no Allotrope/ISA/ontology-domain artifacts [CODE] | Pair with a domain scientist; co-author contracts with lab SMEs; learn QUDT/Allotrope/EMMO basics |
| **Semantic-layer gaps for scientific use** | IMPORTANT | No entity resolution/alignment, no ontology versioning, shallow SHACL, reasoning config-fragile, graph-level authz absent [CODE] | Funded roadmap; align with a research program (§18) |
| **Architecture overlaps the org's control plane politically** | **CRITICAL** | The repo's own roadmap is "control plane over BYO Databricks" — exactly the turf the org's team owns [DOC] | Reposition as northbound intent layer (§4); pitch as accelerator, not platform |
| **No publication record / community presence** | IMPORTANT (for the research track) | No public product; OSS mirror nascent; no evidence of papers/standards activity [INFER/UNKNOWN] | Start with the ODCS scientific profile RFC + one workshop paper (§18) |
| **Production hardening incomplete** | IMPORTANT | Broken async transformation dispatch, stub classification endpoints, unbundled schema placeholders, prod frontend hosting unclear [CODE] | Fix only what the chosen slice needs; don't harden all 65 apps |
| **Product-management positioning under-developed** | USEFUL | Marketing site silent on OSS; brand-name drift (DataHub/Interoperability Hub/Meshant); frontend v0.0.0 [CODE][DOC] | Pick one name + one positioning sentence; align marketing with the land-and-expand pitch |
| **Skip-debt governance unadopted** | USEFUL | 20 of ~3,540 skips carry TICKET/EXPIRES; debt frozen by ratchet, not scheduled [CODE] | Low priority for strategy; matters for engineering credibility |
| **No measurable business outcomes yet** | **CRITICAL** | Nothing beyond engineering metrics [CODE] | Tie every phase to a scientist-facing metric (time-to-find, prep-hours saved, audit-hours saved) |

## 14. CAREER RISKS

1. **The "unfunded infrastructure" trap**: 2+ years of solo platform building with no users → perceived as an engineer who can't ship business value. Highest-probability risk.
2. **Political collision**: pitching overlapping control-plane capabilities to the org's platform team → labeled redundant/competitive.
3. **IP entanglement**: the company may claim rights to the repo (built on employer-adjacent work/time); unresolved licensing blocks both OSS and personal continuity.
4. **Credibility damage from over-claims**: the documented over-claim pattern (simulated-as-real, docs-ahead-of-code) will be found by any serious evaluator; pre-empt by disclosing.
5. **Research-topic capture**: if the academic/PhD track consumes the roadmap, the product stalls; if the product consumes everything, the differentiation (publications/standards) never materializes. Needs explicit time-split.

## 15. CAREER OPPORTUNITIES

The initiative creates a rare combined asset: *implemented* contract-driven governance + semantic layer + Databricks control-plane integration + standards fluency + delivery discipline. In a market where "data contracts," "semantic layers," and "governed AI" are hot and mostly talk, this is a **"I built it, here it runs"** profile. Two paths: internal (R&D data-platform leadership) and external (open-source maintainer / standards influencer / startup founder), which are mutually reinforcing if the OSS core ships.

## 16. TOP CAREER POSITIONING OPTIONS

| Option | Fit | Missing | Internal potential | External potential | Defensibility | Alignment |
|---|---|---|---|---|---|---|
| **Scientific Data Architect / R&D Data Platform Lead** | Very high | domain credibility (pair with SME), user outcomes | High | High (rare combo) | High | Primary |
| **Semantic Interoperability Architect** | High | standards publications, QUDT/alignment depth | Medium-High | High (niche premium) | Very high (scarcity) | Primary |
| **Data Product / Data Contract Platform Lead** | High | ODCS community presence | High | High | Medium-High (ODCS mainstreaming) | Primary |
| Principal Data Platform Architect (general) | High | — (already qualified on paper) | High | High | Medium (commoditizing) | Fallback |
| **Open-source maintainer / technical founder (data contracts for science)** | Medium-High | community-building skill, funding story, IP resolution | Medium | Very high upside, high variance | Very high (if network effects) | Stretch |
| **Industry researcher / PhD (part-time, industry-anchored)** | Medium-High | publication record, methodology depth | Medium | High (credential) | High | Parallel track |
| Enterprise Data Architect / Data Governance Engineering Lead | High | enterprise politics | High | Medium | Medium | Fallback |

**Top 3–5**: (1) Scientific Data Architect, (2) Semantic Interoperability Architect, (3) Data Product/Contract Platform Lead, (4) OSS maintainer/founder, (5) industry PhD researcher. The winning combination is **(1)+(2)+(5)**: internal credibility from adoption + external credibility from standards/papers, all fed by the same codebase.

---

## 17. OPEN-SOURCE / IP CONSIDERATIONS

**Current state** [CODE][DOC]: machine-enforced open-core boundary (manifest, GATE-29, sanitized public mirror, DCO merge-back), but the license file is proprietary and the Apache-2.0 declaration is unfulfilled; paid layer (incl. the semantic stack) is excluded from the public tree.

**Architecture for separating open core from company-specific extensions** [INFER]:
- **Open-source core candidates**: ODCS/ODPS contract engine, structural floor, approval-workflow engine, audit hash-chain pattern, RLS patterns, lineage model, scientific-contract profile schema, QUDT vocab integration.
- **Company-private extensions**: connectors (ELN/LIMS/instrument), company ontologies/vocabularies, business rules encoding company policy, regulatory classification mappings, tenant configs, any derived data.
- **Decision-sensitive middle**: the semantic layer (currently PAID — must decide: open it for the research/standards story, or keep it as the vendor differentiator; this single decision shapes the entire strategy).

**Questions for company legal/IP teams (NOT conclusions — no legal advice)**: employee invention/prior-invention clauses and any invention-disclosure obligations; whether work was done on company time/equipment and how the greenfield program relates; IP assignment terms of the current role; whether the company holds or waives claims to the repo; open-source approval policy and trademark rules for "Meshant"; publication-approval process for papers/standards; export-control review of cryptography (KMS, HMAC) if released; personal-continuation options (license-back) if leaving.

**Risk summary**: the initiative cannot credibly claim to be "open source" until the license is fixed; the employment context makes an explicit written agreement with the employer a precondition for both the OSS track and the career track.

---

## 18. FRONTIER RESEARCH OPPORTUNITIES

| Direction | Research question | Novelty hypothesis | Industrial value | Venues/communities | PhD-feasible | Publishable w/o proprietary data |
|---|---|---|---|---|---|---|
| Scientific data contracts | "What is the minimal extension profile that makes data contracts machine-actionable for experimental science?" | ODCS extensions + FAIR operationalization = new profile | High | bitol-io TSC/RFC, VLDB/ICDE data-contract workshops, RDA | Yes | Yes (profile + synthetic/toy datasets) |
| Semantic contracts ↔ knowledge graphs | "How do contract schemas and ontologies co-evolve without drift?" | Alignment maintenance as first-class problem | High | ISWC/ESWC, Journal of Web Semantics | Yes | Yes |
| Automated schema→ontology mapping | "Can LLM+SHACL alignment beat manual mapping authoring?" | LLM-assisted alignment with validation guarantees | High | ISWC, K-CAP, DL workshops | Yes | Partially (needs public schemas) |
| Digital thread semantics | "What edge taxonomy suffices for research→manufacturing traceability?" | Typed-edge formalization vs plain lineage | High | ISWC industry track, INCOSE/IEEE systems journals | Yes | Yes |
| Provenance-aware RAG | "Can answers carry verifiable PROV-O evidence chains?" | Evidence-traced generation = new eval criterion | High | SIGIR/ACL, KDD Graph+LLM workshops, SEMANTiCS | Yes | Yes (synthetic KG) |
| Tamper-evident governance audit at scale | "Merkle-anchored audit for multi-tenant data platforms" | Applied crypto governance; systems novelty modest | Medium | Engineering venues (IC2E, SoCC workshops) | Marginal (systems-y) | Yes |
| Information-theoretic data→knowledge value | "Measuring knowledge yield of dataset curation" | Metric for stewardship ROI | Medium | Scientometrics/informatics | Speculative | Yes |
| Machine-actionable FAIR via contracts | "Contracts as FAIR Digital Object bindings" | FAIR-DO + ODCS bridge | Medium-High | RDA FAIR-DO Forum, FDO conf | Yes | Yes |
| Interop between R&D and manufacturing ontologies | "Bridging EMMO/Allotrope and OPC UA/AAS models" | Cross-domain alignment case study | Medium | IOF, EMMC, MSAM | Partial (industrial data needed) | Needs anonymized data |

**Priority** [INFER]: #1 (scientific data contracts) — feeds the adoption pitch, the standards story, and the OSS positioning simultaneously. Then #4/#5 as the second wave.

## 19. POSSIBLE PHD RESEARCH QUESTIONS

1. "A contract-first methodology for scientific data products: from ODCS extensions to executable FAIR metadata" (industry PhD, applied).
2. "Automated ontology alignment for heterogeneous laboratory data: LLM proposals + SHACL verification" (AI + semantic web).
3. "Provenance-aware retrieval: evaluation methodology for evidence-bound generative answers over scientific knowledge graphs" (IR/AI).
4. "Typed lineage for the R&D-to-manufacturing digital thread" (data engineering + semantics).
5. "Measuring data-product knowledge yield: information-theoretic valuation of curation" (more speculative).

Feasibility: high for #1/#2/#3 with anonymized/synthetic data; supervisor fit matters more than topic novelty; the repo itself (contracts, lineage, audit, SPARQL) is a ready-made experimental substrate.

## 20. POSSIBLE PUBLICATION / STANDARDIZATION OPPORTUNITIES

- **Standards**: bitol-io ODCS TSC RFC ("Scientific Data Contract Profile"); RDA FAIR Digital Object Forum; W3C community groups (Dataset Exchange WG interest); EMMO/IOF if the domain track deepens; Allotrope community if the lab-data track lands.
- **Venues**: ISWC/ESWC (industry + research), SEMANTiCS conference (industry-friendly), K-CAP, IPAW (provenance), VLDB/ICDE workshops on data contracts, J. Web Semantics, Semantic Web Journal, Nature Scientific Data (only with real-domain results — see the 2026 FAIR-by-design ELN paper as the bar).
- **Talk track**: Data+AI Summit industry sessions (Databricks complement story), Strata/Data Council.

---

## 21. STAKEHOLDER MAP

| Stakeholder | Cares about | Fears | Value proposition | Convincing evidence |
|---|---|---|---|---|
| R&D researchers / lab scientists | Finding prior work fast; not re-entering data | More admin; tool that slows them | "Search across labs; answers cite evidence" | Working search demo over their own data; minutes saved per search |
| Chemists / materials scientists | Unit/method fidelity; reproducibility | Semantic mistakes in their domain | Unit-aware contracts validated by their methods | Contract with their assay, validated in review |
| Data scientists / AI teams | Clean, governed training data | Governance friction | Curated, provenance-carrying datasets | One dataset prep time measured before/after |
| ELN/LIMS owners | No disruption to source systems | Integration burden | Read-only contracts over their exports | One connector pilot |
| Manufacturing / process engineering | Batch↔lab traceability | R&D-side complexity leaking in | Digital-thread demo across pilot line | One thread walkthrough |
| Quality / regulatory / product stewardship | Audit-grade evidence | Unauditable black boxes | Tamper-evident audit + approval trails | The Merkle/Object-Lock demo — objectively differentiated |
| Data platform team (control plane) | Not being undermined | Turf loss; redundant systems | "We generate intent your plane enforces; here's the grants-bridge proof" | Live UC grant diff/verify demo, OBO attribution |
| Enterprise architecture | Standards alignment; no sprawl | Another ungoverned platform | ODCS/FAIR/W3C standards story; open-core boundary | Standards mapping + boundary docs |
| Cybersecurity | Attack surface | Another system to secure | RLS, SSRF guards, signed transports, encryption at rest | Existing security evidence (pen-test docs, secrets posture) |
| Legal/IP | IP protection; licensing clarity | OSS leaks of proprietary data | Open-core separation; company extensions private | Written IP plan + boundary mechanics (manifest, GATE-29) |
| Databricks platform owners | UC as single governance hub | External governance layer confusing users | "Complementary northbound layer; UC stays the enforcer" | No-overlap matrix + OBO demo |
| Executives | Business value, speed | Platform-land-grab politics | One measurable R&D pain killed per quarter | Pilot metric + reference story |

---

## 22. CRITICAL QUESTIONS STILL UNANSWERED

1. **What ELN/LIMS/instrument systems exist, and what export APIs?** — determines integration pilots. Ask: lab informatics owners. Easy to obtain. **High** impact (pilot feasibility).
2. **Unity Catalog deployment state** (workspaces, metastore count, whether UC is standard) — determines the seam realism. Ask: Databricks platform owners. Easy. **High**.
3. **Scope of the org's control plane** (what it already owns: contracts? catalogs? approvals?) — decides overlap vs complement pitch. Ask: platform team/EA. Easy-Medium. **Very high**.
4. **Employee IP clauses + prior-invention status of the repo** — decides OSS/continuation viability. Ask: legal. Medium difficulty (sensitive). **Critical**.
5. **Open-source approval policy + publication approval process** — gates everything external. Ask: legal/IP office. Medium. **High**.
6. **Research pain-point validation** (which of the 15 use cases are real pains, quantified) — ask: 5–10 scientists in structured interviews. Medium. **Very high** (chooses the pilot).
7. **Existing ontologies/glossaries** in R&D (any EMMO/Allotrope/ISA usage; any master-data programs) — ask: data governance, lab informatics. Medium. **High**.
8. **Regulatory regime** (REACH-type obligations, product stewardship, GxP-adjacent labs) — ask: regulatory affairs. Easy. **High** (shapes use cases 3–4, 10).
9. **AI initiative landscape** (existing RAG/GenAI programs to attach to) — ask: AI/ML teams. Easy. **High**.
10. **Data volumes & geography** (labs, researchers, countries, data residency) — ask: ops/lab management. Easy. **Medium-High** (architecture + compliance).
11. **Internal governance model** (who approves data access today; data council?) — ask: data governance. Medium. **High** (approval-workflow fit).
12. **Company's Databricks contract** (workspace limits, UC tier, federation licenses) — ask: platform team. Easy. **Medium**.
13. **Manufacturing-side digital-twin/AAS program existence** — ask: manufacturing engineering. Medium. **Medium** (thread scope).
14. **Budget/headcount reality for internal platform adoption** — ask: sponsor. Medium. **High** (adoption mode).
15. **The creator's actual employment terms and the repo's origin story** — ask: HR/legal + the person. Sensitive. **Critical** for career+IP sections.
16. **Why the semantic layer was made PAID and who owns "Meshant" commercially** — determines whether semantics can ever be the open differentiator. Ask: the person/company records. Easy-Medium. **High**.
17. **Whether any external users/design partners exist** — ask: the person. Easy. **High** (go/no-go for beta claims).
18. **Time availability split** (day job vs DIH) — ask: the person. Easy. **High** (roadmap realism).

---

## 23. EVIDENCE TABLE

| # | Claim | Evidence | Source | Confidence | Type |
|---|---|---|---|---|---|
| 1 | DIH is a metadata/governance/semantic layer, not storage/compute | No storage keys on Asset; execution delegated (dbt/Prefect/RQ/S3/warehouses) | [hub/apps/assets/models.py:93](hub/apps/assets/models.py#L93) | HIGH | FACT |
| 2 | Contracts (ODCS) are the most mature subsystem | 275 test files; 2.2.2→3.1.0; structural floor always-on | [hub/apps/contracts/](hub/apps/contracts/) | HIGH | FACT |
| 3 | Semantic layer is real Fuseki/SPARQL/JSON-LD/PROV-O, but metadata-scoped, QUDT-less, and PAID | mapper targets contracts/assets only; QUDT zero hits; manifest `_PAID_MODULES` | [services/semantic-service/mapper.py](services/semantic-service/mapper.py), [hub/apps/manifest.py](hub/apps/manifest.py) | HIGH | FACT |
| 4 | Governance: multi-step approval + tamper-evident audit exceed UC's native equivalents | Row-locked approve; hash chain + Merkle + S3 Object Lock; UC has no approval workflows and no crypto audit | [hub/apps/governance/services.py:221-545](hub/apps/governance/services.py#L221-L545), [hub/apps/audit/models.py](hub/apps/audit/models.py) | HIGH | FACT (UC side: external, MEDIUM) |
| 5 | DIH's ABAC/masking overlaps UC engine-level enforcement and would double-govern | FieldAccessPolicy applies at DIH API only; UC enforces at scan/query time | [hub/apps/governance/data_masking.py](hub/apps/governance/data_masking.py) + Databricks release notes (external) | HIGH | FACT+INFER |
| 6 | Databricks integration is deep on read/govern, planned-only on manage | P0/P0b/P1 shipped; P3–P12 `[ ]`; ~289 SP estimate | [openspec/changes/add-databricks-control-plane/tasks.md](openspec/changes/add-databricks-control-plane/tasks.md) | HIGH | FACT |
| 7 | Some documented behavior is simulated/not-in-code | `_consume_share` fabricates recipient; `_download_table` NotImplementedError; E2E SKIP | [hub/apps/integrations/connectors/databricks_connector.py](hub/apps/integrations/connectors/databricks_connector.py), [docs/runbooks/REAL_MARKETPLACE_E2E.md](docs/runbooks/REAL_MARKETPLACE_E2E.md) | HIGH | FACT |
| 8 | Chain engine is dead in production | `execute_chain` zero non-test callers | [hub/apps/core/business_rules/chain_registry.py](hub/apps/core/business_rules/chain_registry.py) | HIGH | FACT |
| 9 | Open-source posture is legally unresolved | LICENSE.txt proprietary vs README/ADR Apache-2.0 claims | [LICENSE.txt](LICENSE.txt), [README.md](README.md) | HIGH | FACT |
| 10 | Product is pre-beta with a real staging, no production evidence | U.8 OPEN; staging artifacts real; no prod artifacts | [docs/operations/beta-go-nogo-ledger.md](docs/operations/beta-go-nogo-ledger.md) | HIGH | FACT+INFER |
| 11 | ODCS v3.1 supports extension via customProperties; no payload-signature concept | RFC-0024; v3.1.0 changelog | bitol-io RFC-0024 + v3.1.0 changelog (external) | HIGH | FACT (external) |
| 12 | Databricks has no native data-contract artifact | patterns via DLT expectations/tags; no shareable contract spec | Databricks community patterns + web baseline (external) | MEDIUM | FACT+INFER (external) |
| 13 | UC 2026 is moving into semantic/context-layer territory | UC Metrics, agent governance, AI lineage at DAIS 2026 | Bain DAIS 2026 analysis (external) | MEDIUM | FACT (external) |
| 14 | "Semantic data contracts" is an open research niche | no established term; adjacent FAIR/KG literature only | Scientific Data 2025 FAIR-interop paper; FAIR GraphRAG (external) | MEDIUM | INFER (external) |
| 15 | Test/delivery rigor is exceptional for a solo project | ~46k test sites; ~40 gates; mutmut; k6; a11y ratchets | [.github/workflows/ci.yml](.github/workflows/ci.yml), [scripts/](scripts/) | HIGH | FACT |
| 16 | Skill breadth is enormous but domain-science depth is unproven | no lab-domain entities; no publications found | codebase scan | HIGH | FACT+INFER |
| 17 | Recommended positioning: semantic data-product governance + interoperability layer, northbound intent to Databricks | overlap/derivation analysis (§3–4) | this document | MEDIUM | INFERENCE |
| 18 | Recommended adoption: accelerator + contract service first, digital-thread later | adoption matrix (§11) | this document | MEDIUM | INFERENCE |
| 19 | Scientific Data Contract Profile is the highest-leverage move | feasibility + ODCS extension mechanics + multi-track payoff | this document + ODCS RFC-0024 | MEDIUM-HIGH | HYPOTHESIS |
| 20 | The initiative could fail from: no users, IP entanglement, political overlap, over-claim credibility | evidence items 7, 9, 10, 16 | this document | MEDIUM | INFERENCE |

---

## CONTEXT PACKAGE FOR STRATEGIC RECOMMENDATION

*(Self-contained summary for the next AI — every load-bearing fact, no repository access needed.)*

**Setup.** A person at a multinational manufacturing company's greenfield R&D data-platform program (Databricks + an in-house data control plane; domains: chemicals, materials, formulations, labs, product development, manufacturing) has solo-built **Data Interoperability Hub (DIH)**, a ~2-year-old private monorepo, OSS core of a SaaS product called "Meshant." Today: pre-beta, go/no-go gate open, staging real, zero production users, internal beta target 20–50 users. Scale: Django 6 monolith (56 apps) + 4 FastAPI services + Jena Fuseki 4.8 triplestore + Postgres (RLS on 98 tables) + Redis + S3-compatible storage + django-rq/Prefect; React frontend (~150 routes, 458 Playwright specs, 13 personas); 422-command CLI; Python/JS SDKs; Helm/k8s/Terraform; ~75 CI workflows, ~40 quality gates; ~46,000 test sites; 181-phase task ledger with honest retractions recorded.

**Open-core boundary (machine-enforced).** 11 of 65 apps are PAID (semantic, marketplace, billing, baas, rate_limiting, ai, ml, social, graphql×3) via [hub/apps/manifest.py](hub/apps/manifest.py); sanitized public mirror + DCO merge-back; `HUB_CORE_ONLY=1` boots 42 apps. **License unresolved**: LICENSE.txt proprietary; README/ADR claim Apache-2.0; no Apache file exists. SaaS pricing: free / $99 Pro / Enterprise self-host EKS.

**Capability reality (implemented vs aspirational):**
- *Strong, tested, real*: ODCS contracts (2.2.2→3.1.0, structural floor, immutability, versioning — 5.4k tests); marketplace with 5-layer publish gates + Stripe + entitlements; multi-step access approval with delegation windows, compliance gate (`allowed_to_store`), ABAC-on-approval; tamper-evident audit (SHA-256 chain, hourly Merkle roots → S3 Object Lock, 200 event types); tenant isolation (real RLS + CI lint); DQ (Great Expectations + Soda FastAPI service, HMAC payload signature, fail-closed intake); webhooks (HMAC-signed, SSRF-guarded); billing/BaaS metering; OTel observability; walkable E2E core loop (register→contract→publish→search→approve→lineage) with @critical Playwright coverage.
- *Real but gapped*: semantic layer (real Fuseki/SPARQL/JSON-LD/PROV-O/SHACL/Memento/LDN; metadata-scoped; **QUDT absent**; no entity resolution/alignment; no ontology versioning; reasoning helm-only; graph-level authz missing; in the PAID layer); lineage (technical-only 5 edge types, manual editor, time-travel, OpenLineage→Marquez outbound; no semantic/provenance edge taxonomy); ABAC (25+ API-level call sites; not a chokepoint; IP/location attrs unimplemented); Databricks integration (P0/P0b/P1 shipped: workspace registry, encrypted creds, PKCE SSO+OBO fail-closed hybrid identity, UC read mirror with live effective permissions, search feed, lineage reads, CLI `uc ls`; P2 engine shipped but UX/audit open: approval-gated UC DDL + grants bridge plan→diff→apply→verify, never OWNERSHIP; P3–P12 — compute/jobs/DLT/cost/Delta Sharing — design-only, ~4 engineer-quarters).
- *Dead/stub/doc-ahead-of-code*: business-rules chain engine (`execute_chain` zero production callers); transformation async dispatch broken (no RQ handler); AI auto-classification + anomaly = stubs; embeddings removed by design (AI Search sunset; documented 410 never landed); marketplace Databricks PUSH/download NotImplementedError, `_consume_share` fabricates results; Databricks E2E recorded SKIP; ODPS bundled schemas are self-authored placeholders; ~3,540 skip sites with 20 TICKET/EXPIRES annotations; several doc retractions (semgrep "not enforced", per-tenant chains "prose only").
- *AI/ML*: NL search + AI schema matching real (OpenAI-compatible) but sunset-bound; ML app = registry/training/inference bridge to external ODH; no vector search, no NL→SQL/SPARQL.

**External baselines (2026).** ODCS v3.1.0 (Dec 2025) supports `customProperties` extensions + `Relationship`; no payload-signature concept (DIH's is internal transport HMAC). Databricks has no native data-contract artifact (DLT expectations + tags + patterns only). Unity Catalog 2026: cross-engine ABAC GA, Managed Iceberg, UC Metrics (semantic layer), AI/agent governance + lineage, internal marketplace, Lakehouse Federation metadata inheritance, Delta Sharing for Iceberg; criticisms: Databricks-boundary governance, single-region metastore, lock-in. "Semantic data contracts" is not an established research term (adjacent: FAIR GraphRAG, Scientific Data 2025 FAIR-interop paper, 2026 FAIR-by-design ELN paper).

**Strategic conclusions (recap).** Position: **semantic data-product governance + interoperability layer — a northbound contract/intent plane above Databricks**; explicitly NOT a data control plane, warehouse, general catalog, ML platform, or orchestrator. Architecture: CONTRACT/INTENT (DIH) → ENTERPRISE CONTROL PLANE → DATABRICKS, with DIH's grants-bridge/OBO pattern as the proven seam template. Databricks keeps: storage, compute, engine-level enforcement, physical lineage, DQ execution, ML lifecycle. DIH adds: contracts (incl. a proposed **Scientific Data Contract Profile** via ODCS customProperties: semantic types, QUDT units, uncertainty, methods/instruments/conditions, valid ranges, provenance requirements, FAIR fields, confidentiality/IP classification, retention), human approval governance, tamper-evident audit, RDF semantics, digital-thread edges (technical/semantic/provenance/evidence/version/process). Top use cases: unified experiment/material search; unit-method harmonization; formulation provenance/claim evidence; spec↔measurement traceability; ELN/LIMS contract integration; curated AI-ready datasets; cross-lab semantic alignment; digital-thread pilot; IP-gated partner sharing; governed evidence-backed AI. Adoption: land-and-expand = contract service + accelerator for the existing control-plane team (NOT a platform pitch), then semantic service, then digital-thread pilot. Career: strengths = rare breadth + rigor + real governance/semantic/Databricks depth; critical gaps = no users, unresolved IP/licensing, solo sprawl, unproven domain-science depth, over-claim credibility risk, political overlap with the control-plane team. Top positioning: Scientific Data Architect / Semantic Interoperability Architect / Data Product Platform Lead / OSS maintainer / industry PhD — combination wins. Research: priority = scientific data contracts (bitol RFC), typed digital-thread lineage, provenance-aware RAG; venues = ISWC/ESWC/SEMANTiCS/IPAW/VLDB-ICDE workshops/RDA; PhD-feasible with anonymized data. Open questions that most change strategy: ELN/LIMS landscape, UC deployment state, control-plane scope, employment-IP terms, validated research pain points, regulatory regime, existing AI programs, semantic-layer PAID decision.

**Both failure and success modes.** Why it could fail: no real user within 6 months; employer claims the IP; pitch collides with the control-plane team; over-claim pattern erodes credibility; scope stays at 65 apps instead of 3 slices. Why it could succeed: the scientific-contract + semantic-governance niche sits exactly where Databricks is weak and slow, the codebase already proves the hard parts, and the combination (contracts + approvals + tamper-evident audit + RDF + UC integration) has no obvious single competitor — only the incumbent's fast-moving context layer as a shrinking window.

---

## External sources consulted

- [ODCS v3.1.0 changelog](https://bitol-io.github.io/open-data-contract-standard/v3.1.0/changelog/)
- [bitol-io TSC RFC-0024: extensions to customProperties](https://github.com/bitol-io/tsc/blob/f2635d3b05808d8e75b1421422fb12bcc4f9ff77/rfcs/0024-extensions-to-customproperties-authoritativedefinitions.md)
- [Databricks product release notes](https://docs.databricks.com/aws/en/release-notes/product)
- [Bain — Data + AI Summit 2026: the lakehouse as agentic enterprise control plane](https://www.bain.com/insights/databricks-data-ai-summit-the-lakehouse-becomes-the-agentic-enterprise-control-plane/)
- [lakeFS — Unity Catalog and the quiet return of vendor lock-in](https://lakefs.io/blog/unity-catalog-quiet-return-of-vendor-lock-in)
- [Atlan — 5 Unity Catalog limitations (2026)](http://atlan.com.s3-website.ap-south-1.amazonaws.com/know/databricks-unity-catalog-limitations/)
- [Databricks community — quarantine pattern for failed DLT expectations](https://community.databricks.com/t5/data-engineering/designing-an-effective-quot-quarantine-quot-pattern-for-failed/td-p/168345)
- [FAIR GraphRAG paper (Semantic Scholar)](https://www.semanticscholar.org/reader/a97b2143523b241dc70fbcf749e93ba04550ad74)
- [MeshAnt (name-collision check — unrelated project)](https://github.com/automatedtomato/mesh-ant)
