# Runbook Library — Index (281.A.10.2)

**Last updated:** 2026-05-17  
**Total runbooks:** 115 across 11 categories  
**Game day tested:** See `docs/operations/game-day-runbook.md`

## By Category

### Asset & Data Lifecycle (15 runbooks)
| Runbook | Description | Game Day |
|---|---|---|
| [asset-creation.md](asset-creation.md) | Asset creation workflow troubleshooting | ✅ GD-Asset-01 |
| [asset-creation-auto-rollback.md](asset-creation-auto-rollback.md) | Auto-rollback on asset creation failure | ✅ GD-Asset-02 |
| [asset-fail-closed-rollback.md](asset-fail-closed-rollback.md) | Fail-closed asset persistence rollback | |
| [asset-creation-ci-matrix.md](asset-creation-ci-matrix.md) | CI test matrix for asset paths | |
| [asset-creation-otel-sampling.md](asset-creation-otel-sampling.md) | OTel sampling for asset creation | |
| [asset-saga-mutation-testing.md](asset-saga-mutation-testing.md) | Saga mutation testing procedures | |
| [asset-webhook-events.md](asset-webhook-events.md) | Webhook event troubleshooting | |
| [DATA_FIRST_ASSET_CREATION.md](DATA_FIRST_ASSET_CREATION.md) | Data-first asset creation workflow | |
| [dataset-retire.md](dataset-retire.md) | Dataset retirement procedure | |
| [datasets-files-dr.md](datasets-files-dr.md) | Datasets/files disaster recovery | |
| [dataset-version-compare-failure.md](dataset-version-compare-failure.md) | Version comparison failures | |
| [file-orphan-cleanup.md](file-orphan-cleanup.md) | Orphan file cleanup procedure | |
| [file-quota-exhaustion.md](file-quota-exhaustion.md) | File quota exhaustion response | |
| [file-retention.md](file-retention.md) | File retention policy enforcement | |
| [file-virus-scan-incident.md](file-virus-scan-incident.md) | Virus scan incident response | |

### Lineage (13 runbooks)
| Runbook | Description | Game Day |
|---|---|---|
| [lineage-a11y-review.md](lineage-a11y-review.md) | Lineage a11y review procedure | |
| [lineage-archive-job-failure.md](lineage-archive-job-failure.md) | Archive job failure recovery | ✅ GD-LIN-01 |
| [lineage-cycle-false-positive.md](lineage-cycle-false-positive.md) | Cycle false-positive investigation | |
| [lineage-dr.md](lineage-dr.md) | Lineage disaster recovery | |
| [lineage-edge-backfill-failure.md](lineage-edge-backfill-failure.md) | Edge backfill failure recovery | |
| [lineage-edge-sync-drift.md](lineage-edge-sync-drift.md) | Edge sync drift detection | |
| [lineage-notification-storm.md](lineage-notification-storm.md) | Notification storm mitigation | ✅ GD-LIN-02 |
| [lineage-pitr-rto-rpo.md](lineage-pitr-rto-rpo.md) | PITR RTO/RPO targets | |
| [lineage-snapshots-dod-evidence.md](lineage-snapshots-dod-evidence.md) | Snapshots definition-of-done | |
| [lineage-soak-period.md](lineage-soak-period.md) | Soak period monitoring | |
| [openlineage-dlq-replay.md](openlineage-dlq-replay.md) | DLQ replay procedure | |
| [openlineage-dod-evidence.md](openlineage-dod-evidence.md) | OpenLineage DoD evidence | |
| [marquez-outage.md](marquez-outage.md) | Marquez outage response | |
| [marquez-upgrade.md](marquez-upgrade.md) | Marquez upgrade procedure | |

### Semantic & SPARQL (10 runbooks)
| Runbook | Description | Game Day |
|---|---|---|
| [semantic-degraded.md](semantic-degraded.md) | Semantic service degraded response | |
| [semantic-export.md](semantic-export.md) | RDF export procedures | |
| [semantic-federation.md](semantic-federation.md) | Federated query troubleshooting | |
| [semantic-graphql.md](semantic-graphql.md) | GraphQL semantic endpoint | |
| [semantic-inference.md](semantic-inference.md) | Inference engine procedures | |
| [semantic-ldn.md](semantic-ldn.md) | Linked Data Notifications | |
| [semantic-memento.md](semantic-memento.md) | Memento datetime negotiation | |
| [semantic-ontology.md](semantic-ontology.md) | Ontology management | |
| [semantic-tombstone.md](semantic-tombstone.md) | Tombstone lifecycle | |
| [sparql-determinism.md](sparql-determinism.md) | Non-deterministic SPARQL results | |

