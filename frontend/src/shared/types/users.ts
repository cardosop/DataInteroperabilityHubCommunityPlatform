/**
 * User Types
 * Based on backend user models and serializers
 */

export interface User {
  id: string;
  email: string;
  display_name?: string;
  status: 'ACTIVE' | 'INACTIVE' | 'PENDING' | 'SUSPENDED';
  tenant?: string;
  tenant_name?: string;
  roles?: string[];
  created_at: string;
  updated_at: string;
}

export interface UserListFilters {
  page?: number;
  page_size?: number;
  status?: string;
}
