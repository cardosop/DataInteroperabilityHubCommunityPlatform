# ODH (Open Data Hub) CLI Command Reference

> **Canonical guide:** [../../sdk/python/docs/ODH_USAGE.md](../../sdk/python/docs/ODH_USAGE.md)
> (concepts, SDK code, and setup — this file keeps ONLY the CLI command
> examples; W6.4 dedupe of the diverging `cli/docs` vs `sdk/python/docs`
> copies).

### List Models
```bash
# List all models
datahub ml models list

# Filter by asset ID
datahub ml models list --asset-id <asset-id>

# Filter by status
datahub ml models list --status TRAINED

# Combine filters with pagination
datahub ml models list \
  --asset-id <asset-id> \
  --status DEPLOYED \
  --limit 50 \
  --offset 0

# Output in JSON format
datahub ml models list --format json
```

### Get Model Details
```bash
# Get model details (table format)
datahub ml models get <model-id>

# Get model details (JSON format)
datahub ml models get <model-id> --format json
```

### Create Model
```bash
# Create model with required fields
datahub ml models create \
  --odh-model-id <odh-model-id> \
  --odh-model-name "My Model" \
  --odh-model-version "1.0.0" \
  --model-type CLASSIFICATION

# Create model linked to asset
datahub ml models create \
  --odh-model-id <odh-model-id> \
  --odh-model-name "Customer Churn Predictor" \
  --odh-model-version "1.0.0" \
  --model-type CLASSIFICATION \
  --asset-id <asset-id>

# Create model linked to asset and contract
datahub ml models create \
  --odh-model-id <odh-model-id> \
  --odh-model-name "Sales Forecast" \
  --odh-model-version "2.1.0" \
  --model-type REGRESSION \
  --asset-id <asset-id> \
  --contract-id <contract-id>
```

### Update Model
```bash
# Update model status
datahub ml models update <model-id> --status DEPLOYED

# Update linked asset
datahub ml models update <model-id> --asset-id <new-asset-id>

# Update linked contract
datahub ml models update <model-id> --contract-id <new-contract-id>

# Update multiple fields
datahub ml models update <model-id> \
  --asset-id <new-asset-id> \
  --status TRAINED
```

### Delete Model
```bash
datahub ml models delete <model-id>
```

### List Model Versions
```bash
datahub ml models versions <model-id>
```

### Submit Training Job
```bash
# Submit with JSON config string
datahub ml training submit \
  --model-id <model-id> \
  --dataset-id <dataset-id> \
  --config '{"epochs": 100, "batch_size": 32, "learning_rate": 0.001}'

# Submit with config file
datahub ml training submit \
  --model-id <model-id> \
  --dataset-id <dataset-id> \
  --config training-config.json
```

### List Training Jobs
```bash
# List all training jobs
datahub ml training list

# Filter by model ID
datahub ml training list --model-id <model-id>

# Filter by status
datahub ml training list --status RUNNING

# Combine filters with pagination
datahub ml training list \
  --model-id <model-id> \
  --status COMPLETED \
  --limit 20 \
  --offset 0
```

### Get Training Job Details
```bash
datahub ml training get <job-id>
```

### Cancel Training Job
```bash
datahub ml training cancel <job-id>
```

### Get Training Logs
```bash
# Get all logs
datahub ml training logs <job-id>

# Get last 100 lines
datahub ml training logs <job-id> --lines 100
```

### Deploy Model
```bash
# Deploy with default configuration
datahub ml inference deploy --model-id <model-id>

# Deploy with custom configuration
datahub ml inference deploy \
  --model-id <model-id> \
  --config deployment-config.json
```

### Run Prediction
```bash
# Predict with JSON input string
datahub ml inference predict \
  --deployment-id <deployment-id> \
  --input-data '{"feature1": 0.5, "feature2": 0.8}'

# Predict with input file
datahub ml inference predict \
  --deployment-id <deployment-id> \
  --input-data input.json
```

### List Deployments
```bash
# List all deployments
datahub ml inference list

# Filter by model ID
datahub ml inference list --model-id <model-id>

# Filter by status
datahub ml inference list --status DEPLOYED

# Combine filters with pagination
datahub ml inference list \
  --model-id <model-id> \
  --status DEPLOYED \
  --limit 20 \
  --offset 0
```

### Get Deployment Details
```bash
datahub ml inference get <deployment-id>
```

### Undeploy Model
```bash
datahub ml inference undeploy <deployment-id>
```

