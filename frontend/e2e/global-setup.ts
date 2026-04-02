/**
 * Global Setup for E2E Tests
 * Runs before all tests to ensure backend is available
 */

import * as fs from 'fs';
import * as path from 'path';
import { FullConfig } from '@playwright/test';

function getDefaultApiBase(): string {
  return (
    process.env.E2E_API_BASE_URL ||
    (process.env.VITE_PROXY_TARGET ? `${process.env.VITE_PROXY_TARGET.replace(/\/$/, '')}/api/v1` : null) ||
    (process.env.VITE_API_BASE_URL?.startsWith('http') ? process.env.VITE_API_BASE_URL : null) ||
    'http://localhost:8000/api/v1'
  );
}

/** Alternate port 8000 <-> 8001 for localhost */
function getAlternateApiBase(currentBase: string): string | null {
  try {
    const url = new URL(currentBase);
    if (url.hostname === 'localhost' || url.hostname === '127.0.0.1') {
      const port = parseInt(url.port || '80', 10);
      const altPort = port === 8001 ? 8000 : port === 8000 ? 8001 : null;
      if (altPort) {
        url.port = String(altPort);
        return url.toString();
      }
    }
  } catch {
    // ignore
  }
  return null;
}

async function checkApiReachable(baseUrl: string): Promise<boolean> {
  try {
    const healthUrl = baseUrl.replace(/\/api\/v1\/?$/, '') + '/health/';
    const r = await fetch(healthUrl, { method: 'GET' });
    return r.status !== undefined;
  } catch {
    return false;
  }
}

async function globalSetup(config: FullConfig) {
  // Ensure test-results exists to reduce ENOENT artifact race (Playwright trace/video writes)
  const outputDir = config.outputDir ?? path.join(process.cwd(), 'test-results');
  fs.mkdirSync(outputDir, { recursive: true });

  let API_BASE_URL = getDefaultApiBase();
  const maxRetries = 15;
  const retryDelay = 2000;

  // If default (8000) unreachable, try alternate port (8001) — common with docker-compose.test.yml
  if (!process.env.E2E_API_BASE_URL && !(await checkApiReachable(API_BASE_URL))) {
    const alt = getAlternateApiBase(API_BASE_URL);
    if (alt && (await checkApiReachable(alt))) {
      API_BASE_URL = alt;
      process.env.E2E_API_BASE_URL = API_BASE_URL;
      console.log(`Using alternate API port: ${API_BASE_URL}`);
    }
  }

  // Write proxy target for webServer (config loads before globalSetup; webServer needs correct port)
  try {
    const origin = new URL(API_BASE_URL).origin;
    const envPath = path.join(process.cwd(), '.env.e2e');
    fs.writeFileSync(
      envPath,
      `export VITE_PROXY_TARGET=${origin}\nexport E2E_API_BASE_URL=${API_BASE_URL}\n`,
      'utf8'
    );
  } catch {
    // ignore
  }

  console.log(`Checking backend API availability at ${API_BASE_URL}...`);

  for (let i = 0; i < maxRetries; i++) {
    try {
      const healthResponse = await fetch(`${API_BASE_URL.replace(/\/api\/v1\/?$/, '')}/health/`, {
        method: 'GET',
      });

      if (healthResponse.status !== undefined) {
        console.log('✅ Backend API health endpoint is available');

        const apiResponse = await fetch(`${API_BASE_URL}/auth/login/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email: 'test', password: 'test' }),
        });

        if (apiResponse.status !== undefined) {
          console.log('✅ Backend API is available and responding');
          process.env.E2E_API_BASE_URL = API_BASE_URL;
          // Ensure E2E persona users (AUDITOR, TENANT_ADMIN, etc.) exist for role-gated journey tests
          try {
            const { execSync } = await import('child_process');
            const port = new URL(API_BASE_URL).port || '8000';
            const container = port === '8001' ? 'hub-test-api' : 'hub-api';
            // Seed default plans first (required for registration; ensure_e2e_user_roles may create users)
            execSync(`docker exec ${container} python hub/manage.py seed_default_plans`, {
              stdio: 'pipe',
              encoding: 'utf8',
            });
            execSync(`docker exec ${container} python hub/manage.py ensure_e2e_user_roles`, {
              stdio: 'pipe',
              encoding: 'utf8',
            });
            console.log('✅ E2E persona users ensured (ensure_e2e_user_roles)');
            try {
              execSync(`docker exec ${container} python hub/manage.py ensure_e2e_subscription`, {
                stdio: 'pipe',
                encoding: 'utf8',
              });
              console.log('✅ E2E subscription ensured (ensure_e2e_subscription)');
              try {
                const authDir = path.join(process.cwd(), 'e2e', '.auth');
                fs.mkdirSync(authDir, { recursive: true });
                fs.writeFileSync(
                  path.join(authDir, 'subscription-primed.json'),
                  JSON.stringify({ apiBaseUrl: API_BASE_URL }),
                  'utf8'
                );
              } catch {
                // Marker is optional; workers fall back to HTTP ensure
              }
            } catch {
              // Ignore - command may not exist or subscription setup may fail
            }
          } catch {
            // Ignore if docker/command unavailable (e.g. CI uses different container name)
          }
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
  console.error('');
  console.error('E2E tests require a running backend. From repo root, run one of:');
  console.error('  • docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d');
  console.error('  • docker compose up -d');
  console.error('  • docker compose -f docker-compose.test.yml up -d  (API on 8001; set E2E_API_BASE_URL=http://localhost:8001/api/v1)');
  console.error('');
  console.error('Wait for api-service to be healthy, then run: npm run test:e2e');
  console.error('Or use: npm run test:e2e:full  (starts backend automatically)');
  console.error('');

  throw new Error(
    'Backend API is not available. E2E tests require a running API service. See instructions above.'
  );
}

export default globalSetup;
