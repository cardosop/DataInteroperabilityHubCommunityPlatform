/**
 * Customer List Page — Phase 116C.1
 * Groups API keys by customer_id, shows usage totals per customer.
 */

import { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAPIKeys } from '../hooks/useBaaS';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { EmptyState } from '../../../shared/components/EmptyState';
import type { CustomerSummary } from '../../../shared/types/baas';

export function CustomerListPage() {
  const navigate = useNavigate();
  const { data: apiKeysData, isLoading, error } = useAPIKeys();

  const customers = useMemo<CustomerSummary[]>(() => {
    if (!apiKeysData?.results) return [];
    const map = new Map<string, CustomerSummary>();
    for (const key of apiKeysData.results) {
      const cid = key.customer_id;
      if (!cid) continue;
      const existing = map.get(cid);
      if (existing) {
        existing.api_key_count += 1;
      } else {
        map.set(cid, {
          customer_id: cid,
          customer_name: key.customer_name || cid,
          customer_email: key.customer_email || '',
          api_key_count: 1,
          total_requests: 0,
          total_billed: '0.00',
          currency: 'USD',
        });
      }
    }
    return Array.from(map.values());
  }, [apiKeysData]);

  if (isLoading) return <LoadingSpinner message="Loading customers..." />;
  if (error) return <ErrorDisplay error={error} title="Failed to load customers" />;
  if (customers.length === 0) {
    return (
      <EmptyState
        title="No customers"
        message="Customers appear when API keys are created with a customer_id."
      />
    );
  }

  return (
    <div className="customer-list-page">
      <div className="section-header">
        <h2>Customers</h2>
        <span className="badge">{customers.length}</span>
      </div>
      <table className="billing-table">
        <thead>
          <tr>
            <th>Customer</th>
            <th>Customer ID</th>
            <th>Email</th>
            <th>API Keys</th>
          </tr>
        </thead>
        <tbody>
          {customers.map((c) => (
            <tr
              key={c.customer_id}
              className="clickable-row"
              onClick={() => navigate(`/settings/baas/customers/${encodeURIComponent(c.customer_id)}`)}
            >
              <td className="customer-name">{c.customer_name}</td>
              <td><code>{c.customer_id}</code></td>
              <td>{c.customer_email || '—'}</td>
              <td>{c.api_key_count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