### Get Inference Metrics
```bash
# Get all metrics
datahub ml inference metrics <deployment-id>

# Get metrics for time range
datahub ml inference metrics <deployment-id> \
  --start-time "2025-01-15T00:00:00Z" \
  --end-time "2025-01-15T23:59:59Z"
```

### Complete ML Lifecycle
```bash
# Create model link
datahub ml models create \
  --odh-model-id my-model-123 \
  --odh-model-name "Customer Churn Predictor" \
  --odh-model-version "1.0.0" \
  --model-type CLASSIFICATION \
  --asset-id <asset-id>
```

```bash
# Submit training job
datahub ml training submit \
  --model-id <model-id> \
  --dataset-id <dataset-id> \
  --config training-config.json

# Monitor training
datahub ml training get <job-id>
datahub ml training logs <job-id>

# Update model status after training
datahub ml models update <model-id> --status TRAINED
```

```bash
# Deploy for inference
datahub ml inference deploy \
  --model-id <model-id> \
  --config deployment-config.json

# Wait for deployment to be ready
datahub ml inference get <deployment-id>
```

```bash
# Make predictions
datahub ml inference predict \
  --deployment-id <deployment-id> \
  --input-data input.json

# Monitor metrics
datahub ml inference metrics <deployment-id>
```

```bash
# Mark as deployed
datahub ml models update <model-id> --status DEPLOYED
```

### Model Versioning Workflow
```bash
# Create new version of existing model
datahub ml models create \
  --odh-model-id my-model-123 \
  --odh-model-name "Customer Churn Predictor" \
  --odh-model-version "2.0.0" \
  --model-type CLASSIFICATION \
  --asset-id <asset-id>
```

```bash
# Get all versions
datahub ml models versions <model-id>
```

```bash
# Deploy new version
datahub ml inference deploy --model-id <new-version-model-id>

# Undeploy old version
datahub ml inference undeploy <old-deployment-id>
```

### Error Recovery Workflow
```bash
# Check training job status
datahub ml training get <job-id>

# Review logs
datahub ml training logs <job-id>

# Update model status
datahub ml models update <model-id> --status FAILED

# Fix issues and resubmit
datahub ml training submit \
  --model-id <model-id> \
  --dataset-id <dataset-id> \
  --config fixed-training-config.json
```

```bash
# Check deployment status
datahub ml inference get <deployment-id>

# Undeploy failed deployment
datahub ml inference undeploy <deployment-id>

# Update model status
datahub ml models update <model-id> --status TRAINED

# Retry deployment with different config
datahub ml inference deploy \
  --model-id <model-id> \
  --config retry-deployment-config.json
```

### Deploy / Undeploy / Rollback
```bash
# Deploy a model (optionally with config file)
datahub ml deploy <model_id> --config-file deploy-config.json

# Undeploy a model
datahub ml undeploy <model_id>

# Rollback to a previous version
datahub ml rollback <model_odh_id> --version v2
```

### Marketplace Publishing
```bash
# Publish model to the internal marketplace
datahub ml marketplace-publish <model_id> --pricing-model REQUEST_APPROVAL
```

### Plan Limits
```bash
# Show current ML subscription plan
datahub ml plan show

# Show ML-specific plan limits
datahub ml plan limits
```

## Troubleshooting

### Model Not Appearing in List

**Problem:** Model created but not visible in list.

**Solutions:**
1. Check filters: `datahub ml models list` (no filters)
2. Verify model ID: `datahub ml models get <model-id>`
3. Check status filter: Models with certain statuses may be filtered out

### Training Job Stuck

**Problem:** Training job remains in PENDING or RUNNING status.

**Solutions:**
1. Check job details: `datahub ml training get <job-id>`
2. Review logs: `datahub ml training logs <job-id>`
3. Check Hub job status: Use the Hub Job ID to check in the jobs system
4. Cancel and resubmit if necessary: `datahub ml training cancel <job-id>`

### Deployment Not Responding

**Problem:** Deployment exists but predictions fail.

**Solutions:**
1. Check deployment status: `datahub ml inference get <deployment-id>`
2. Verify endpoint: Ensure endpoint URL is accessible
3. Check metrics: `datahub ml inference metrics <deployment-id>`
4. Review deployment configuration: Ensure resources are sufficient

### Model Versions Not Found

**Problem:** `datahub ml models versions` returns no results.

**Solutions:**
1. Verify model has ODH Model ID: `datahub ml models get <model-id>`
2. Check if other versions exist with same ODH Model ID
3. Ensure model was created with proper ODH Model ID
