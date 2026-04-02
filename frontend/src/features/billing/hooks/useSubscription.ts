/**
 * Billing React Query Hooks
 */

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useMutationWithNotification } from '../../../shared/hooks/useMutationWithNotification';
import { billingService } from '../services/billingService';
import type { BillingApiError } from '../services/billingService';

export function useCurrentSubscription(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['billing', 'subscription', 'current'],
    queryFn: () => billingService.getCurrentSubscription(),
    enabled: options?.enabled !== false,
    staleTime: 5 * 60 * 1000, // 5 minutes
    refetchInterval: 60 * 1000, // 1 minute
  });
}

export function usePlans(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['billing', 'plans'],
    queryFn: () => billingService.getPlans(),
    enabled: options?.enabled !== false,
    staleTime: 10 * 60 * 1000, // 10 minutes — plans rarely change
  });
}

/** Map billing API error codes to user-friendly messages. */
function getChangePlanErrorMessage(error: unknown): string {
  const axiosError = error as { response?: { data?: BillingApiError } };
  const data = axiosError?.response?.data;

  if (data?.code === 'plan_limit_exceeded') {
    const detail = data.details as { limit_key?: string; current?: number; max?: number } | undefined;
    return detail?.limit_key
      ? `Your usage of ${detail.limit_key.replace(/_/g, ' ')} (${detail.current}) exceeds the new plan's limit (${detail.max}). Reduce usage before downgrading.`
      : 'Your current usage exceeds the limits of the selected plan.';
  }

  if (data?.code === 'tenant_suspended') {
    return 'Your account is suspended. Please contact support to resolve billing issues before changing plans.';
  }

  if (data?.code === 'subscription_inactive') {
    return 'Your subscription is not active. Only active subscriptions can change plans.';
  }

  // Fallback to server message or generic
  return data?.error ?? (error as Error)?.message ?? 'Failed to change plan';
}

export function useChangePlan() {
  const queryClient = useQueryClient();
  return useMutationWithNotification({
    mutationFn: (planSlug: string) => billingService.changePlan(planSlug),
    successMessage: 'Plan changed',
    errorMessage: (error: unknown) => getChangePlanErrorMessage(error),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['billing', 'subscription', 'current'] });
      queryClient.invalidateQueries({ queryKey: ['billing', 'plans'] });
    },
  });
}

export function useInvoices(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['billing', 'invoices'],
    queryFn: () => billingService.getInvoices(),
    enabled: options?.enabled !== false,
    staleTime: 5 * 60 * 1000,
  });
}

export function useMLSubscription(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['billing', 'ml-subscription', 'current'],
    queryFn: () => billingService.getMLSubscription(),
    enabled: options?.enabled !== false,
    staleTime: 5 * 60 * 1000,
  });
}
