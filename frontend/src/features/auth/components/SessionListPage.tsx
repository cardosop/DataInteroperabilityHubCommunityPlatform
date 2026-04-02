/**
 * Active Sessions Page
 * Lists active sessions (refresh tokens) with Revoke per session.
 * Route: /settings/sessions
 */

import { useEffect, useState } from 'react';
import { ConfirmDialog } from '../../../shared/components/ConfirmDialog';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { useToast } from '../../../shared/components/Toast';
import { ListPageSkeleton } from '../../../shared/components/skeletons/ListPageSkeleton';
import type { ApiError } from '../../../shared/types/api';
import type { Session } from '../../../shared/types/auth';
import { normalizeError } from '../../../shared/utils/errorUtils';
import { authService } from '../services/authService';
import './SessionListPage.css';

export function SessionListPage() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);
  const [revokingId, setRevokingId] = useState<string | null>(null);
  const [confirmRevokeId, setConfirmRevokeId] = useState<string | null>(null);
  const toast = useToast();

  const loadSessions = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await authService.listSessions();
      setSessions(data);
    } catch (err) {
      setError(normalizeError(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSessions();
  }, []);

  const handleRevokeClick = (sessionId: string) => setConfirmRevokeId(sessionId);
  const handleRevokeConfirm = async () => {
    const sessionId = confirmRevokeId;
    if (!sessionId) return;
    setConfirmRevokeId(null);
    setRevokingId(sessionId);
    try {
      await authService.revokeSession(sessionId);
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));
      toast.success('Session revoked.');
    } catch (err) {
      const normalized = normalizeError(err);
      setError(normalized);
      toast.error(normalized.error.message);
    } finally {
      setRevokingId(null);
    }
  };

  if (loading) {
    return <ListPageSkeleton />;
  }

  if (error) {
    return (
      <ErrorDisplay error={error} title="Failed to load sessions" onRetry={() => loadSessions()} />
    );
  }

  return (
    <div className="session-list-page">
      <div className="session-list-header">
        <h1>Active Sessions</h1>
        <p className="session-list-description">
          Sessions where you are signed in. Revoke any session to sign out that device.
        </p>
      </div>

      {sessions.length === 0 ? (
        <div className="session-list-empty">
          <p>No active sessions.</p>
        </div>
      ) : (
        <div className="session-list-table-wrap">
          <table className="session-list-table">
            <thead>
              <tr>
                <th>Created</th>
                <th>Expires</th>
                <th>Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {sessions.map((session) => (
                <tr key={session.id}>
                  <td>{new Date(session.created_at).toLocaleString()}</td>
                  <td>{new Date(session.expires_at).toLocaleString()}</td>
                  <td>
                    {session.revoked_at ? (
                      <span className="session-status revoked">Revoked</span>
                    ) : session.is_current ? (
                      <span className="session-status current">Current</span>
                    ) : (
                      <span className="session-status active">Active</span>
                    )}
                  </td>
                  <td>
                    {!session.revoked_at && (
                      <button
                        type="button"
                        className="btn-revoke"
                        onClick={() => handleRevokeClick(session.id)}
                        disabled={revokingId === session.id}
                      >
                        {revokingId === session.id ? 'Revoking...' : 'Revoke'}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <ConfirmDialog
        isOpen={confirmRevokeId !== null}
        onClose={() => setConfirmRevokeId(null)}
        onConfirm={handleRevokeConfirm}
        title="Revoke session"
        message="Revoke this session? The user will need to sign in again on that device."
        confirmLabel="Revoke"
        variant="warning"
      />
    </div>
  );
}
