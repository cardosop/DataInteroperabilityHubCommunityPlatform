# Interoperable Data Hub JavaScript SDK

TypeScript/JavaScript client library for the Interoperable Data Hub API.

## Installation

```bash
npm install @datahub/interoperability-sdk
```

## Quick Start

```typescript
import { DataHubClient } from '@datahub/interoperability-sdk';

// Initialize client with API key
const client = new DataHubClient({
  baseUrl: 'https://api.hub.example.com/api/v1',
  apiToken: process.env.DATAHUB_API_TOKEN,
});

// Use the client
const assets = await client.assets.list();
console.log(assets);
```

## Authentication

### API Key

```typescript
const client = new DataHubClient({
  baseUrl: 'https://api.hub.example.com/api/v1',
  apiToken: 'your-api-key',
});
```

### JWT Token with Auto-Refresh

```typescript
const client = new DataHubClient({
  baseUrl: 'https://api.hub.example.com/api/v1',
  apiToken: initialToken,
});

// Set token refresh callback
client.setTokenRefreshCallback(async () => {
  // Refresh token logic
  const response = await fetch('/api/auth/refresh', {
    method: 'POST',
    body: JSON.stringify({ refreshToken }),
  });
  const data = await response.json();
  return data.access_token;
});
```

## Error Handling

```typescript
import {
  DataHubError,
  ValidationError,
  NotFoundError,
  UnauthorizedError,
} from '@datahub/interoperability-sdk';

try {
  const asset = await client.assets.get('asset-id');
} catch (error) {
  if (error instanceof NotFoundError) {
    console.log('Asset not found:', error.message);
    console.log('Request ID:', error.requestId);
  } else if (error instanceof ValidationError) {
    console.log('Validation errors:', error.details);
  } else {
    console.error('Unexpected error:', error);
  }
}
```

## Retry Logic

The SDK automatically retries transient errors (5xx, network timeouts) with exponential backoff:

```typescript
const client = new DataHubClient({
  baseUrl: 'https://api.hub.example.com/api/v1',
  apiToken: 'your-api-key',
  maxRetries: 3, // Default: 3
  timeout: 30000, // Default: 30000ms
});
```

## Examples

### Create Asset

```typescript
const asset = await client.assets.create({
  key: 'my-asset',
  name: 'My Asset',
  description: 'Asset description',
  domain: 'marketing',
});
```

### List Assets with Filters

```typescript
const assets = await client.assets.list({
  status: 'ACTIVE',
  domain: 'marketing',
  search: 'customer',
  limit: 20,
  offset: 0,
});
```

### Upload File

```typescript
const file = await client.files.initUpload({
  name: 'data.csv',
  size: 1024,
  content_type: 'text/csv',
});

// Upload to pre-signed URL
await fetch(file.upload_url, {
  method: 'PUT',
  body: fileData,
});

// Complete upload
await client.files.completeUpload(file.id);
```

## Configuration

### Environment Variables

```bash
export DATAHUB_BASE_URL=https://api.hub.example.com/api/v1
export DATAHUB_API_TOKEN=your-api-key
```

```typescript
const client = new DataHubClient({
  baseUrl: process.env.DATAHUB_BASE_URL!,
  apiToken: process.env.DATAHUB_API_TOKEN,
});
```

## TypeScript Support

The SDK is written in TypeScript and provides full type definitions:

```typescript
import { Asset, AssetCreateRequest } from '@datahub/interoperability-sdk';

const request: AssetCreateRequest = {
  key: 'my-asset',
  name: 'My Asset',
};

const asset: Asset = await client.assets.create(request);
```

## License

MIT

