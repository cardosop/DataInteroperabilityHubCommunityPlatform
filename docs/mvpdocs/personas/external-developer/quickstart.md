# External Developer Quickstart

This guide takes you from zero to a working API integration in under ten
minutes. By the end you will have installed the SDK, made your first API
call, handled an error, and registered a webhook.

**Prerequisites:**

- Python 3.10 or later.
- A Meshant API key (obtain from your Tenant Admin or the Meshant web UI
  under **Settings > API Keys**).
- The base URL for your Meshant instance (e.g.,
  `https://meshant-internal.example.com`).


## Step 1: Get an API Key

1. Log in to the Meshant web UI.
2. Navigate to **Settings > API Keys**.
3. Click **Create API Key**.
4. Give the key a descriptive name (e.g., `etl-pipeline-prod`).
5. Select the scopes the key needs (e.g., `assets:read`,
   `search:read`, `webhooks:manage`).
6. Copy the key. You will not be able to see it again.

Store the key securely. Set it as an environment variable:

```bash
export DATAHUB_API_KEY="your-api-key-here"
export DATAHUB_BASE_URL="https://meshant-internal.example.com"
```


## Step 2: Install the SDK

```bash
pip install datahub-interoperability
```

Verify the installation:

```bash
python -c "import datahub_interoperability; print(datahub_interoperability.__version__)"
```


## Step 3: Make Your First API Call

List assets available to your tenant:

```python
from datahub_interoperability import DataHubClient, DataHubClientConfig

config = DataHubClientConfig(
    base_url="https://meshant-internal.example.com",
    api_key="your-api-key-here",
)
client = DataHubClient(config=config)

# Or use environment variables:
# client = DataHubClient.from_env()

assets = client.assets.list(status="ACTIVE", limit=10)
for asset in assets:
    print(f"{asset.id}  {asset.name}  [{asset.status}]")
```

Or use the CLI directly:

```bash
datahub-cli assets list --status ACTIVE --limit 10 --format table
```

Expected output:

```
ID                                       Name                           Status
---------------------------------------------------------------------------------------------------------
a1b2c3d4-...                             Customer Demographics          ACTIVE
e5f6g7h8-...                             Revenue Forecast Q4            ACTIVE
```


## Step 4: Handle Errors

Meshant returns structured error responses. The SDK raises typed
exceptions:

```python
from datahub_interoperability.errors import (
    NotFoundError,
    AuthenticationError,
    FeatureGatedError,
)

try:
    asset = client.assets.get("nonexistent-id")
except NotFoundError as e:
    print(f"Asset not found: {e.message}")
except AuthenticationError as e:
    print(f"Auth failed: {e.message}")
except FeatureGatedError as e:
    # Post-MVP feature -- the error includes roadmap context
    print(f"Feature not available: {e.message}")
    print(f"Error code: {e.error_code}")  # "FEATURE_GATED"
```

The `FeatureGatedError` is raised when you call an endpoint that is
gated behind the MVP boundary (e.g., `mesh/` or `ml/` prefix endpoints).
The error message explains which release will include the feature.


## Step 5: Set Up a Webhook Receiver

Webhooks let you react to platform events without polling.

### Register a webhook

```python
webhook = client.webhooks.create(
    url="https://your-app.example.com/webhooks/meshant",
    events=["asset.published", "dq.check.completed", "contract.created"],
    secret="your-hmac-secret",
)
print(f"Webhook ID: {webhook.id}, Status: {webhook.status}")
```

Or via CLI:

```bash
datahub-cli webhooks create \
  --url "https://your-app.example.com/webhooks/meshant" \
  --events "asset.published,dq.check.completed" \
  --secret "your-hmac-secret"
```

### Build a minimal receiver (Flask example)

```python
import hmac
import hashlib
from flask import Flask, request, jsonify

app = Flask(__name__)
WEBHOOK_SECRET = b"your-hmac-secret"

@app.route("/webhooks/meshant", methods=["POST"])
def handle_webhook():
    # Verify HMAC signature
    signature = request.headers.get("X-Meshant-Signature")
    expected = hmac.new(WEBHOOK_SECRET, request.data, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return jsonify({"error": "invalid signature"}), 401

    event = request.json
    print(f"Received event: {event['type']} for {event['resource_id']}")

    # Process the event...
    return jsonify({"status": "ok"}), 200
```

For detailed webhook setup, see
[How-To: Handle Webhooks](how-to/handle-webhooks.md).


## What Next?

- [How-To: Authenticate and Authorize](how-to/authenticate-and-authorize.md)
  -- JWT tokens, scopes, service accounts
- [How-To: Handle Webhooks](how-to/handle-webhooks.md) -- signature
  verification, retry logic, event types
- [How-To: Integrate Semantic Layer](how-to/integrate-semantic-layer.md)
  -- JSON-LD, SPARQL queries
- [Reference](reference.md) -- all API endpoints, SDK classes, error codes
