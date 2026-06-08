# RB-ML-001: ODH Connectivity Failure

**Owner:** ML Engineering Team | **Severity:** Critical | **ID:** RB-ML-001

## 1. Overview
This runbook covers failures when the ODH (Open Data Hub) inference scheduler is unreachable or returns errors. ODH is required for model deployment, inference prediction, and training job submission.

## 2. Symptoms
- `POST /predict/` returns 503 `ODH_SERVICE_UNAVAILABLE`
- `POST /predict-async/` enqueues but jobs never process
- `POST /deploy/`, `DELETE /deployments/{id}/` return 503
- `TrainingJobViewSet.create()` fails with 503
- `service._inference_client` is None in the view

## 3. Diagnosis
```bash
# Check ODH endpoint health
curl -s https://odh-api.<cluster>.openshift.com/healthz
# Check Prefect flow status
prefect flow-run ls --flow-name ml-inference-flow --limit 10
```
## 4. Impact
- All model deployment, inference, and training operations fail
- Async jobs remain queued indefinitely
- Tenant inference quota is consumed by failed sync attempts

## 5. Resolution
1. Verify ODH cluster is running: `oc get nodes -l node-role.kubernetes.io/worker`
2. Check ODH operator status: `oc get csv -n opendatahub`
3. Restart the inference scheduler: `oc rollout restart deployment/odh-model-controller -n opendatahub`
4. Verify network connectivity from the worker node to the ODH API

## 6. Escalation
| Level | Contact | When |
|-------|---------|------|
| L1 | ML Engineering on-call | Any 503 from ODH endpoints |
| L2 | OpenShift Admin | ODH cluster issues |
| L3 | ODH vendor support | Persistent ODH failures |

## 7. Prevention
- Monitor ODH health endpoint at 30s intervals
- Set up Prefect flow alerts for `ml-inference-flow` failures
- Circuit-breaker: after 5 consecutive ODH failures, stop enqueuing new jobs for 60s
- Document ODH version compatibility matrix
