import react from '@vitejs/plugin-react';
import { sentryVitePlugin } from '@sentry/vite-plugin';
import path from 'path';
import { defineConfig } from 'vite';

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
      server.middlewares.use((_req, res, next) => {
        // Match nginx.test.conf CSP exactly so E2E csp-enforce tests pass.
        // script-src needs 'unsafe-inline' for Vite's HMR client injection in dev mode.
        // connect-src needs ws: for Vite HMR WebSocket, localhost:9010 for MinIO presigned uploads.
        // style-src needs fonts.googleapis.com for Google Fonts loaded in index.html.
        // font-src needs fonts.gstatic.com for the actual font file downloads.
        res.setHeader('Content-Security-Policy',
          "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data: blob:; connect-src 'self' ws: http://localhost:9010; report-uri /api/csp-report/");
        res.setHeader('X-Frame-Options', 'DENY');
        res.setHeader('X-Content-Type-Options', 'nosniff');
        res.setHeader('Strict-Transport-Security', 'max-age=31536000; includeSubDomains; preload');
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
    },
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
      },
      '/api': {
        target: getProxyTarget(),
        changeOrigin: true,
        // 30s proxy timeout: long enough for normal API calls (including file uploads via
        // presigned URLs which bypass the proxy), short enough to release Vite's event loop
        // when the backend is slow under parallel E2E load. Previously 60s — stalled proxy
        // connections blocked Vite from serving index.html, causing navigation timeouts.
        timeout: 30000,
        proxyTimeout: 30000,
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
