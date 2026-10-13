/// <reference types="vite/client" />

import react from '@vitejs/plugin-react';
import { sentryVitePlugin } from '@sentry/vite-plugin';
import fs from 'fs';
import path from 'path';
import { defineConfig } from 'vite';
import { DEV_SECURITY_HEADERS_REV } from './src/lib/playwright-frontend-resolve';
import { E2E_STRIPE_PUBLISHABLE_KEY } from './src/lib/e2e-stripe-config';

// E2E-mode default for the Stripe publishable key. Playwright's webServer
// injects this for servers IT starts, but batch runs reuse the supervised
// dev server started by scripts/e2e-detect-api.sh (only VITE_E2E_TEST is
// in its env) — without this default that server embeds no key, the
// checkout page renders "Stripe is not configured", and the Stripe
// checkout E2E runtime-skips. Vite loads this config file BEFORE loadEnv
// merges process.env into import.meta.env, so the mutation below is
// picked up by every VITE_* replacement. An explicitly exported key
// always wins.
if (
  process.env.VITE_E2E_TEST === 'true' &&
  !process.env.VITE_STRIPE_PUBLISHABLE_KEY
) {
  process.env.VITE_STRIPE_PUBLISHABLE_KEY = E2E_STRIPE_PUBLISHABLE_KEY;
}

/**
 * Resolve proxy target for API/health/ws. Safe when VITE_API_BASE_URL is relative (e.g. /api/v1).
 * Priority: VITE_PROXY_TARGET > VITE_API_BASE_URL (if absolute URL) > http://localhost:8000
 */
function getProxyTarget(): string {
  if (process.env.VITE_PROXY_TARGET) {
    return process.env.VITE_PROXY_TARGET.replace(/\/$/, '');
  }
  const base = process.env.VITE_API_BASE_URL;
  if (base?.startsWith('http://') || base?.startsWith('https://')) {
    try {
      return new URL(base).origin;
    } catch {
      /* fall through */
    }
  }
  return 'http://localhost:8000';
}

/**
 * Vite plugin: inject the same security headers that nginx.conf adds in production.
 * This lets E2E CSP-enforce tests pass against the Vite dev server (not just Nginx).
 * Headers match frontend/nginx.test.conf exactly.
 */
