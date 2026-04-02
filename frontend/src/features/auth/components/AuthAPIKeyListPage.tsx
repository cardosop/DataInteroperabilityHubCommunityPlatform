/**
 * Auth API Keys Page
 * List, create, delete Auth API keys (login/programmatic). Not BaaS API keys.
 * Route: /settings/api-keys
 */

import { useEffect, useState } from 'react';
import type { ApiError } from '../../../shared/types/api';
import { ConfirmDialog } from '../../../shared/components/ConfirmDialog';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { useToast } from '../../../shared/components/Toast';
import { ListPageSkeleton } from '../../../shared/components/skeletons/ListPageSkeleton';
import type {
  AuthAPIKey,
  AuthAPIKeyCreate,
  AuthAPIKeyCreateResponse,
} from '../../../shared/types/auth';
import { normalizeError } from '../../../shared/utils/errorUtils';
import { authService } from '../services/authService';
import './AuthAPIKeyListPage.css';
import { Button } from '../../../shared/components/Button';

export function AuthAPIKeyListPage() {
  const [keys, setKeys] = useState<AuthAPIKey[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [createdKey, setCreatedKey] = useState<AuthAPIKeyCreateResponse | null>(null);
  const [createForm, setCreateForm] = useState<AuthAPIKeyCreate>({
    name: '',
    scopes: [],
    expires_in_days: undefined,
  });
  const [createSubmitting, setCreateSubmitting] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const toast = useToast();

  const loadKeys = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await authService.listAuthApiKeys({ page, page_size: 20 });
      setKeys(data.results);
      setTotalPages(data.total_pages);
    } catch (err) {
      setError(normalizeError(err));
    } finally {
      setLoading(false);
    }
  };

  /* eslint-disable react-hooks/exhaustive-deps */
  useEffect(() => {
    loadKeys();
  }, [page]);
  /* eslint-enable react-hooks/exhaustive-deps */

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreateError(null);
    setCreateSubmitting(true);
    try {
      const payload: AuthAPIKeyCreate = {
        name: createForm.name.trim(),
        scopes: Array.isArray(createForm.scopes) ? createForm.scopes : [],
        expires_in_days: createForm.expires_in_days ?? undefined,
      };
      const result = await authService.createAuthApiKey(payload);
      setCreatedKey(result);
      setCreateForm({ name: '', scopes: [], expires_in_days: undefined });
      loadKeys();
    } catch (err: unknown) {
      const normalized = normalizeError(err);
      setCreateError(normalized.error.message);
    } finally {
      setCreateSubmitting(false);
    }
  };

  const handleCloseCreated = () => {
    setCreatedKey(null);
    setCreateModalOpen(false);
  };

  const handleDeleteClick = (keyId: string) => setConfirmDeleteId(keyId);
  const handleDeleteConfirm = async () => {
    const keyId = confirmDeleteId;
    if (!keyId) return;
    setConfirmDeleteId(null);
    setDeletingId(keyId);
    try {
      await authService.deleteAuthApiKey(keyId);
      setKeys((prev) => prev.filter((k) => k.id !== keyId));
      toast.success('API key deleted.');
    } catch (err) {
      const normalized = normalizeError(err);
      setError(normalized);
      toast.error(normalized.error.message);
    } finally {
      setDeletingId(null);
    }
  };

  if (loading && keys.length === 0) {
    return <ListPageSkeleton />;
  }

  return (
    <div className="auth-api-key-list-page">
      <div className="auth-api-key-list-header">
        <div>
          <h1>Auth API Keys</h1>
          <p className="auth-api-key-clarification">
            Programmatic login keys for API access. These are <strong>not</strong> BaaS API keys.
          </p>
        </div>
        <Button variant="primary" onClick={() => setCreateModalOpen(true)}>
          Create API key
        </Button>
      </div>

      {error && (
        <ErrorDisplay error={error} title="Failed to load API keys" onRetry={() => loadKeys()} />
      )}

      {keys.length === 0 && !error ? (
        <div className="auth-api-key-empty">
          <p>No API keys yet. Create one for programmatic access.</p>
        </div>
      ) : (
        <div className="auth-api-key-table-wrap">
          <table className="auth-api-key-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Scopes</th>
                <th>Expires</th>
                <th>Last used</th>
                <th>Created</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {keys.map((key) => (
                <tr key={key.id}>
                  <td>{key.name}</td>
                  <td>{key.scopes?.length ? key.scopes.join(', ') : '—'}</td>
                  <td>
                    {key.expires_at ? new Date(key.expires_at).toLocaleDateString() : 'Never'}
                  </td>
                  <td>{key.last_used_at ? new Date(key.last_used_at).toLocaleString() : '—'}</td>
                  <td>{new Date(key.created_at).toLocaleString()}</td>
                  <td>
                    <Button
 variant="danger" size="sm"
 onClick={() => handleDeleteClick(key.id)}
 disabled={deletingId === key.id}>
                      {deletingId === key.id ? 'Deleting...' : 'Delete'}
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {totalPages > 1 && (
        <div className="auth-api-key-pagination">
          <button
            type="button"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page <= 1}
          >
            Previous
          </button>
          <span>
            Page {page} of {totalPages}
          </span>
          <button type="button" onClick={() => setPage((p) => p + 1)} disabled={page >= totalPages}>
            Next
          </button>
        </div>
      )}

      {createModalOpen && (
        <div className="auth-api-key-modal-overlay" role="dialog" aria-modal="true">
          <div className="auth-api-key-modal">
            {createdKey ? (
              <>
                <h2>API key created</h2>
                <p className="auth-api-key-warning">
                  Copy this key now. You won&apos;t see it again.
                </p>
                <div className="auth-api-key-plaintext-wrap">
                  <code className="auth-api-key-plaintext">{createdKey.api_key}</code>
                  <button
                    type="button"
                    className="btn-copy"
                    onClick={() => navigator.clipboard.writeText(createdKey.api_key)}
                  >
                    Copy
                  </button>
                </div>
                <div className="auth-api-key-modal-actions">
                  <Button variant="primary" onClick={handleCloseCreated}>
                    Done
                  </Button>
                </div>
              </>
            ) : (
              <>
                <h2>Create Auth API key</h2>
                <form onSubmit={handleCreate} className="auth-api-key-form">
                  <div className="form-group">
                    <label htmlFor="api-key-name">
                      Name <span className="required">*</span>
                    </label>
                    <input
                      id="api-key-name"
                      type="text"
                      value={createForm.name}
                      onChange={(e) => setCreateForm({ ...createForm, name: e.target.value })}
                      required
                      placeholder="e.g. CI pipeline"
                    />
                  </div>
                  <div className="form-group">
                    <label htmlFor="api-key-scopes">Scopes (optional, comma-separated)</label>
                    <input
                      id="api-key-scopes"
                      type="text"
                      value={Array.isArray(createForm.scopes) ? createForm.scopes.join(', ') : ''}
                      onChange={(e) =>
                        setCreateForm({
                          ...createForm,
                          scopes: e.target.value
                            .split(',')
                            .map((s) => s.trim())
                            .filter(Boolean),
                        })
                      }
                      placeholder="e.g. assets:read, assets:write"
                    />
                  </div>
                  <div className="form-group">
                    <label htmlFor="api-key-expires">Expires in (days, optional)</label>
                    <input
                      id="api-key-expires"
                      type="number"
                      min={1}
                      value={createForm.expires_in_days ?? ''}
                      onChange={(e) =>
                        setCreateForm({
                          ...createForm,
                          expires_in_days: e.target.value
                            ? parseInt(e.target.value, 10)
                            : undefined,
                        })
                      }
                      placeholder="Leave empty for no expiry"
                    />
                  </div>
                  {createError && (
                    <p className="auth-api-key-error" role="alert">
                      {createError}
                    </p>
                  )}
                  <div className="auth-api-key-modal-actions">
                    <Button
 variant="secondary"
 onClick={() => setCreateModalOpen(false)}>
                      Cancel
                    </Button>
                    <Button type="submit" variant="primary" disabled={createSubmitting}>
                      {createSubmitting ? 'Creating...' : 'Create'}
                    </Button>
                  </div>
                </form>
              </>
            )}
          </div>
        </div>
      )}

      <ConfirmDialog
        isOpen={confirmDeleteId !== null}
        onClose={() => setConfirmDeleteId(null)}
        onConfirm={handleDeleteConfirm}
        title="Delete API key"
        message="Delete this API key? It will stop working immediately."
        confirmLabel="Delete"
        variant="danger"
      />
    </div>
  );
}
