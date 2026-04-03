# RB-ML-001: ML Platform Troubleshooting

**Severity**: P2 (model deployment failure) to P3 (training timeout)
**Last Updated**: 2026-03-22
**Owner**: Platform Team

---

## ML-5: ODH Deployment Failures

### Symptoms

- `deploy_model()` succeeds locally but model not serving predictions
- `deployment_id` set but inference returns 404/503
- ODH Inference Scheduler logs show deployment errors

### Diagnosis

```bash
# Check model deployment status
docker exec hub-test-api python /app/hub/manage.py shell -c "
from hub.apps.ml.models import MLModel
model = MLModel.objects.get(id='<model-id>')
print(f'Status: {model.status}')
print(f'Deployment ID: {model.deployment_id}')
print(f'ODH Model ID: {model.odh_model_id}')
print(f'ODH Version: {model.odh_model_version}')
"

# Check ODH Inference Scheduler health
curl http://localhost:8097/health/

# Check ODH Model Registry
curl http://localhost:8095/api/v1/models/<odh-model-id>/
```

### Resolution

1. **ODH service down**: Restart `docker compose restart odh-inference-scheduler`
2. **Model not registered**: Re-sync via `sync_model_from_odh()`
3. **Deployment stuck**: Undeploy and redeploy:

```bash
docker exec hub-test-api python /app/hub/manage.py shell -c "
from hub.apps.ml.services import ModelRegistryBridgeService
svc = ModelRegistryBridgeService(tenant_id='<tenant-id>', user_id='<user-id>')
svc.undeploy_model('<model-id>')
svc.deploy_model('<model-id>')
"
```

---

## ML-6: Training Timeout Configuration

### Symptoms

- Training jobs timing out before completion
- Large models failing with timeout errors

### Diagnosis

```bash
# Check current timeout for a tenant
docker exec hub-test-api python /app/hub/manage.py shell -c "
from hub.apps.tenants.models import Tenant
tenant = Tenant.objects.select_related('plan').get(slug='<slug>')
if tenant.plan and tenant.plan.limits_json:
    print(f'Plan timeout: {tenant.plan.limits_json.get(\"ml_training_timeout\", \"not set\")}')
else:
    print('No plan or limits set — default 3600s')
"
```

### Resolution

Timeout is resolved in priority order:

| Priority | Source | How to Set |
|----------|--------|------------|
| 1 | `training_config.timeout` | Pass in API call |
| 2 | `plan.limits_json.ml_training_timeout` | Update tenant plan |
| 3 | Default | 3600 seconds (1 hour) |

```bash
# Update plan timeout (for all tenants on this plan)
docker exec hub-test-api python /app/hub/manage.py shell -c "
from hub.apps.tenants.models import TenantPlan
plan = TenantPlan.objects.get(slug='pro')
plan.limits_json['ml_training_timeout'] = 7200  # 2 hours
plan.save()
print(f'Updated: {plan.limits_json}')
"
```

---

## ML-1: Deployment ID Verification

### Symptoms

- Model shows DEPLOYED but `deployment_id` is None
- Inference workflow can't find deployment

### Diagnosis

```bash
# Check all deployed models
docker exec hub-test-api python /app/hub/manage.py shell -c "
from hub.apps.ml.models import MLModel
deployed = MLModel.objects.filter(status='DEPLOYED')
for m in deployed:
    status = 'OK' if m.deployment_id else 'MISSING deployment_id'
    print(f'{m.odh_model_name} v{m.odh_model_version}: {status} ({m.deployment_id})')
"
```

### Resolution

If `deployment_id` is missing on a DEPLOYED model, re-deploy:

```bash
docker exec hub-test-api python /app/hub/manage.py shell -c "
from hub.apps.ml.services import ModelRegistryBridgeService
svc = ModelRegistryBridgeService(tenant_id='<tenant-id>', user_id='<user-id>')
# Undeploy first (resets to TRAINED)
svc.undeploy_model('<model-id>')
# Deploy again (sets deployment_id)
model = svc.deploy_model('<model-id>')
print(f'Deployed: {model.deployment_id}')
"
```

The `deploy_model()` method generates `deployment_id` as `deploy-{odh_model_id}-{version}` and uses `select_for_update()` for concurrency safety.
