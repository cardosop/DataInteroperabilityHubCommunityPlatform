# RB-ML-002: Model Deployment Failure

**Owner:** ML Engineering Team | **Severity:** High | **ID:** RB-ML-002

## 1. Overview
This runbook covers failures during ML model deployment, undeployment, and inference setup. Includes GPU allocation failures, model artifact loading errors, and deployment timeout.

## 2. Symptoms
- `POST /deploy/` returns 500 with error detail
- `GPUAllocationFailed` error in inference logs
- Deployment status stuck in "DEPLOYING" for >5 minutes
- `POST /predict/` returns "model not deployed"
- `MLInferenceThrottle` 429 responses for inference endpoints

## 3. Diagnosis
```bash
# Check GPU pool state
cat /tmp/meshant_gpu_pool_state.json | python -m json.tool
# Check inference queue depth
python hub/manage.py shell -c "from hub.apps.ml.inference_queue import InferenceQueue; q=InferenceQueue(); print(q.queue_depth)"
# Check deployment status via API
curl -H "Authorization: ..." /api/v1/ml/inference/deployments/<id>/
```
## 4. Impact
- Model cannot serve predictions
- Async inference jobs in queue cannot be processed
- A/B test cannot be started if base model not deployed

## 5. Resolution
1. GPU allocation failure: check `gpu_pool_state.json` for available GPUs; verify K8s node has GPUs
2. Model artifact loading: verify the model file exists in the ODH model registry
3. Deployment timeout: increase `deployment_timeout_seconds` in `source_config`
4. Undeploy and retry: `DELETE /deployments/{id}/` → `POST /deploy/`
5. Check `MLInferenceThrottle` rate (10/sec per tenant) — reduce request rate

## 6. Escalation
| Level | Contact | When |
|-------|---------|------|
| L1 | ML Engineering on-call | Deployment stuck >5 min |
| L2 | GPU Infrastructure team | GPU allocation failures |
| L3 | ODH vendor support | Model artifact loading errors |

## 7. Prevention
- Pre-warm GPU pool on worker node startup
- Run `dbt parse`-style validation on model artifacts before deployment
- Set deployment timeout to 300s default (configurable)
- Monitor `ml_inference_queue_depth` for queue buildup
- Alert when `MODEL_UNDEPLOYED` rate exceeds baseline