function securityHeadersPlugin(): import('vite').Plugin {
  return {
    name: 'security-headers',
    configureServer(server) {
      // Direct-mode support: when VITE_API_BASE_URL is absolute (e.g.
      // .env.local's http://localhost:8001/api/v1), the browser fetches the
      // API cross-origin, bypassing the proxy. The static nginx-parity CSP
      // below would block every apiClient fetch (connect-src 'self' only)
      // — a CSP-blocked fetch rejects as TypeError "Failed to fetch",
      // indistinguishable from a network outage. Append the API origin to
      // connect-src in direct mode only; proxy mode (relative base, the E2E
      // batch path) keeps the header byte-identical to nginx.test.conf and
      // the csp-enforce parity specs stay green.
      // process.env (NOT import.meta.env): the config is bundled into a
      // temp .mjs where import.meta.env is undefined and reading it
      // crashes every FRESH vite start with "Cannot read properties of
      // undefined (reading 'VITE_API_BASE_URL')" (b7 verification run) —
      // long-running servers that loaded the config before the bundler
      // behaviour changed masked it. getProxyTarget() above already uses
      // process.env; the wrapper exports VITE_API_BASE_URL into the vite
      // process env, so the direct/proxy-mode decision is unchanged.
      const apiBase = process.env.VITE_API_BASE_URL as string | undefined;
      let apiOrigin = '';
      if (apiBase && /^https?:\/\//.test(apiBase)) {
        try {
          apiOrigin = new URL(apiBase).origin;
        } catch {
          /* keep the static header */
        }
      }
      const connectSrcExtra = apiOrigin ? ` ${apiOrigin}` : '';
      server.middlewares.use((_req, res, next) => {
        // Match nginx.test.conf CSP exactly so E2E csp-enforce tests pass.
        // script-src needs 'unsafe-inline' for Vite's HMR client injection in dev mode.
        // connect-src needs ws: for Vite HMR WebSocket, localhost:9010 for MinIO presigned uploads.
        // style-src needs fonts.googleapis.com for Google Fonts loaded in index.html.
        // font-src needs fonts.gstatic.com for the actual font file downloads.
        res.setHeader('Content-Security-Policy',
          // script-src/frame-src include js.stripe.com (mirrors
          // nginx.test.conf) — without it the Stripe.js loader is CSP-blocked
          // and the checkout page hangs on its skeleton forever (the Stripe
          // E2E timed out on an h1 that can never render).
          `default-src 'self'; script-src 'self' 'unsafe-inline' https://js.stripe.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data: blob:; connect-src 'self' ws: http://localhost:9010 https://api.stripe.com${connectSrcExtra}; frame-src 'self' https://js.stripe.com https://hooks.stripe.com; report-uri /api/csp-report/`);
        res.setHeader('X-Frame-Options', 'DENY');
        res.setHeader('X-Content-Type-Options', 'nosniff');
        res.setHeader('Strict-Transport-Security', 'max-age=31536000; includeSubDomains; preload');
        // nginx.test.conf:54-57 — keep the dev-server header set at parity with
        // the reverse proxy so the E2E security-header specs (csp-enforce,
        // security-headers) assert the same baseline against both servers.
        res.setHeader('Referrer-Policy', 'strict-origin-when-cross-origin');
        res.setHeader('Permissions-Policy', 'geolocation=(), camera=(), microphone=()');
        // Staleness fingerprint for global-setup's reused-server guard —
        // BUMP DEV_SECURITY_HEADERS_REV whenever this header set changes.
        res.setHeader('X-Vite-Security-Headers-Rev', DEV_SECURITY_HEADERS_REV);
        next();
      });
    },
  };
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    securityHeadersPlugin(),
    ...(process.env.GENERATE_SOURCEMAPS === 'true' && process.env.SENTRY_AUTH_TOKEN
      ? [sentryVitePlugin({
          org: process.env.SENTRY_ORG,
          project: process.env.SENTRY_PROJECT,
          authToken: process.env.SENTRY_AUTH_TOKEN,
        })]
      : []),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      // Resolves to ./shared/ in Docker (CI copies shared/ into frontend/)
      // or ../shared/ in local dev (repo root shared/).
      '@shared': fs.existsSync(path.resolve(__dirname, 'shared'))
        ? path.resolve(__dirname, 'shared')
        : path.resolve(__dirname, '../shared'),
    },
  },
  // Phase 278 / b7 #14 — @codemirror/view is imported directly by
  // SemanticPage (EditorView.contentAttributes for the a11y label +
  // E2E testid). When the long-lived dev server discovers the new
  // import mid-flight, Vite pre-bundles a SECOND copy of view/state,
  // and CodeMirror's ExtensionSet instanceof checks throw
  // "Unrecognized extension value ... multiple instances of
  // @codemirror/state are loaded" at runtime (the whole semantic
  // page crashed with the ErrorDisplay). Pinning view+state in the
  // optimizeDeps pre-bundle keeps exactly one browser instance.
  optimizeDeps: {
    include: ['@codemirror/view', '@codemirror/state'],
  },
  server: {
    port: 5173, // Vite default port (3000 is used by Grafana)
    // E2E (VITE_E2E_TEST): disable HMR so the dev server does not compete for CPU/WebSocket
    // with parallel Playwright workers; domcontentloaded was stalling under load.
    hmr: process.env.VITE_E2E_TEST === 'true' ? false : undefined,
    // Playwright HTML reports and artifacts live under the repo root; watching them triggers
    // full HMR reloads during parallel E2E and starves /login navigation (see e2e-results logs).
    watch: {
      ignored: ['**/playwright-report/**', '**/test-results/**'],
    },
    proxy: {
      '/health': {
        target: getProxyTarget(),
        changeOrigin: true,
        rewrite: (path) => (path === '/health' ? '/health/' : path),
        // Same no-pooling rationale as the /api proxy below.
        agent: false,
      },
      '/api': {
        target: getProxyTarget(),
        changeOrigin: true,
        // No keep-alive pooling for the API proxy: after a backend container
        // restart (batch startup, mid-run `docker restart`, gunicorn HUP) the
        // pooled sockets point at the dead container and the first requests
        // on them die with ECONNRESET → browser "Failed to fetch" /
        // NETWORK_ERROR on the API-fetch layer (b7: assets + compliance
        // nil-UUID probes NETWORK_ERROR'd while the API was healthy — the
        // requests never reached Django). A fresh agent per request removes
        // the stale-pool failure mode entirely; the cost on localhost is
        // negligible. `agent: false` is the documented http-proxy switch.
        agent: false,
        // 30s proxy timeout: long enough for normal API calls (including file uploads via
        // presigned URLs which bypass the proxy), short enough to release Vite's event loop
        // when the backend is slow under parallel E2E load. Previously 60s — stalled proxy
        // connections blocked Vite from serving index.html, causing navigation timeouts.
        timeout: 30000,
        proxyTimeout: 30000,
        // Override the browser's Accept header with application/json.  The browser sends
        // Accept: text/html,application/xhtml+xml,application/xml;q=0.9,... which DRF's
        // content negotiation rejects with HTTP 406 Not Acceptable when no XML renderer
        // is configured.  Normalizing to application/json prevents silent console errors.
        configure: (proxy) => {
          proxy.on('proxyReq', (proxyReq) => {
            if (proxyReq.getHeader('Accept') !== 'application/json') {
              proxyReq.setHeader('Accept', 'application/json');
            }
          });
        },
      },
      '/api-docs': {
        target: getProxyTarget(),
        changeOrigin: true,
      },
      // Phase 31 — Semantic API calls go through /api/v1/semantic/... which is handled
      // by the '/api' proxy above. Do NOT proxy bare '/semantic' — it collides with the
      // SPA route /semantic (SemanticPage) and causes Vite to forward the browser
      // navigation to the Django backend instead of serving the React app.
      '/ws': {
        target: getProxyTarget().replace(/^http/, 'ws'),
        ws: true,
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    // Vite's default assetsDir is "assets", which collides with the SPA route
    // /assets and the directory dist/assets/. nginx serving dist/ will then
    // 301 /assets → /assets/ (directory) → 403 (autoindex off, no index.html),
    // breaking SPA navigation to /assets. Renaming to "static" eliminates the
    // collision; SPA routes own /assets, hashed bundles live under /static.
    assetsDir: 'static',
    // Source maps expose original source to the browser — never ship them in production.
    // Set GENERATE_SOURCEMAPS=true only for staging/debug builds or when uploading to
    // a source map service (e.g. Sentry) that strips them before CDN delivery.
    sourcemap: process.env.GENERATE_SOURCEMAPS === 'true',
  },
});
