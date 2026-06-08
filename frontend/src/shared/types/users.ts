/**
 * User Types
 * Based on backend user models and serializers
 */

/** Role as returned by API (object) or legacy string */
export type UserRole = string | { id: string; name: string };

/** Tenant as returned by API (object) or legacy string ID */
export type UserTenant = string | { id: string; name: string };

export interface User {
  id: string;
  email: string;
  display_name?: string;
  status: 'ACTIVE' | 'INACTIVE' | 'PENDING' | 'SUSPENDED';
  tenant?: UserTenant;
  tenant_id?: string;
  tenant_name?: string;
  roles?: UserRole[];
  has_seen_tour?: boolean;
  created_at: string;
  updated_at: string;
}

export interface UserListFilters {
  page?: number;
  page_size?: number;
  status?: string;
}
