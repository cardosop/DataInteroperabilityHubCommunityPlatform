# Model Serving CLI Usage Guide

Complete guide for using model serving and A/B testing commands in the DataHub CLI.

## Table of Contents

1. [Overview](#overview)
2. [Model Serving Concepts](#model-serving-concepts)
3. [Model Serving Commands](#model-serving-commands)
4. [A/B Testing Commands](#ab-testing-commands)
5. [Workflow Patterns](#workflow-patterns)
6. [Error Handling](#error-handling)
7. [Troubleshooting](#troubleshooting)

## Overview

The DataHub CLI provides comprehensive support for model serving, allowing you to deploy ML models as production-ready API endpoints with contract validation, quality monitoring, and A/B testing capabilities.

### Key Features

- **Model Serving**: Deploy models as API endpoints with custom paths
- **Direct Predictions**: Run predictions using model IDs (no deployment ID needed)
- **Quality Monitoring**: Track accuracy, latency, error rate, and data drift
- **A/B Testing**: Compare model variants with configurable traffic splitting
- **Contract Validation**: Automatic validation of input/output contracts
- **Marketplace Integration**: Serve models through marketplace listings

## Model Serving Concepts

### Serving Deployments

Serving deployments expose ML models as REST API endpoints:
- Models are deployed with optional custom endpoint paths
- Predictions are made directly using model IDs
- Each deployment tracks quality metrics and performance
- Deployments can be monitored, updated, and undeployed

### A/B Testing

A/B testing allows you to compare model performance:
- Split traffic between a base model and variant model
- Traffic split is configurable (e.g., 50:50, 70:30)
- Metrics are tracked separately for each variant
- Results help determine which model performs better

### Quality Metrics

Serving deployments track comprehensive quality metrics:
- **Accuracy**: Model prediction accuracy
- **Latency**: Average response time in milliseconds
- **Error Rate**: Percentage of failed requests
- **Data Drift**: Measure of input data distribution changes
- **Request Counts**: Total, successful, and failed requests

## Model Serving Commands

### Deploy Model for Serving

Deploy a model as a serving endpoint:

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

**Example Output:**
```
Model deployed for serving successfully!
Serving ID: 123e4567-e89b-12d3-a456-426614174000
Model ID: 456e7890-e89b-12d3-a456-426614174001
Status: DEPLOYING
Endpoint URL: https://api.hub.example.com/api/v1/models/my-classifier
```

**Parameters:**
- `--model-id` (required): UUID of the ML model to deploy
- `--endpoint` (optional): Custom endpoint path (default: auto-generated)
- `--format` (optional): Output format (`table` or `json`, default: `table`)

### Run Prediction

Run inference prediction on a served model:

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

**Example Input File (input.json):**
```json
{
  "feature1": 0.5,
  "feature2": 0.8,
  "feature3": 0.3
}
```

**Example Output:**
```
Prediction completed successfully!
Model ID: 456e7890-e89b-12d3-a456-426614174001
Status: success

Output:
{
  "prediction": 0.95,
  "confidence": 0.87,
  "class": "positive"
}
```

**Parameters:**
- `--model-id` (required): UUID of the ML model
- `--input` (required): Input data as JSON string or file path
- `--format` (optional): Output format (`table` or `json`, default: `table`)

### List Serving Deployments

List all serving deployments with optional filters:

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

**Example Output:**
```
Serving ID                              Model ID                               Status               Endpoint
---------------------------------------- ---------------------------------------- -------------------- --------------------------------------------------
123e4567-e89b-12d3-a456-426614174000   456e7890-e89b-12d3-a456-426614174001   READY                https://api.hub.example.com/api/v1/models/my-model
789e0123-e89b-12d3-a456-426614174002   456e7890-e89b-12d3-a456-426614174001   DEPLOYING            N/A
```

**Parameters:**
- `--model-id` (optional): Filter by model ID
- `--status` (optional): Filter by deployment status
- `--limit` (optional): Maximum number of results (default: 20)
- `--offset` (optional): Pagination offset (default: 0)
- `--format` (optional): Output format (`table` or `json`, default: `table`)

### Get Serving Deployment Details

Get detailed information about a specific serving deployment:

```bash
# Get serving details (table format)
datahub ml serving get <serving-id>

# Get serving details (JSON format)
datahub ml serving get <serving-id> --format json
```

**Example Output:**
```
Serving ID: 123e4567-e89b-12d3-a456-426614174000
Model ID: 456e7890-e89b-12d3-a456-426614174001
Status: READY
Endpoint: https://api.hub.example.com/api/v1/models/my-classifier
Created: 2025-01-10T10:00:00Z
Updated: 2025-01-10T10:05:00Z

Metrics:
  Accuracy: 0.95
  Latency: 45.2 ms
  Error Rate: 0.5%
```

**Parameters:**
- `<serving-id>` (required): UUID of the serving deployment
- `--format` (optional): Output format (`table` or `json`, default: `table`)

### Undeploy Serving Deployment

Undeploy a serving deployment:

```bash
# Undeploy a serving deployment
datahub ml serving undeploy <serving-id>

# Output in JSON format
datahub ml serving undeploy <serving-id> --format json
```

**Example Output:**
```
Serving deployment undeployed successfully!
```

**Parameters:**
- `<serving-id>` (required): UUID of the serving deployment to undeploy
- `--format` (optional): Output format (`table` or `json`, default: `table`)

### Get Serving Metrics

Get quality metrics for a serving deployment:

```bash
# Get serving metrics (table format)
datahub ml serving metrics <serving-id>

# Get serving metrics (JSON format)
datahub ml serving metrics <serving-id> --format json
```

**Example Output:**
```
Metrics for Serving Deployment: 123e4567-e89b-12d3-a456-426614174000
Accuracy: 0.95
Average Latency: 45.2 ms
Error Rate: 0.5%
Data Drift: 0.02
Total Requests: 1000
Successful Requests: 995
Failed Requests: 5

Additional Metrics:
{
  "p95_latency_ms": 78.5,
  "p99_latency_ms": 120.3,
  "throughput_rps": 50.2
}
```

**Parameters:**
- `<serving-id>` (required): UUID of the serving deployment
- `--format` (optional): Output format (`table` or `json`, default: `table`)

**Metrics Explained:**
- **Accuracy**: Model prediction accuracy (0.0 to 1.0)
- **Average Latency**: Average response time in milliseconds
- **Error Rate**: Percentage of failed requests (0.0 to 100.0)
- **Data Drift**: Measure of input data distribution changes (0.0 = no drift, 1.0 = maximum drift)
- **Total Requests**: Total number of prediction requests
- **Successful Requests**: Number of successful predictions
- **Failed Requests**: Number of failed predictions

## A/B Testing Commands

### Create A/B Test

Create an A/B test to compare two model variants:

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

**Example Output:**
```
A/B test created successfully!
A/B Test ID: 789e0123-e89b-12d3-a456-426614174002
Base Model ID: 456e7890-e89b-12d3-a456-426614174001
Variant Model ID: 789e0123-e89b-12d3-a456-426614174003
Traffic Split: 50:50
Status: ACTIVE
```

**Parameters:**
- `--model-id` (required): UUID of the base model
- `--variant-id` (required): UUID of the variant model to compare
- `--traffic-split` (required): Traffic split in format "X:Y" where X+Y=100 (e.g., "50:50", "70:30")
- `--format` (optional): Output format (`table` or `json`, default: `table`)

**Traffic Split Format:**
- Must be in format "X:Y" where X and Y are integers
- X and Y must sum to 100
- X represents percentage of traffic to base model
- Y represents percentage of traffic to variant model
- Examples: "50:50", "70:30", "90:10", "80:20"

### List A/B Tests

List all A/B tests with optional filters:

```bash
# List all A/B tests
datahub ml serving ab-test list

# Filter by model ID
datahub ml serving ab-test list --model-id <model-id>

# Output in JSON format
datahub ml serving ab-test list --format json
```

**Example Output:**
```
A/B Test ID                            Base Model ID                          Variant Model ID                       Traffic Split          Status
---------------------------------------- ---------------------------------------- ---------------------------------------- -------------------- ---------------
789e0123-e89b-12d3-a456-426614174002   456e7890-e89b-12d3-a456-426614174001   789e0123-e89b-12d3-a456-426614174003   50:50                  ACTIVE
012e3456-e89b-12d3-a456-426614174004   456e7890-e89b-12d3-a456-426614174001   345e6789-e89b-12d3-a456-426614174005   70:30                  ACTIVE
```

**Parameters:**
- `--model-id` (optional): Filter by model ID (base or variant)
- `--format` (optional): Output format (`table` or `json`, default: `table`)

### Get A/B Test Details

Get detailed information about a specific A/B test:

```bash
# Get A/B test details (table format)
datahub ml serving ab-test get <ab-test-id>

# Get A/B test details (JSON format)
datahub ml serving ab-test get <ab-test-id> --format json
```

**Example Output:**
```
A/B Test ID: 789e0123-e89b-12d3-a456-426614174002
Base Model ID: 456e7890-e89b-12d3-a456-426614174001
Variant Model ID: 789e0123-e89b-12d3-a456-426614174003
Traffic Split: 50:50
Status: ACTIVE
Created: 2025-01-10T10:00:00Z
Updated: 2025-01-10T10:05:00Z

Metrics:
  Base Model:
    Accuracy: 0.95
    Latency: 45.2 ms
    Error Rate: 0.5%
  Variant Model:
    Accuracy: 0.97
    Latency: 42.1 ms
    Error Rate: 0.3%
```

**Parameters:**
- `<ab-test-id>` (required): UUID of the A/B test
- `--format` (optional): Output format (`table` or `json`, default: `table`)

## Workflow Patterns

### Complete Model Serving Workflow

Deploy a model, run predictions, monitor metrics, and undeploy:

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

Create an A/B test, monitor results, and compare performance:

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

Deploy a model with monitoring and quality checks:

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

Compare new model version with existing production model:

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

## Error Handling

### Common Errors and Solutions

#### Invalid Model ID Format

**Error:**
```
Invalid model-id format: invalid-uuid
```

**Solution:**
Ensure the model ID is a valid UUID format:
```bash
# Correct format
datahub ml serving deploy --model-id 123e4567-e89b-12d3-a456-426614174000
```

#### Invalid Traffic Split Format

**Error:**
```
Invalid traffic split format: Traffic split percentages must sum to 100
```

**Solution:**
Ensure traffic split sums to 100:
```bash
# Correct format
datahub ml serving ab-test create \
  --model-id <base-id> \
  --variant-id <variant-id> \
  --traffic-split "50:50"  # Sums to 100
```

#### Invalid JSON Input

**Error:**
```
Invalid input format: Invalid JSON format
```

**Solution:**
Ensure input is valid JSON:
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

**Error:**
```
Failed to deploy model for serving: Model not found
```

**Solution:**
Verify the model exists:
```bash
# List models to find correct ID
datahub ml models list

# Verify model ID
datahub ml models get <model-id>
```

#### Serving Deployment Not Ready

**Error:**
```
Failed to run prediction: Serving deployment not ready
```

**Solution:**
Wait for deployment to be ready:
```bash
# Check deployment status
datahub ml serving get <serving-id>

# Wait until status is READY before running predictions
```

### Error Handling Best Practices

1. **Always validate inputs**: Check model IDs, input JSON, and traffic splits before running commands
2. **Check deployment status**: Verify serving deployments are READY before running predictions
3. **Monitor metrics**: Regularly check metrics to catch issues early
4. **Handle errors gracefully**: Use JSON format for scripting to parse error messages
5. **Verify model existence**: Check that models exist before deploying

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

## Additional Resources

- **[ODH Usage Guide](ODH_USAGE.md)** - Complete guide for ML/ODH commands
- **[CLI README](../README.md)** - General CLI documentation
- **[API Documentation](https://api.hub.example.com/docs)** - API reference documentation

## Command Reference

### Model Serving Commands

| Command | Description | Required Parameters |
|---------|-------------|---------------------|
| `deploy` | Deploy model for serving | `--model-id` |
| `predict` | Run prediction | `--model-id`, `--input` |
| `list` | List serving deployments | None |
| `get` | Get serving details | `<serving-id>` |
| `undeploy` | Undeploy serving | `<serving-id>` |
| `metrics` | Get serving metrics | `<serving-id>` |

### A/B Testing Commands

| Command | Description | Required Parameters |
|---------|-------------|---------------------|
| `ab-test create` | Create A/B test | `--model-id`, `--variant-id`, `--traffic-split` |
| `ab-test list` | List A/B tests | None |
| `ab-test get` | Get A/B test details | `<ab-test-id>` |