### Governance & Compliance (10 runbooks)
| Runbook | Description | Game Day |
|---|---|---|
| [phase232-breach.md](phase232-breach.md) | Breach notification procedure | ✅ GD-BR-01 |
| [phase232-compliance-programme.md](phase232-compliance-programme.md) | Compliance programme overview | |
| [phase232-consent-processor.md](phase232-consent-processor.md) | Consent processor management | |
| [phase232-dpia.md](phase232-dpia.md) | DPIA workflow | |
| [phase232-dsar.md](phase232-dsar.md) | DSAR request handling | ✅ GD-DSAR-01 |
| [phase232-public-portal.md](phase232-public-portal.md) | Public portal management | |
| [phase232-regulator-audit-tabletop.md](phase232-regulator-audit-tabletop.md) | Regulator audit tabletop | |
| [phase232-ropa.md](phase232-ropa.md) | RoPA management | |
| [compliance-intake-gate.md](compliance-intake-gate.md) | Compliance intake gate | |
| [RB-COMP-006-federated-import.md](RB-COMP-006-federated-import.md) | Federated import — credential rotation, provider connectivity, cross-region consent | |

### Feature Flags (8 runbooks) — Phase 283.6
| Runbook | Description | Game Day |
|---|---|---|
| [RB-FLAG-001-trust-signals.md](RB-FLAG-001-trust-signals.md) | `trust_signals_enabled` GA flag — catalogue badges, freshness, lineage | |
| [RB-FLAG-002-workflows.md](RB-FLAG-002-workflows.md) | `workflows_enabled` GA flag — Prefect/SDK workflow execution | |
| [RB-FLAG-003-audit-full-sampling.md](RB-FLAG-003-audit-full-sampling.md) | `compliance_audit_full_sampling` GA flag — per-read audit forensics | |
| [RB-FLAG-004-datasets-files.md](RB-FLAG-004-datasets-files.md) | `datasets_enabled` + `files_enabled` GA flags — REST surface kill-switches | |
| [RB-FLAG-005-data-quality.md](RB-FLAG-005-data-quality.md) | `data_quality_enabled` + `data_quality_advanced_enabled` GA flags | |
| [RB-FLAG-006-versioning.md](RB-FLAG-006-versioning.md) | `versioning_enabled` GA flag — snapshots, diff, rollback | |
| [RB-FLAG-007-processor-agreements.md](RB-FLAG-007-processor-agreements.md) | `compliance_processor_agreements_enabled` GA flag — Article 28 agreements | |
| [RB-FLAG-008-retention-enforcer.md](RB-FLAG-008-retention-enforcer.md) | `compliance_retention_enforcer_enabled` GA flag — tombstone/hard-delete sweep | |

### RBAC, Auth & Security (8 runbooks)
| Runbook | Description | Game Day |
|---|---|---|
| [RB-AUTH-001-rls-kill-switch.md](RB-AUTH-001-rls-kill-switch.md) | RLS kill-switch activation | ✅ GD-SEC-01 |
| [RB-AUTH-002-cross-tenant-denial-investigation.md](RB-AUTH-002-cross-tenant-denial-investigation.md) | Cross-tenant denial investigation | |
| [RB-AUTH-003-cookie-mode-rollback.md](RB-AUTH-003-cookie-mode-rollback.md) | Cookie mode rollback | |
| [RB-AUTH-004-internal-api-key-rotation.md](RB-AUTH-004-internal-api-key-rotation.md) | Internal API key rotation | |
| [RB-SEC-001-credential-rotation.md](RB-SEC-001-credential-rotation.md) | Credential rotation | |
| [RB-SEC-002-cve-remediation.md](RB-SEC-002-cve-remediation.md) | CVE remediation | |
| [RB-CMP-002-legal-basis-strict-mode-incident.md](RB-CMP-002-legal-basis-strict-mode-incident.md) | Legal basis strict-mode incident | |
| [dsar-public-penetration-review.md](dsar-public-penetration-review.md) | DSAR penetration review | |

### Marketplace & Stripe (8 runbooks)
| Runbook | Description | Game Day |
|---|---|---|
| [RB-MKT-001-stripe-connect-onboarding-failure.md](RB-MKT-001-stripe-connect-onboarding-failure.md) | Stripe Connect onboarding failure | |
| [RB-MKT-002-refund-discrepancy.md](RB-MKT-002-refund-discrepancy.md) | Refund discrepancy investigation | |
| [RB-MKT-003-payout-failure-investigation.md](RB-MKT-003-payout-failure-investigation.md) | Payout failure investigation | |
| [marketplace-connector-deployment.md](marketplace-connector-deployment.md) | Connector deployment | |
| [KYC_PROVIDER_INTEGRATION.md](KYC_PROVIDER_INTEGRATION.md) | KYC provider integration | |
| [vendor-failure-stripe.md](vendor-failure-stripe.md) | Stripe vendor outage | ✅ GD-VF-01 |

