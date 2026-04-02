import { describe, expect, it } from 'vitest';
import { resolvePlaywrightFrontend } from './playwright-frontend-resolve';

describe('resolvePlaywrightFrontend', () => {
  it('prefers E2E_WEB_PORT over FRONTEND_URL so Vite and baseURL match', () => {
    const r = resolvePlaywrightFrontend({
      E2E_WEB_PORT: '5184',
      FRONTEND_URL: 'http://localhost:3010/',
    } as NodeJS.ProcessEnv);
    expect(r.baseURL).toBe('http://localhost:5184');
    expect(r.webPort).toBe('5184');
    expect(r.webServerCheckUrl).toBe('http://localhost:5184/');
  });

  it('uses FRONTEND_URL origin when E2E_WEB_PORT unset', () => {
    const r = resolvePlaywrightFrontend({
      FRONTEND_URL: 'http://localhost:3010',
    } as NodeJS.ProcessEnv);
    expect(r.baseURL).toBe('http://localhost:3010');
    expect(r.webPort).toBe('3010');
  });

  it('defaults to 5173 for bare http://localhost', () => {
    const r = resolvePlaywrightFrontend({
      FRONTEND_URL: 'http://localhost',
    } as NodeJS.ProcessEnv);
    expect(r.baseURL).toBe('http://localhost:5173');
    expect(r.webPort).toBe('5173');
  });

  it('defaults when no env', () => {
    const r = resolvePlaywrightFrontend({} as NodeJS.ProcessEnv);
    expect(r.baseURL).toBe('http://localhost:5173');
    expect(r.webPort).toBe('5173');
  });

  it('uses PLAYWRIGHT_BASE_URL when FRONTEND_URL unset', () => {
    const r = resolvePlaywrightFrontend({
      PLAYWRIGHT_BASE_URL: 'http://127.0.0.1:4000/',
    } as NodeJS.ProcessEnv);
    expect(r.baseURL).toBe('http://127.0.0.1:4000');
    expect(r.webPort).toBe('4000');
  });
});
