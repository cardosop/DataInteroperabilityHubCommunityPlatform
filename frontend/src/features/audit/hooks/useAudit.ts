/**
 * Audit React Query Hooks
 */

import { useQuery } from '@tanstack/react-query';
import type { AuditEventListFilters, ResourceType } from '../../../shared/types/audit';
import { auditService } from '../services/auditService';

export function useAuditEvents(
  filters: AuditEventListFilters = {},
  options?: { enabled?: boolean },
) {
  return useQuery({
    queryKey: ['audit', 'events', 'list', filters],
    queryFn: () => auditService.list(filters),
    enabled: options?.enabled !== false,
  });
}

export function useAuditEvent(id: string | null) {
  return useQuery({
    queryKey: ['audit', 'events', 'detail', id],
    queryFn: () => auditService.getById(id!),
    enabled: !!id,
  });
}

/**
 * Phase 224.3 — fetch the sanitized activity feed for a single resource.
 * Requires both ``resourceType`` and ``resourceId``; either missing → disabled.
 */
export function useResourceActivity(
  resourceType: ResourceType | null | undefined,
  resourceId: string | null | undefined,
  options?: { enabled?: boolean },
) {
  const enabled =
    options?.enabled !== false && !!resourceType && !!resourceId;
  return useQuery({
    queryKey: ['audit', 'resource-activity', resourceType, resourceId],
    queryFn: () => auditService.resourceActivity(resourceType!, resourceId!),
    enabled,
  });
}
