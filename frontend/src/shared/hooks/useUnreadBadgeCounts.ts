/**
 * useUnreadBadgeCounts — sidebar badge counters.
 *
 * Currently surfaces PENDING governance access-requests for admin users.
 * The hook intentionally short-circuits for non-admins so that regular
 * users never issue the admin-only `/pending-count/` request (which would
 * otherwise 403 every 60s for every logged-in user).
 */

import { useQuery } from '@tanstack/react-query';
import { useAuthStore } from '../../features/auth/store/authStore';
import { governanceService } from '../../features/governance/services/governanceService';

export interface UnreadBadgeCounts {
  /** PENDING governance access requests visible to the caller. */
  governancePending: number;
}

const ADMIN_ROLES = ['TENANT_ADMIN', 'PLATFORM_ADMIN'] as const;

function userIsAdmin(roles: string[] | undefined, isPlatformAdmin: boolean | undefined): boolean {
  if (isPlatformAdmin) return true;
  if (!roles) return false;
  return roles.some((r) => (ADMIN_ROLES as readonly string[]).includes(r));
}

export function useUnreadBadgeCounts(): UnreadBadgeCounts {
  const user = useAuthStore((s) => s.user);
  const isAdmin = userIsAdmin(user?.roles, user?.is_platform_admin);

  const { data } = useQuery({
    queryKey: ['badges', 'governance', 'pending-count'],
    queryFn: () => governanceService.getPendingCount(),
    enabled: isAdmin,
    refetchInterval: 60_000,
    staleTime: 30_000,
    retry: 1,
  });

  return {
    governancePending: data ?? 0,
  };
}
