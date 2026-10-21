/**
 * Order Service
 * API client for marketplace order operations
 */

import { apiClient } from '../../../shared/api/client';
import { isApiError } from '../../../shared/types/api';
import type { PaginatedResponse } from '../../../shared/types/api';
import type {
  Order,
  OrderCreateRequest,
  OrderListFilters,
} from '../../../shared/types/marketplace';

const ORDERS_BASE_PATH = 'marketplace/orders';

export type PurchaseWithPaymentRequest = {
  listing_id: string;
  payment_method: string;
  payment_method_details: Record<string, string>;
  gateway?: string;
};

export type PurchaseWithPaymentSuccess = {
  order: Order;
  payment?: Record<string, unknown>;
  entitlement?: unknown;
};

export type PurchaseWithPaymentResult =
  | { kind: 'success'; data: PurchaseWithPaymentSuccess }
  | {
      kind: 'requires_action';
      client_secret: string;
      payment_intent_id: string;
      order_id: string;
      payment_id: string;
    };

export const orderService = {
  /**
   * List orders with filtering and pagination
   */
  async list(filters: OrderListFilters = {}): Promise<PaginatedResponse<Order>> {
    const params = new URLSearchParams();

    if (filters.page) params.append('page', filters.page.toString());
    if (filters.page_size) params.append('page_size', filters.page_size.toString());
    if (filters.ordering) params.append('ordering', filters.ordering);
    if (filters.status) params.append('status', filters.status);
    if (filters.listing_id) params.append('listing_id', filters.listing_id);

    const qs = params.toString();
    const url = qs ? `${ORDERS_BASE_PATH}/?${qs}` : `${ORDERS_BASE_PATH}/`;
    const response = await apiClient.getClient().get<PaginatedResponse<Order>>(url);
    return response.data;
  },

  /**
   * Get order by ID
   */
  async getById(id: string): Promise<Order> {
    const response = await apiClient.getClient().get<Order>(`${ORDERS_BASE_PATH}/${id}/`);
    return response.data;
  },

  /**
   * Create a new order
   * For FREE_AUTO_APPROVE listings, response format is {order: Order, entitlement?: Entitlement}
   * For regular orders, response format is just Order
   */
  async create(data: OrderCreateRequest): Promise<Order | { order: Order; entitlement?: unknown }> {
    const response = await apiClient
      .getClient()
      .post<Order | { order: Order; entitlement?: unknown }>(`${ORDERS_BASE_PATH}/`, data);
    return response.data;
  },

  /**
   * Paid checkout: POST /orders/purchase/ (402 when 3DS required).
   */
  async purchaseWithPayment(payload: PurchaseWithPaymentRequest): Promise<PurchaseWithPaymentResult> {
    try {
      const response = await apiClient
        .getClient()
        .post<PurchaseWithPaymentSuccess>(`${ORDERS_BASE_PATH}/purchase/`, payload);
      return { kind: 'success', data: response.data };
    } catch (e) {
      // Phase 209: replaced axios.isAxiosError with isApiError after axios supply chain compromise.
      // The fetch-based client normalizes errors to ApiError shape with http_status.
      // 402 Payment Required returns requires_action with client_secret for 3D Secure.
      if (isApiError(e) && e.error.http_status === 402) {
        const d = e.error.details as Record<string, unknown> | undefined;
        if (d?.requires_action && typeof d.client_secret === 'string') {
          return {
            kind: 'requires_action',
            client_secret: d.client_secret,
            payment_intent_id: String(d.payment_intent_id ?? ''),
            order_id: String(d.order_id ?? ''),
            payment_id: String(d.payment_id ?? ''),
          };
        }
      }
      throw e;
    }
  },

  /**
   * After 3DS, sync PI and complete order server-side.
   */
  async confirmPayment(orderId: string): Promise<unknown> {
    const response = await apiClient
      .getClient()
      .post<unknown>(`${ORDERS_BASE_PATH}/${orderId}/confirm-payment/`, {});
    return response.data;
  },

  /**
   * Provider / platform admin refund
   */
  async refund(orderId: string, body: { reason: string; amount?: string }): Promise<unknown> {
    const response = await apiClient
      .getClient()
      .post<unknown>(`${ORDERS_BASE_PATH}/${orderId}/refund/`, body);
    return response.data;
  },

  /**
   * Approve an order
   */
  async approve(id: string): Promise<Order> {
    const response = await apiClient.getClient().post<Order>(`${ORDERS_BASE_PATH}/${id}/approve/`);
    return response.data;
  },

  /**
   * Reject an order
   */
  async reject(id: string, reason?: string): Promise<Order> {
    const response = await apiClient.getClient().post<Order>(`${ORDERS_BASE_PATH}/${id}/reject/`, {
      reason,
    });
    return response.data;
  },

  /**
   * Cancel an order
   */
  async cancel(id: string): Promise<Order> {
    const response = await apiClient.getClient().post<Order>(`${ORDERS_BASE_PATH}/${id}/cancel/`);
    return response.data;
  },
};
