# JOURNEY-DS-001 — Register and Deploy ML Model

**Persona:** Data Scientist (DS)
**Priority:** P1
**Phase:** 285 (GA)

## Goal

Register a trained ML model in the Meshant model registry and deploy it
to the ODH inference endpoint for real-time serving.

## Steps

1. **Register model** (`POST /api/v1/ml/models/`): Provide model name,
   framework (PyTorch/TensorFlow/ONNX), artifact reference (S3 URI or
   HuggingFace model ID), and metadata tags.

2. **Create model version** (`POST /api/v1/ml/models/{id}/versions/`):
   Upload model artifact. Schema validation runs automatically.

3. **Deploy to inference** (`POST /api/v1/ml/models/{id}/deploy/`):
   Select deployment target (ODH inference scheduler). Configure
   auto-scaling parameters (min/max replicas).

4. **Verify deployment** (`GET /api/v1/ml/models/{id}/inference/`):
   Send a test inference request. Verify response latency and shape.

## Expected Outcome

Model is registered, versioned, deployed, and serving inference requests.

## Related

- Feature flag: `ml_enabled` (GA, opt-in)
- Runbook: `docs/runbooks/RB-ML-001-odh-connectivity-failure.md`
- How-to: `docs/mvpdocs/personas/data-scientist/how-to/register-and-deploy-ml-models.md`
