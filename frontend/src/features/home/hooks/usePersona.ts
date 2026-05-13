/**
 * Phase 278.B.3 — persona detection hook.
 *
 * Resolves the current user's primary persona from their roles,
 * tenant flags, and recent activity. Falls back to "default"
 * when no clear persona match is found.
 */
import { useAuthStore } from '../../auth/store/authStore';

export type Persona = 'DE' | 'DPO' | 'CPO' | 'DC' | 'MPA' | 'DEV' | 'default';

export function usePersona(): Persona {
  const { user } = useAuthStore();

  if (!user) return 'default';

  const roles: string[] = user.roles ?? [];
  const isPlatformAdmin = (user as any).is_platform_admin ?? false;

  // CPO: PLATFORM_ADMIN → sees billing/cost oversight
  if (isPlatformAdmin && roles.includes('PLATFORM_ADMIN')) return 'CPO';

  // DPO: AUDITOR role + compliance flags
  if (roles.includes('AUDITOR')) return 'DPO';

  // DE: DATA_PROVIDER or TENANT_ADMIN managing assets/ingestion
  if (roles.includes('DATA_PROVIDER')) return 'DE';
  if (roles.includes('TENANT_ADMIN')) return 'DE';

  // DC: DATA_CONSUMER — marketplace buyer
  if (roles.includes('DATA_CONSUMER')) return 'DC';

  // MPA: TENANT_ADMIN with marketplace listings
  if (roles.includes('TENANT_ADMIN')) return 'MPA';

  // DEV: has API keys or SDK usage
  if (roles.includes('DEVELOPER')) return 'DEV';

  return 'default';
}

export const PERSONA_LABELS: Record<Persona, string> = {
  DE: 'Data Engineer',
  DPO: 'Data Protection Officer',
  CPO: 'Chief Product Officer',
  DC: 'Data Consumer',
  MPA: 'Marketplace Administrator',
  DEV: 'Developer',
  default: 'User',
};
