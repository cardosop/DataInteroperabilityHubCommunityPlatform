import react from '@vitejs/plugin-react';
import path from 'path';
import { defineConfig } from 'vite';

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
      '/api': {
        // VITE_PROXY_TARGET: proxy origin (avoids CORS). VITE_API_BASE_URL: fallback for full URL.
        target: process.env.VITE_PROXY_TARGET
          ? process.env.VITE_PROXY_TARGET
          : process.env.VITE_API_BASE_URL
            ? new URL(process.env.VITE_API_BASE_URL).origin
            : 'http://localhost:8000',
        changeOrigin: true,
      },
      '/health': {
        target: process.env.VITE_PROXY_TARGET
          ? process.env.VITE_PROXY_TARGET
          : process.env.VITE_API_BASE_URL
            ? new URL(process.env.VITE_API_BASE_URL).origin
            : 'http://localhost:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: process.env.VITE_PROXY_TARGET
          ? process.env.VITE_PROXY_TARGET.replace(/^http/, 'ws')
          : process.env.VITE_API_BASE_URL
            ? new URL(process.env.VITE_API_BASE_URL).origin.replace(/^http/, 'ws')
            : 'ws://localhost:8000',
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
