/**
 * MVP-gated route wrapper.
 *
 * When VITE_MVP_MODE=true, redirects to /coming-soon for paths that are
 * gated in the MVP release. Without this guard, route children render even
 * if the sidebar entry is hidden — direct URL navigation would bypass the
 * gating that mvpNav.ts only enforces in the sidebar.
 *
 * Use for routes whose backend feature is also disabled in MVP_MODE
 * (e.g. scheduled-ingestions, scheduled-exports — Prefect-backed features
 * gated by Phase 211 work).
 */

import { Navigate, useLocation } from 'react-router-dom';
import { isMvpModeEnabledFromEnv, isPathHiddenInMvpMode } from '../../features/shell/utils/mvpNav';

interface MvpGatedRouteProps {
  children: React.ReactNode;
}

export function MvpGatedRoute({ children }: MvpGatedRouteProps) {
  const location = useLocation();
  const mvpEnabled = isMvpModeEnabledFromEnv();

  // Check both exact path and any hierarchical prefix in MVP_EXACT_PATHS
  // (e.g. /scheduled-ingestions/123 should also be gated when /scheduled-ingestions is)
  const pathname = location.pathname;
  const isGated =
    mvpEnabled &&
    (isPathHiddenInMvpMode(pathname, true) ||
      // Hierarchical match: any parent segment in MVP_EXACT_PATHS
      pathname.split('/').reduce<{ prefix: string; gated: boolean }>(
        (acc, seg) => {
          if (acc.gated) return acc;
          const next = acc.prefix === '' && seg === '' ? '' : `${acc.prefix}/${seg}`.replace(/^\/+/, '/');
          return { prefix: next, gated: isPathHiddenInMvpMode(next, true) };
        },
        { prefix: '', gated: false }
      ).gated);

  if (isGated) {
    return <Navigate to="/coming-soon" replace />;
  }

  return <>{children}</>;
}
