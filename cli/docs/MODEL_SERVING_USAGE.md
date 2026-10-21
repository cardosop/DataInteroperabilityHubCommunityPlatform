# Model Serving CLI Command Reference

> **Canonical guide:** [../../sdk/python/docs/MODEL_SERVING_USAGE.md](../../sdk/python/docs/MODEL_SERVING_USAGE.md)
> (concepts, SDK code, and setup — this file keeps ONLY the CLI command
> examples; W6.4 dedupe of the diverging `cli/docs` vs `sdk/python/docs`
> copies).

### Deploy Model for Serving
```bash
# Basic deployment
datahub ml serving deploy --model-id <model-id>

# Deploy with custom endpoint path
datahub ml serving deploy \
  --model-id <model-id> \
  --endpoint /api/v1/models/my-classifier

# Output in JSON format
datahub ml serving deploy \
  --model-id <model-id> \
  --format json
```

### Run Prediction
```bash
# Predict with JSON string input
datahub ml serving predict \
  --model-id <model-id> \
  --input '{"feature1": 0.5, "feature2": 0.8}'

# Predict with input file
datahub ml serving predict \
  --model-id <model-id> \
  --input input.json

# Output in JSON format
datahub ml serving predict \
  --model-id <model-id> \
  --input input.json \
  --format json
```

### List Serving Deployments
```bash
# List all serving deployments
datahub ml serving list

# Filter by model ID
datahub ml serving list --model-id <model-id>

# Filter by status
datahub ml serving list --status READY

# Combine filters with pagination
datahub ml serving list \
  --model-id <model-id> \
  --status READY \
  --limit 50 \
  --offset 0

# Output in JSON format
datahub ml serving list --format json
```

### Get Serving Deployment Details
```bash
# Get serving details (table format)
datahub ml serving get <serving-id>

# Get serving details (JSON format)
datahub ml serving get <serving-id> --format json
```

### Undeploy Serving Deployment
```bash
# Undeploy a serving deployment
datahub ml serving undeploy <serving-id>

# Output in JSON format
datahub ml serving undeploy <serving-id> --format json
```

### Get Serving Metrics
```bash
# Get serving metrics (table format)
datahub ml serving metrics <serving-id>

# Get serving metrics (JSON format)
datahub ml serving metrics <serving-id> --format json
```

### Create A/B Test
```bash
# Create A/B test with 50:50 traffic split
datahub ml serving ab-test create \
  --model-id <base-model-id> \
  --variant-id <variant-model-id> \
  --traffic-split "50:50"

# Create A/B test with 70:30 traffic split
datahub ml serving ab-test create \
  --model-id <base-model-id> \
  --variant-id <variant-model-id> \
  --traffic-split "70:30"

# Output in JSON format
datahub ml serving ab-test create \
  --model-id <base-model-id> \
  --variant-id <variant-model-id> \
  --traffic-split "50:50" \
  --format json
```

### List A/B Tests
```bash
# List all A/B tests
datahub ml serving ab-test list

# Filter by model ID
datahub ml serving ab-test list --model-id <model-id>

# Output in JSON format
datahub ml serving ab-test list --format json
```

### Get A/B Test Details
```bash
# Get A/B test details (table format)
datahub ml serving ab-test get <ab-test-id>

# Get A/B test details (JSON format)
datahub ml serving ab-test get <ab-test-id> --format json
```

### Complete Model Serving Workflow
```bash
# 1. Deploy model for serving
datahub ml serving deploy \
  --model-id <model-id> \
  --endpoint /api/v1/models/my-classifier

# Save the serving ID from output
SERVING_ID="123e4567-e89b-12d3-a456-426614174000"

# 2. Wait for deployment to be ready (check status)
datahub ml serving get $SERVING_ID

# 3. Run predictions
datahub ml serving predict \
  --model-id <model-id> \
  --input input.json

# 4. Monitor metrics
datahub ml serving metrics $SERVING_ID

# 5. List all serving deployments
datahub ml serving list --model-id <model-id>

# 6. Undeploy when done
datahub ml serving undeploy $SERVING_ID
```

### A/B Testing Workflow
```bash
# 1. Deploy base model
datahub ml serving deploy --model-id <base-model-id>

# 2. Deploy variant model
datahub ml serving deploy --model-id <variant-model-id>

# 3. Create A/B test
datahub ml serving ab-test create \
  --model-id <base-model-id> \
  --variant-id <variant-model-id> \
  --traffic-split "50:50"

# Save the A/B test ID from output
AB_TEST_ID="789e0123-e89b-12d3-a456-426614174002"

# 4. Monitor A/B test results
datahub ml serving ab-test get $AB_TEST_ID

# 5. List all A/B tests
datahub ml serving ab-test list --model-id <base-model-id>
```

