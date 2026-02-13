/**
 * Global Setup for E2E Tests
 * Runs before all tests to ensure backend is available
 */

import { FullConfig } from '@playwright/test';

const API_BASE_URL = process.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

async function globalSetup(config: FullConfig) {
  // Check if backend API is available
  const maxRetries = 15; // Increased from 10 to 15 for CI environments
  const retryDelay = 2000; // 2 seconds

  console.log(`Checking backend API availability at ${API_BASE_URL}...`);

  for (let i = 0; i < maxRetries; i++) {
    try {
      // Check health endpoint first (lighter than login)
      const healthResponse = await fetch(`${API_BASE_URL.replace('/api/v1', '')}/health/`, {
        method: 'GET',
      });

      if (healthResponse.status !== undefined) {
        console.log('✅ Backend API health endpoint is available');

        // Also verify API endpoint responds
        const apiResponse = await fetch(`${API_BASE_URL}/auth/login/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email: 'test', password: 'test' }),
        });

        // Any response (even 400/401) means API is available
        if (apiResponse.status !== undefined) {
          console.log('✅ Backend API is available and responding');
          return;
        }
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      console.log(
        `⏳ Waiting for backend API... (attempt ${i + 1}/${maxRetries}) - ${errorMessage}`
      );
      if (i < maxRetries - 1) {
        await new Promise((resolve) => setTimeout(resolve, retryDelay));
      }
    }
  }

  console.error('❌ Backend API is not available after maximum retries.');
  console.error('   Make sure docker-compose is running: docker compose up -d');
  console.error('   Or verify API service is accessible at:', API_BASE_URL);

  // In CI, fail fast if API is not available
  if (process.env.CI) {
    throw new Error('Backend API is not available. E2E tests require a running API service.');
  }

  // In local development, warn but continue (allows manual intervention)
  console.warn('⚠️  Continuing anyway (local dev mode). Tests may fail.');
}

export default globalSetup;
