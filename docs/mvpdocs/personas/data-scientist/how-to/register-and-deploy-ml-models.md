# How to Register and Deploy ML Models

**Persona:** Data Scientist
**Phase:** 285.9b (ML GA Closure)
**Status:** ✅ Implemented

## Overview

Register ML models trained in ODH (Open Data Hub), link them to Hub assets and contracts, deploy for inference, and monitor performance.

## Prerequisites

- `ml_enabled` feature flag enabled for your tenant
- ODH model trained and available (model ID + version)
- A Hub asset and contract to link
- `ml:write` scope on your API key

## Steps

### 1. Register a Model

```bash
datahub ml models create \
  --odh-model-id "my-customer-churn-model" \
  --odh-model-version "v2" \
  --asset-id "<asset_uuid>" \
  --model-type "classification" \
  --contract-id "<contract_uuid>"
```

### 2. Deploy for Inference

```bash
datahub ml inference deploy \
  --model-id "<model_uuid>" \
  --replicas 2 \
  --gpu-required true
```

### 3. Run Inference

Sync (real-time):
```bash
datahub ml inference predict \
  --deployment-id "<deployment_uuid>" \
  --input '{"features": [1.2, 3.4, 5.6]}'
```

Async (queued):
```bash
datahub ml inference predict-async \
  --deployment-id "<deployment_uuid>" \
  --input '{"features": [1.2, 3.4, 5.6]}'
# Returns job_id — poll with:
datahub ml inference job-status --deployment-id "<id>" --job-id "<job_id>"
```

### 4. Monitor Performance

```bash
datahub ml inference metrics --model-id "<model_uuid>"
```

## See Also

- [Product Guide: ML Model Registry](../../../PRODUCT_GUIDE.md)
- [RB-ML-001: ODH Connectivity Failure](../../../runbooks/RB-ML-001-odh-connectivity-failure.md)
- [RB-ML-002: Model Deployment Failure](../../../runbooks/RB-ML-002-model-deployment-failure.md)
