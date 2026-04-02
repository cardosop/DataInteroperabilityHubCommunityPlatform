/**
 * Order List Page
 * View all orders
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { EmptyState } from '../../../shared/components/EmptyState';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { ListPageSkeleton } from '../../../shared/components/skeletons/ListPageSkeleton';
import { OrderStatus } from '../../../shared/types/marketplace';
import { useOrders } from '../hooks/useOrders';
import './OrderListPage.css';
import { Button } from '../../../shared/components/Button';

export function OrderListPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [pageSize] = useState(50);
  const [statusFilter, setStatusFilter] = useState<OrderStatus | ''>('');

  const filters = {
    page,
    page_size: pageSize,
    status: statusFilter || undefined,
    ordering: '-created_at',
  };

  const { data, isLoading, error, refetch } = useOrders(filters);

  const handleOrderClick = (orderId: string) => {
    navigate(`/marketplace/orders/${orderId}`);
  };

  if (isLoading) {
    return <ListPageSkeleton />;
  }

  if (error) {
    return <ErrorDisplay error={error} title="Failed to load orders" onRetry={() => refetch()} />;
  }

  if (!data?.results?.length) {
    return (
      <EmptyState
        title="No orders found"
        message={
          statusFilter
            ? 'Try adjusting your filters to see more results.'
            : "You haven't placed any orders yet."
        }
      />
    );
  }

  return (
    <div className="order-list-page">
      <div className="order-list-header">
        <h1>Orders</h1>
      </div>

      <div className="order-list-filters">
        <select
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value as OrderStatus | '');
            setPage(1);
          }}
          className="filter-select"
        >
          <option value="">All Statuses</option>
          <option value={OrderStatus.REQUESTED}>Requested</option>
          <option value={OrderStatus.APPROVED}>Approved</option>
          <option value={OrderStatus.REJECTED}>Rejected</option>
          <option value={OrderStatus.CANCELLED}>Cancelled</option>
          <option value={OrderStatus.FULFILLED}>Fulfilled</option>
        </select>
      </div>

      <div className="order-list-table">
        <table>
          <thead>
            <tr>
              <th>Listing</th>
              <th>Status</th>
              <th>Created</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {data.results.map((order) => (
              <tr key={order.id} onClick={() => handleOrderClick(order.id)} className="order-row">
                <td>{order.listing_title || order.listing}</td>
                <td>
                  <span className={`order-status order-status-${order.status.toLowerCase()}`}>
                    {order.status}
                  </span>
                </td>
                <td>{new Date(order.created_at).toLocaleDateString()}</td>
                <td>
                  <button
                    className="btn-link"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleOrderClick(order.id);
                    }}
                    type="button"
                  >
                    View
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {data.count > pageSize && (
        <div className="order-list-pagination">
          <Button
 variant="secondary"
 onClick={() => setPage((p) => Math.max(1, p - 1))}
 disabled={page === 1}>
            Previous
          </Button>
          <span className="pagination-info">
            Page {page} of {Math.ceil(data.count / pageSize)}
          </span>
          <Button
 variant="secondary"
 onClick={() => setPage((p) => p + 1)}
 disabled={page>= Math.ceil(data.count / pageSize)}>
            Next
          </Button>
        </div>
      )}
    </div>
  );
}
