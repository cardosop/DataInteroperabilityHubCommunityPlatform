/**
 * DelegationSettingsPage — Phase 272.6.7
 *
 * Allows a TENANT_ADMIN to create, view, and revoke approval delegations
 * for out-of-office coverage. A delegation authorizes a delegate to
 * approve access requests on the delegator's behalf during a defined
 * time window.
 *
 * Data sources:
 * - ``GET /api/v1/governance/delegations/`` — list active/inactive delegations
 * - ``POST /api/v1/governance/delegations/`` — create new delegation
 * - ``DELETE /api/v1/governance/delegations/{id}/`` — revoke early
 */

import { useEffect, useState, useCallback } from 'react';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { Button } from '../../../shared/components/Button';
import { apiClient } from '../../../shared/api/client';
import './DelegationSettingsPage.css';

const DELEGATIONS_PATH = '/governance/delegations/';

interface DelegationRecord {
  id: string;
  delegate_email: string;
  delegate_name: string;
  start_at: string;
  end_at: string;
  reason: string;
  is_active: boolean;
  created_at: string;
}

export function DelegationSettingsPage() {
  const [delegations, setDelegations] = useState<DelegationRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);

  // Form state
  const [delegateEmail, setDelegateEmail] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [reason, setReason] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const fetchDelegations = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // The SPA apiClient carries the Bearer token + tenant context —
      // a raw cookie fetch is 401 here (the SPA login is token-based,
      // no session cookie exists).
      const response = await apiClient.getClient().get<unknown>(DELEGATIONS_PATH);
      const data = response.data as
        | Partial<{ results: DelegationRecord[] }>
        | DelegationRecord[];
      setDelegations(Array.isArray(data) ? data : (data.results ?? []));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load delegations');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDelegations();
  }, [fetchDelegations]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    setSuccessMessage(null);

    if (!delegateEmail.trim()) {
      setFormError('Delegate email is required.');
      return;
    }
    if (!startDate || !endDate) {
      setFormError('Start and end dates are required.');
      return;
    }
    if (new Date(endDate) <= new Date(startDate)) {
      setFormError('End date must be after start date.');
      return;
    }

    setSubmitting(true);
    try {
      await apiClient.getClient().post(DELEGATIONS_PATH, {
        delegate_email: delegateEmail.trim(),
        // The date inputs carry yyyy-mm-dd; the API contract is full
        // ISO datetimes. The window covers the WHOLE chosen days —
        // start at 00:00:00, end at 23:59:59 of the end date.
        start_at: `${startDate}T00:00:00`,
        end_at: `${endDate}T23:59:59`,
        reason: reason.trim() || undefined,
      });
      setSuccessMessage('Delegation created successfully.');
      setDelegateEmail('');
      setStartDate('');
      setEndDate('');
      setReason('');
      setShowForm(false);
      fetchDelegations();
    } catch (err) {
      // The apiClient rejects with its normalized ApiError shape
      // ({error: {code, message, ...}}) — surface the REAL backend
      // message (the classified 400 detail rides in error.message),
      // never a bare HTTP status.
      const apiMessage = (err as { error?: { message?: string } })?.error?.message;
      setFormError(
        apiMessage ?? (err instanceof Error ? err.message : 'Failed to create delegation')
      );
    } finally {
      setSubmitting(false);
    }
  };

  const handleRevoke = async (id: string) => {
    try {
      await apiClient.getClient().delete(`${DELEGATIONS_PATH}${id}/`);
      fetchDelegations();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to revoke delegation');
    }
  };

  if (loading) return <LoadingSpinner data-testid="delegation-loading" />;
  if (error) {
    return (
      <ErrorDisplay
        error={error}
        title="Failed to load delegations"
        onRetry={() => fetchDelegations()}
      />
    );
  }

  return (
    <div className="delegation-settings-page" data-testid="delegation-settings-page">
      <h1>Approval Delegation</h1>
      <p>
        Delegate your approval authority to another user for a defined time window (e.g.,
        out-of-office coverage). Delegates can approve access requests on your behalf during the
        active window.
      </p>

      {successMessage && (
        <div role="status" className="delegation-success">
          {successMessage}
        </div>
      )}

      <div className="delegation-actions">
        <Button
          variant="primary"
          onClick={() => setShowForm(!showForm)}
          data-testid="toggle-delegation-form"
        >
          {showForm ? 'Cancel' : 'New Delegation'}
        </Button>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className="delegation-form" data-testid="delegation-form">
          {formError && (
            <div role="alert" className="delegation-form-error">
              {formError}
            </div>
          )}

          <div className="delegation-form-field">
            <label htmlFor="delegate-email">Delegate Email</label>
            <input
              id="delegate-email"
              type="email"
              value={delegateEmail}
              onChange={(e) => setDelegateEmail(e.target.value)}
              placeholder="colleague@company.com"
              required
            />
          </div>

          <div className="delegation-form-field">
            <label htmlFor="start-date">Start Date</label>
            <input
              id="start-date"
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              required
            />
          </div>

          <div className="delegation-form-field">
            <label htmlFor="end-date">End Date</label>
            <input
              id="end-date"
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              required
            />
          </div>

          <div className="delegation-form-field">
            <label htmlFor="reason">Reason (optional)</label>
            <input
              id="reason"
              type="text"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Out of office — annual leave"
              maxLength={500}
            />
          </div>

          <Button type="submit" variant="primary" loading={submitting}>
            Create Delegation
          </Button>
        </form>
      )}

      {delegations.length === 0 ? (
        <p className="delegation-empty">No active delegations.</p>
      ) : (
        <table className="delegation-table" data-testid="delegation-table">
          <thead>
            <tr>
              <th>Delegate</th>
              <th>Start</th>
              <th>End</th>
              <th>Status</th>
              <th>Reason</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {delegations.map((d) => (
              <tr key={d.id} data-testid={`delegation-row-${d.id}`}>
                <td>
                  {d.delegate_name && (
                    <span className="delegate-name">
                      {d.delegate_name}
                      <br />
                    </span>
                  )}
                  <code>{d.delegate_email}</code>
                </td>
                <td>{new Date(d.start_at).toLocaleDateString()}</td>
                <td>{new Date(d.end_at).toLocaleDateString()}</td>
                <td>
                  <span
                    className={`delegation-status delegation-status-${d.is_active ? 'active' : 'inactive'}`}
                  >
                    {d.is_active ? 'Active' : 'Inactive'}
                  </span>
                </td>
                <td>{d.reason || '-'}</td>
                <td>
                  {d.is_active && (
                    <Button
                      variant="danger"
                      size="sm"
                      onClick={() => handleRevoke(d.id)}
                      data-testid={`revoke-delegation-${d.id}`}
                    >
                      Revoke
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
