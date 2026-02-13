/**
 * Order Service
 * API client for marketplace order operations
 */

import { apiClient } from '../../../shared/api/client';
import type { PaginatedResponse } from '../../../shared/types/api';
import type {
  Order,
  OrderCreateRequest,
  OrderListFilters,
} from '../../../shared/types/marketplace';

const ORDERS_BASE_PATH = 'marketplace/orders';

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

    const response = await apiClient.getClient().get<PaginatedResponse<Order>>(
      `${ORDERS_BASE_PATH}/${params.toString() ? `?${params.toString()}` : ''}`
    );
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
  async create(data: OrderCreateRequest): Promise<Order | { order: Order; entitlement?: any }> {
    const response = await apiClient.getClient().post<Order | { order: Order; entitlement?: any }>(`${ORDERS_BASE_PATH}/`, data);
    return response.data;
  },

  /**
   * Purchase (create order with auto-approval if applicable)
   */
  async purchase(listingId: string, purpose?: string): Promise<Order> {
    const response = await apiClient.getClient().post<Order>(`${ORDERS_BASE_PATH}/purchase/`, {
      listing_id: listingId,
      purpose,
    });
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
      rejection_reason: reason,
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
