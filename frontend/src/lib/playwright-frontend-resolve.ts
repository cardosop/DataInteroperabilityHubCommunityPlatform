/**
 * Resolves Playwright baseURL and the Vite webServer port as a single unit.
 *
 * Root issue: .env / CI often sets FRONTEND_URL=http://localhost:3010 (docker nginx
 * from docker-compose.test.yml) while e2e-detect-api.sh sets E2E_WEB_PORT=5184 to
 * run a local Vite for the 8001 test API. If baseURL still prefers FRONTEND_URL,
 * setup-auth probes 3010 while webServer starts on 5184 → ECONNREFUSED.
 *
 * Priority: E2E_WEB_PORT wins when set (explicit E2E runner contract), then
 * FRONTEND_URL / PLAYWRIGHT_BASE_URL, then Vite default 5173.
 */

export type PlaywrightFrontendResolution = {
  /** Origin only; no trailing slash (Playwright baseURL convention). */
  baseURL: string;
  /** Port string for `vite --port`. */
  webPort: string;
  /** URL Playwright webServer waits on (GET must succeed when the app is up). */
  webServerCheckUrl: string;
};

export function resolvePlaywrightFrontend(env: NodeJS.ProcessEnv = process.env): PlaywrightFrontendResolution {
  const e2ePort = env.E2E_WEB_PORT?.trim();
  if (e2ePort) {
    const origin = `http://localhost:${e2ePort}`;
    return {
      baseURL: origin,
      webPort: e2ePort,
      webServerCheckUrl: `${origin}/`,
    };
  }

  const explicit = (env.FRONTEND_URL || env.PLAYWRIGHT_BASE_URL || '').trim();
  if (explicit) {
    const candidate = explicit.replace(/\/$/, '');
    try {
      const u = new URL(candidate);
      let port = u.port;
      if (!port) {
        if (u.protocol === 'https:') {
          port = '443';
        } else if (u.hostname === 'localhost' || u.hostname === '127.0.0.1') {
          // http://localhost with no port → local Vite default
          port = '5173';
        } else {
          port = '80';
        }
      }
      const origin = `${u.protocol}//${u.hostname}:${port}`;
      return {
        baseURL: origin,
        webPort: port,
        webServerCheckUrl: `${origin}/`,
      };
    } catch {
      return {
        baseURL: candidate,
        webPort: '5173',
        webServerCheckUrl: 'http://localhost:5173/',
      };
    }
  }

  return {
    baseURL: 'http://localhost:5173',
    webPort: '5173',
    webServerCheckUrl: 'http://localhost:5173/',
  };
}
