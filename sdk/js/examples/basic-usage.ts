/**
 * Basic SDK Usage Examples
 */

import { DataHubClient } from '../src/client';
import { ValidationError, NotFoundError } from '../src/errors';

// Initialize client
const client = new DataHubClient({
  baseUrl: process.env.DATAHUB_BASE_URL || 'https://api.hub.example.com/api/v1',
  apiToken: process.env.DATAHUB_API_TOKEN,
  enableLogging: true,
});

// Example 1: List assets
async function listAssets() {
  try {
    const assets = await client.get('/assets/', {
      params: {
        status: 'ACTIVE',
        limit: 20,
        offset: 0,
      },
    });
    console.log('Assets:', assets);
  } catch (error) {
    if (error instanceof NotFoundError) {
      console.error('Assets not found');
    } else {
      console.error('Error:', error);
    }
  }
}

// Example 2: Create asset
async function createAsset() {
  try {
    const asset = await client.post('/assets/', {
      key: 'my-asset',
      name: 'My Asset',
      description: 'Asset description',
      domain: 'marketing',
    });
    console.log('Created asset:', asset);
  } catch (error) {
    if (error instanceof ValidationError) {
      console.error('Validation errors:', error.details);
    } else {
      console.error('Error:', error);
    }
  }
}

// Example 3: Get asset by ID
async function getAsset(assetId: string) {
  try {
    const asset = await client.get(`/assets/${assetId}/`);
    console.log('Asset:', asset);
  } catch (error) {
    if (error instanceof NotFoundError) {
      console.error(`Asset ${assetId} not found`);
    } else {
      console.error('Error:', error);
    }
  }
}

// Example 4: Update asset
async function updateAsset(assetId: string) {
  try {
    const asset = await client.patch(`/assets/${assetId}/`, {
      description: 'Updated description',
    });
    console.log('Updated asset:', asset);
  } catch (error) {
    console.error('Error:', error);
  }
}

// Example 5: Delete asset
async function deleteAsset(assetId: string) {
  try {
    await client.delete(`/assets/${assetId}/`);
    console.log('Asset deleted');
  } catch (error) {
    console.error('Error:', error);
  }
}

// Run examples
async function main() {
  await listAssets();
  await createAsset();
  // await getAsset('asset-id');
  // await updateAsset('asset-id');
  // await deleteAsset('asset-id');
}

if (require.main === module) {
  main().catch(console.error);
}

