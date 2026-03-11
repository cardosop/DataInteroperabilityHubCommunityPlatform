/**
 * Billing React Query Hooks
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { billingService } from '../services/billingService';

export function useCurrentSubscription(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['billing', 'subscription', 'current'],
    queryFn: () => billingService.getCurrentSubscription(),
    enabled: options?.enabled !== false,
  });
}

export function usePlans(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['billing', 'plans'],
    queryFn: () => billingService.getPlans(),
    enabled: options?.enabled !== false,
  });
}

export function useChangePlan() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (planSlug: string) => billingService.changePlan(planSlug),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['billing', 'subscription', 'current'] });
    },
  });
}

export function useInvoices(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['billing', 'invoices'],
    queryFn: () => billingService.getInvoices(),
    enabled: options?.enabled !== false,
  });
}
