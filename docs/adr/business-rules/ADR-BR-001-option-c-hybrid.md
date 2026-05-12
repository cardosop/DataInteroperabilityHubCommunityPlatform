# ADR-BR-001: Option C (Hybrid) Architecture for Business Rules

**Status:** Accepted
**Date:** 2026-05-12
**Phase:** 274

## Context

The business rules subsystem had architectural drift:
1. `BusinessRulesRegistry.execute_rules()` was dead code
2. No `RuleChain` primitive existed
3. 25 rule classes manually duplicated OTel + audit emission

## Decision

Adopt **Option C (Hybrid)**:
- Direct rule-class instantiation as canonical hot path
- New `RuleChain` primitive (`hub/apps/core/business_rules/chains.py`) for multi-rule operations
- Chain runner handles single audit event + OTel span per chain execution
- Per-rule failure counters stay at rule level for granularity

## Consequences

- Dead orchestration methods removed (Phase 274.6)
- `StructuralFloorRule`, `KYBVerificationRule`, `AssetActivationRule` promoted to composable rules
- Migration to chains is additive; existing direct callers continue to work
