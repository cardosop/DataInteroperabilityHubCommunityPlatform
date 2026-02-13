/**
 * Audit React Query Hooks
 */

import { useQuery } from '@tanstack/react-query';
import type { AuditEventListFilters } from '../../../shared/types/audit';
import { auditService } from '../services/auditService';

export function useAuditEvents(filters: AuditEventListFilters = {}) {
  return useQuery({
    queryKey: ['audit', 'events', 'list', filters],
    queryFn: () => auditService.list(filters),
  });
}

export function useAuditEvent(id: string | null) {
  return useQuery({
    queryKey: ['audit', 'events', 'detail', id],
    queryFn: () => auditService.getById(id!),
    enabled: !!id,
  });
}
