import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import * as Sentry from '@sentry/react';
import App from './App.tsx';
import './index.css';
import './shared/styles/a11y.css';
import '@xyflow/react/dist/style.css';

// Vite stale-chunk recovery (primary path).
//
// After a deploy the hashed chunk filenames in the previous index.html are
// gone from the CDN. Browsers (and Playwright contexts that survive a redeploy
// via reused storageState) still hold the old manifest, so the next dynamic
// `import('./Foo')` rejects. Vite emits `vite:preloadError` when this happens
// — catching it here lets us hard-reload BEFORE React renders an error UI,
// which is faster, simpler, and less jarring than letting the React error
// boundary catch the rejection. The ErrorBoundary still has its own
// chunk-error recovery as a safety net for browsers/code paths the Vite event
// doesn't cover (e.g. CSS preload failures in some build modes).
//
// Loop guard: time-based via sessionStorage. Cooldown matches the boundary's
// CHUNK_RELOAD_COOLDOWN_MS so a persistently-broken deploy surfaces a real
// error to the user instead of looping. We deliberately do NOT preventDefault
// the event when we don't reload — letting it bubble preserves the standard
// rejection so React/Sentry still see the error and the user gets feedback.
const VITE_RELOAD_FLAG = '__meshant_chunk_reload_at__';
const VITE_RELOAD_COOLDOWN_MS = 30_000;
window.addEventListener('vite:preloadError', (event) => {
  try {
    const last = Number(window.sessionStorage.getItem(VITE_RELOAD_FLAG)) || 0;
    if (Date.now() - last > VITE_RELOAD_COOLDOWN_MS) {
      window.sessionStorage.setItem(VITE_RELOAD_FLAG, String(Date.now()));
      // Prevent the default unhandled rejection so the user doesn't see a
      // flash of the React error boundary before the reload starts.
      event.preventDefault();
      window.location.reload();
    }
  } catch {
    // sessionStorage unavailable (private mode) — let the error propagate.
  }
});

// Phase 56 (B3): Initialize Sentry (listener moved to App component useEffect for cleanup)
const VITE_SENTRY_DSN = import.meta.env.VITE_SENTRY_DSN as string | undefined;
if (VITE_SENTRY_DSN) {
  Sentry.init({
    dsn: VITE_SENTRY_DSN,
    integrations: [Sentry.browserTracingIntegration()],
  });
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>
);
