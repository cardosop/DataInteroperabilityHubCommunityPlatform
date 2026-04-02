/**
 * Orders React Query Hooks
 */

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useMutationWithNotification } from '../../../shared/hooks/useMutationWithNotification';
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

  return useMutationWithNotification({
    mutationFn: (data: OrderCreateRequest) => orderService.create(data),
    successMessage: 'Order created',
    errorMessage: 'Failed to create order',
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['marketplace', 'orders'] });
      queryClient.invalidateQueries({ queryKey: ['marketplace', 'entitlements'] });
    },
  });
}

/**
 * Same as useCreateOrder — free / request-access listings use POST /orders/.
 * Paid listings use the checkout page + orderService.purchaseWithPayment.
 */
export const usePurchaseListing = useCreateOrder;

export function useRefundOrder() {
  const queryClient = useQueryClient();

  return useMutationWithNotification({
    mutationFn: ({
      orderId,
      reason,
      amount,
    }: {
      orderId: string;
      reason: string;
      amount?: string;
    }) => orderService.refund(orderId, { reason, amount }),
    successMessage: 'Refund processed',
    errorMessage: 'Refund failed',
    onSuccess: (_, { orderId }) => {
      queryClient.invalidateQueries({ queryKey: ['marketplace', 'orders'] });
      queryClient.invalidateQueries({ queryKey: ['marketplace', 'orders', 'detail', orderId] });
      queryClient.invalidateQueries({ queryKey: ['marketplace', 'entitlements'] });
    },
  });
}

export function useApproveOrder() {
  const queryClient = useQueryClient();

  return useMutationWithNotification({
    mutationFn: (id: string) => orderService.approve(id),
    successMessage: 'Order approved',
    errorMessage: 'Failed to approve order',
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({ queryKey: ['marketplace', 'orders'] });
      queryClient.invalidateQueries({ queryKey: ['marketplace', 'orders', 'detail', id] });
      queryClient.invalidateQueries({ queryKey: ['marketplace', 'entitlements'] });
    },
  });
}

export function useRejectOrder() {
  const queryClient = useQueryClient();

  return useMutationWithNotification({
    mutationFn: ({ id, reason }: { id: string; reason?: string }) => orderService.reject(id, reason),
    successMessage: 'Order rejected',
    errorMessage: 'Failed to reject order',
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['marketplace', 'orders'] });
      queryClient.invalidateQueries({ queryKey: ['marketplace', 'orders', 'detail', variables.id] });
    },
  });
}

export function useCancelOrder() {
  const queryClient = useQueryClient();

  return useMutationWithNotification({
    mutationFn: (id: string) => orderService.cancel(id),
    successMessage: 'Order cancelled',
    errorMessage: 'Failed to cancel order',
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({ queryKey: ['marketplace', 'orders'] });
      queryClient.invalidateQueries({ queryKey: ['marketplace', 'orders', 'detail', id] });
    },
  });
}
