/**
 * TenantPill — persistent environment + tenant indicator (278.C.1).
 *
 * Renders in the header showing the active tenant name with color-coded
 * trim for the current environment. Click opens the tenant switcher.
 */
import { type FC } from 'react';
import { useAuthStore } from '../../auth/store/authStore';
import './TenantPill.css';

type EnvColor = 'red' | 'amber' | 'blue' | 'neutral';

function readViteEnv(): string {
  try {
    const env = (import.meta as unknown as Record<string, unknown>).env as Record<string, string> | undefined;
    return env?.VITE_ENVIRONMENT ?? '';
  } catch {
    return '';
  }
}

const VITE_ENV: string = readViteEnv();

function envColor(): EnvColor {
  const env = VITE_ENV.toLowerCase();
  if (env === 'production' || env === 'prod') return 'red';
  if (env === 'staging') return 'amber';
  if (env === 'sandbox' || env === 'sandbox') return 'blue';
  return 'neutral';
}

export const TenantPill: FC = () => {
  const user = useAuthStore((s) => s.user);
  const activeTenantId = useAuthStore((s) => s.active_tenant_id);
  const setActiveTenant = useAuthStore((s) => s.setActiveTenant);

  const effectiveTenantId = activeTenantId || user?.tenant_id;
  if (!effectiveTenantId || !user) return null;

  // Derive display name from the user's tenant list or the stored tenant_id
  const tenantName =
    user.tenant_name ?? (effectiveTenantId.split('-')[0] ?? effectiveTenantId).slice(0, 8);

  const color = envColor();

  const handleClick = () => {
    // Toggle: clear active tenant to return to home, or open switcher
    if (activeTenantId) {
      setActiveTenant(null);
    }
    // The existing tenant-switch dropdown handles further interaction.
    // Clicking the pill focuses the tenant-switch trigger button below.
  };

  return (
    <button
      type="button"
      className={`tenant-pill tenant-pill--${color}`}
      onClick={handleClick}
      aria-label={`Current tenant: ${tenantName}. Environment: ${VITE_ENV || 'development'}. Click to switch.`}
      title={`${tenantName} · ${VITE_ENV || 'development'}`}
      data-testid="tenant-pill"
    >
      <span className="tenant-pill__env-dot" aria-hidden="true" />
      <span className="tenant-pill__name">{tenantName}</span>
    </button>
  );
};
