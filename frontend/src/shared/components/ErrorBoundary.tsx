/**
 * Error Boundary Component
 * Catches React errors and reports them
 */

import { Component, type ReactNode } from 'react';
import { errorReportingService } from '../services/errorReporting';
import { ErrorDisplay } from './ErrorDisplay';

// sessionStorage key used to break a reload loop. We store the *timestamp*
// of the last reload attempt and refuse to reload again if it's within
// CHUNK_RELOAD_COOLDOWN_MS. We deliberately do NOT clear the flag on a
// successful mount: the boundary mounts before its children render, so any
// `componentDidMount`-based clear would fire before the child can throw,
// producing an infinite reload loop on a persistently-broken chunk URL.
// Time-based expiry is the only correct guard.
const CHUNK_RELOAD_FLAG = '__meshant_chunk_reload_at__';
const CHUNK_RELOAD_COOLDOWN_MS = 30_000;

/**
 * Detect Vite/webpack dynamic-import chunk-loading failures.
 *
 * After a deploy, browsers (and Playwright contexts that survive a redeploy
 * via reused storageState) hold references to hashed chunk filenames that no
 * longer exist on the CDN — `import('./Foo')` then rejects with one of the
 * messages below. The user's React tree never mounted, so the React error
 * boundary catches it and the whole page goes "Something went wrong".
 *
 * The correct recovery is a single hard reload: that drops the stale module
 * graph and the SPA picks up the new manifest. We guard against reload loops
 * with a sessionStorage timestamp — if a reload was attempted within the
 * cooldown window and we still hit the same error, it's a real bug (not a
 * stale-chunk race), so we surface the error instead of looping.
 */
function isChunkLoadError(error: Error | null | undefined): boolean {
  if (!error) return false;
  const message = `${error.name ?? ''} ${error.message ?? ''}`;
  return (
    /ChunkLoadError/i.test(message) ||
    /Loading chunk \d+ failed/i.test(message) ||
    /Failed to fetch dynamically imported module/i.test(message) ||
    /Unable to preload CSS/i.test(message) ||
    /error loading dynamically imported module/i.test(message) ||
    /Importing a module script failed/i.test(message)
  );
}

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  errorInfo: { componentStack?: string } | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
    };
  }

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    return {
      hasError: true,
      error,
    };
  }

  componentDidCatch(error: Error, errorInfo: { componentStack?: string }): void {
    // Stale-chunk recovery: if this is a Vite chunk-load failure and we have
    // not already attempted a reload in this session, hard-reload once. The
    // reload re-fetches index.html and pulls fresh hashed chunk filenames,
    // resolving the mismatch without any user intervention.
    if (isChunkLoadError(error) && typeof window !== 'undefined') {
      try {
        const lastAttempt = Number(window.sessionStorage.getItem(CHUNK_RELOAD_FLAG)) || 0;
        const sinceLastAttempt = Date.now() - lastAttempt;
        if (sinceLastAttempt > CHUNK_RELOAD_COOLDOWN_MS) {
          window.sessionStorage.setItem(CHUNK_RELOAD_FLAG, String(Date.now()));
          // Report before reload so observability still captures the event
          // (errorCode is the closest existing field for tagging the recovery
          // path — keeps the report payload schema-compatible).
          errorReportingService.reportError(error, {
            componentStack: errorInfo.componentStack,
            errorCode: 'CHUNK_LOAD_RELOAD',
          });
          window.location.reload();
          return;
        }
        // Recent reload already attempted — fall through to surface the
        // error to the user instead of looping. The 30 s cooldown self-
        // expires so the next deploy in the same session can recover.
      } catch {
        // sessionStorage may be unavailable (private mode, SSR) — fall through
        // and surface the error normally.
      }
    }

    // Report error
    errorReportingService.reportError(error, {
      componentStack: errorInfo.componentStack,
    });

    this.setState({
      errorInfo,
    });
  }

  render(): ReactNode {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <ErrorDisplay
          error={this.state.error || new Error('An unexpected error occurred')}
          title="Something went wrong"
        />
      );
    }

    return this.props.children;
  }
}
