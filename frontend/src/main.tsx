import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import * as Sentry from '@sentry/react';
import App from './App.tsx';
import './index.css';
import './shared/styles/a11y.css';
import '@xyflow/react/dist/style.css';

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
