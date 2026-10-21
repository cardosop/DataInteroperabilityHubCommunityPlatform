/**
 * Phase 231.6 — centralized role predicates for shell navigation and
 * ``ProtectedRoute``. Keeps Sidebar / CommandPalette / route gates aligned.
 */

import type { User } from '../types/auth';

type RoleUserSlice = Pick<User, 'roles' | 'is_platform_admin'>;

/**
 * True when the item/route should be available: user holds any role in
 * ``requiredRole``, or is a platform admin and ``PLATFORM_ADMIN`` is among
 * the allowed roles (matches ``GET /auth/me/`` + JWT claim injection on the Hub;
 * survives brief hydration skew if ``roles`` lag ``is_platform_admin``).
 */
export function userHasAnyRequiredRole(
  user: RoleUserSlice | null | undefined,
  requiredRole?: string[] | null,
): boolean {
  if (!requiredRole?.length) return true;
  if (!user) return false;
  const roles = user.roles ?? [];
  if (requiredRole.some((r) => roles.includes(r))) return true;
  return user.is_platform_admin === true && requiredRole.includes('PLATFORM_ADMIN');
}
