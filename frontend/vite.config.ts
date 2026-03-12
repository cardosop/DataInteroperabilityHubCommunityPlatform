import react from '@vitejs/plugin-react';
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

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173, // Vite default port (3000 is used by Grafana)
    proxy: {
      '/health': {
        target: getProxyTarget(),
        changeOrigin: true,
        rewrite: (path) => (path === '/health' ? '/health/' : path),
      },
      '/api': {
        target: getProxyTarget(),
        changeOrigin: true,
        // Increase timeouts for file uploads and long-running API calls (avoids ECONNRESET under load)
        timeout: 60000,
        proxyTimeout: 60000,
      },
      '/api-docs': {
        target: getProxyTarget(),
        changeOrigin: true,
      },
      '/ws': {
        target: getProxyTarget().replace(/^http/, 'ws'),
        ws: true,
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
});
