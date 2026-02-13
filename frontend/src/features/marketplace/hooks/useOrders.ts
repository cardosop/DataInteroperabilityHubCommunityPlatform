/**
 * Orders React Query Hooks
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { orderService } from '../services/orderService';
import type {
  OrderCreateRequest,
  OrderListFilters,
} from '../../../shared/types/marketplace';

export function useOrders(filters: OrderListFilters = {}) {
  return useQuery({
    queryKey: ['marketplace', 'orders', 'list', filters],
    queryFn: () => orderService.list(filters),
  });
}

export function useOrder(id: string | null) {
  return useQuery({
    queryKey: ['marketplace', 'orders', 'detail', id],
    queryFn: () => orderService.getById(id!),
    enabled: !!id,
  });
}

export function useCreateOrder() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: OrderCreateRequest) => orderService.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['marketplace', 'orders'] });
      queryClient.invalidateQueries({ queryKey: ['marketplace', 'entitlements'] });
    },
  });
}

export function usePurchaseListing() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ listingId, purpose }: { listingId: string; purpose?: string }) =>
      orderService.purchase(listingId, purpose),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['marketplace', 'orders'] });
      queryClient.invalidateQueries({ queryKey: ['marketplace', 'entitlements'] });
    },
  });
}

export function useApproveOrder() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => orderService.approve(id),
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({ queryKey: ['marketplace', 'orders'] });
      queryClient.invalidateQueries({ queryKey: ['marketplace', 'orders', 'detail', id] });
      queryClient.invalidateQueries({ queryKey: ['marketplace', 'entitlements'] });
    },
  });
}

export function useRejectOrder() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, reason }: { id: string; reason?: string }) => orderService.reject(id, reason),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['marketplace', 'orders'] });
      queryClient.invalidateQueries({ queryKey: ['marketplace', 'orders', 'detail', variables.id] });
    },
  });
}

export function useCancelOrder() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => orderService.cancel(id),
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({ queryKey: ['marketplace', 'orders'] });
      queryClient.invalidateQueries({ queryKey: ['marketplace', 'orders', 'detail', id] });
    },
  });
}
