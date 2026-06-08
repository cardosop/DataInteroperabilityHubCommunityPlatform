# JOURNEY-DS-002 — Run AB Test

**Persona:** Data Scientist (DS)
**Priority:** P2
**Phase:** 285 (GA)

## Goal

Create and run an AB test to compare two model versions against live
traffic, with statistical significance tracking.

## Steps

1. **Create AB test** (`POST /api/v1/ml/ab-tests/`): Select two model
   versions (control and treatment). Define traffic split (default 50/50).
   Set evaluation metric (accuracy, latency, throughput).

2. **Start test** (`POST /api/v1/ml/ab-tests/{id}/start/`): Begin
   routing traffic to both model versions.

3. **Monitor results** (`GET /api/v1/ml/ab-tests/{id}/results/`):
   View real-time metric comparison, confidence intervals, and
   statistical significance (p-value).

4. **Conclude test** (`POST /api/v1/ml/ab-tests/{id}/conclude/`):
   Promote the winning model version or discard if inconclusive.

## Expected Outcome

Statistically significant comparison between two model versions with a
clear winner promoted to production.

## Related

- Feature flag: `ml_enabled` (GA, opt-in)
- Model: `hub/apps/ml/models.py` — `ABTest`