### Governance RB (6 runbooks)
| Runbook | Description | Game Day |
|---|---|---|
| [RB-GOV-001-compliance-blocked-approval-investigation.md](RB-GOV-001-compliance-blocked-approval-investigation.md) | Compliance-blocked approval | |
| [RB-GOV-002-multi-step-policy-misconfigured.md](RB-GOV-002-multi-step-policy-misconfigured.md) | Multi-step policy misconfiguration | |

### Infrastructure & Operations (10 runbooks)
| Runbook | Description | Game Day |
|---|---|---|
| [postgres-runbook.md](postgres-runbook.md) | PostgreSQL operations | ✅ GD-INF-01 |
| [fuseki-pv-migration.md](fuseki-pv-migration.md) | Fuseki PV migration | |
| [kms-rotation.md](kms-rotation.md) | KMS key rotation | |
| [destroy-staging.md](destroy-staging.md) | Staging environment teardown | |
| [vendor-failure-aws.md](vendor-failure-aws.md) | AWS vendor outage | ✅ GD-INF-02 |
| [s3-test-namespace-cleanup.md](s3-test-namespace-cleanup.md) | S3 test namespace cleanup | |

### E2E & Testing (6 runbooks)
| Runbook | Description | Game Day |
|---|---|---|
| [REAL_MARKETPLACE_E2E.md](REAL_MARKETPLACE_E2E.md) | Marketplace E2E procedures | |
| [REAL_SCHEDULED_INGESTION_EXPORT_E2E.md](REAL_SCHEDULED_INGESTION_EXPORT_E2E.md) | Scheduled ingestion/export E2E | |
| [REAL_VIRTUALIZATION_E2E.md](REAL_VIRTUALIZATION_E2E.md) | Virtualization E2E | |

### Process & Operations (21 runbooks)
| Runbook | Description | Game Day |
|---|---|---|
| [260-cookie-rollout-production-flip.md](260-cookie-rollout-production-flip.md) | Cookie rollout production flip | |
| [260-phase-exit-checklist.md](260-phase-exit-checklist.md) | Phase exit checklist | |
| [admin-feature-flag-flip.md](admin-feature-flag-flip.md) | Feature flag flip procedure | |
| [admin-impersonation.md](admin-impersonation.md) | Admin impersonation | |
| [admin-tenant-deactivation.md](admin-tenant-deactivation.md) | Tenant deactivation | |
| [postmortem-template.md](postmortem-template.md) | Postmortem template | |
| [internal-eng-announcement-protocol.md](internal-eng-announcement-protocol.md) | Internal announcement protocol | |
| [tenant-offboarding.md](tenant-offboarding.md) | Tenant offboarding | |
| ... | (see full directory) | |

## Game Day Exercise Map

| Game Day | Runbooks Exercised | Date | Status |
|---|---|---|---|
| GD-Asset-01 | asset-creation.md, DATA_FIRST_ASSET_CREATION.md | Q3 2026 | Planned |
| GD-Asset-02 | asset-creation-auto-rollback.md | Q3 2026 | Planned |
| GD-LIN-01 | lineage-archive-job-failure.md, lineage-dr.md | Q3 2026 | Planned |
| GD-LIN-02 | lineage-notification-storm.md | Q3 2026 | Planned |
| GD-BR-01 | phase232-breach.md | Q2 2026 | ✅ Complete |
| GD-DSAR-01 | phase232-dsar.md | Q2 2026 | ✅ Complete |
| GD-SEC-01 | RB-AUTH-001-rls-kill-switch.md | Q2 2026 | ✅ Complete |
| GD-INF-01 | postgres-runbook.md | Q2 2026 | ✅ Complete |
| GD-INF-02 | vendor-failure-aws.md | Q3 2026 | Planned |
| GD-VF-01 | vendor-failure-stripe.md | Q3 2026 | Planned |

## Cross-Reference Map

- **Operations docs:** `../operations/` — production runbook, capacity planning, deployment
- **Architecture docs:** `../architecture/` — WebSocket auth, lineage architecture
- **Compliance docs:** `../compliance/` — data residency, retention schedule, DPA
- **ADR index:** `../adr/index.md` — 34 architecture decision records
- **Developer guide:** `../DEVELOPER_GUIDE.md`

## Maintenance

- **Owner:** Platform Engineering
- **Review cadence:** Quarterly (next: 2026-08-15)
- **Update triggers:** After every game day exercise, after every SEV1 incident, after new service launch