### Production Deployment Pattern
```bash
# 1. Deploy model
SERVING_ID=$(datahub ml serving deploy \
  --model-id <model-id> \
  --endpoint /api/v1/models/production-classifier \
  --format json | jq -r '.serving_id')

# 2. Verify deployment
datahub ml serving get $SERVING_ID

# 3. Run test predictions
datahub ml serving predict \
  --model-id <model-id> \
  --input test-input.json

# 4. Monitor quality metrics
datahub ml serving metrics $SERVING_ID

# 5. Check for data drift (should be low)
# If data drift > 0.1, consider retraining the model
```

### Model Version Comparison Pattern
```bash
# 1. Deploy new model version
datahub ml serving deploy --model-id <new-model-id>

# 2. Create A/B test with small traffic to new model
datahub ml serving ab-test create \
  --model-id <production-model-id> \
  --variant-id <new-model-id> \
  --traffic-split "90:10"

# 3. Monitor metrics for both models
AB_TEST_ID="..."
datahub ml serving ab-test get $AB_TEST_ID

# 4. If new model performs better, gradually increase traffic
# Update A/B test to 70:30, then 50:50, then 0:100
# 5. Once confident, undeploy old model
datahub ml serving undeploy <old-serving-id>
```

#### Invalid Model ID Format
```bash
# Correct format
datahub ml serving deploy --model-id 123e4567-e89b-12d3-a456-426614174000
```

#### Invalid Traffic Split Format
```bash
# Correct format
datahub ml serving ab-test create \
  --model-id <base-id> \
  --variant-id <variant-id> \
  --traffic-split "50:50"  # Sums to 100
```

#### Invalid JSON Input
```bash
# Correct format
datahub ml serving predict \
  --model-id <model-id> \
  --input '{"feature1": 0.5, "feature2": 0.8}'

# Or use a JSON file
datahub ml serving predict \
  --model-id <model-id> \
  --input input.json
```

#### Model Not Found
```bash
# List models to find correct ID
datahub ml models list

# Verify model ID
datahub ml models get <model-id>
```

#### Serving Deployment Not Ready
```bash
# Check deployment status
datahub ml serving get <serving-id>

# Wait until status is READY before running predictions
```

## Troubleshooting

### Deployment Issues

**Problem: Deployment stuck in DEPLOYING status**

**Solutions:**
1. Check API service health: `curl http://localhost:8000/health/`
2. Verify model exists: `datahub ml models get <model-id>`
3. Check API logs for errors
4. Retry deployment after a few minutes

**Problem: Deployment fails immediately**

**Solutions:**
1. Verify model ID is correct
2. Check model status (should be TRAINED or DEPLOYED)
3. Verify API key has proper permissions
4. Check API service logs

### Prediction Issues

**Problem: Predictions return errors**

**Solutions:**
1. Verify serving deployment is READY: `datahub ml serving get <serving-id>`
2. Check input JSON format is correct
3. Verify input matches model's expected schema
4. Check serving metrics for error rate: `datahub ml serving metrics <serving-id>`

**Problem: Predictions are slow**

**Solutions:**
1. Check latency metrics: `datahub ml serving metrics <serving-id>`
2. Verify model is optimized for production
3. Check API service resource limits
4. Consider scaling deployment

### A/B Testing Issues

**Problem: A/B test not splitting traffic correctly**

**Solutions:**
1. Verify traffic split format: Must be "X:Y" where X+Y=100
2. Check A/B test status: `datahub ml serving ab-test get <ab-test-id>`
3. Verify both models are deployed and READY
4. Check API service logs for routing issues

**Problem: Cannot compare metrics between variants**

**Solutions:**
1. Ensure A/B test has been running long enough to collect data
2. Check that both models are receiving traffic
3. Verify metrics are being tracked: `datahub ml serving ab-test get <ab-test-id>`

### Metrics Issues

**Problem: Metrics not updating**

**Solutions:**
1. Verify serving deployment is receiving requests
2. Check metrics endpoint is accessible
3. Verify API service is collecting metrics
4. Wait a few minutes for metrics to update

**Problem: Data drift is high**

**Solutions:**
1. Review input data distribution changes
2. Consider retraining the model with new data
3. Update data preprocessing pipeline if needed
4. Monitor drift trends over time
