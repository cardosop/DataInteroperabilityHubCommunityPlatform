/**
 * Privacy & Data Page
 * GDPR export (Article 20) and erasure (Article 17) requests.
 * Route: /settings/privacy
 */

import { useEffect, useState } from 'react';
import { Breadcrumbs } from '../../../shared/components/Breadcrumbs';
import { ConfirmDialog } from '../../../shared/components/ConfirmDialog';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { useToast } from '../../../shared/components/Toast';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import type { ApiError } from '../../../shared/types/api';
import type {
  DataExportJob,
  DataExportStatus,
  ErasureRequest,
  ErasureRequestStatus,
} from '../../../shared/types/gdpr';
import { normalizeError } from '../../../shared/utils/errorUtils';
import { gdprService } from '../services/gdprService';
import './PrivacyPage.css';

export function PrivacyPage() {
  const [exportJobs, setExportJobs] = useState<DataExportJob[]>([]);
  const [erasureRequests, setErasureRequests] = useState<ErasureRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);
  const [exporting, setExporting] = useState(false);
  const [erasing, setErasing] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [showErasureConfirm, setShowErasureConfirm] = useState(false);
  const toast = useToast();

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [exportsRes, erasuresRes] = await Promise.all([
        gdprService.listExportJobs({ page_size: 20 }),
        gdprService.listErasureRequests({ page_size: 20 }),
      ]);
      setExportJobs(exportsRes.results);
      setErasureRequests(erasuresRes.results);
    } catch (err) {
      setError(normalizeError(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleRequestExport = async () => {
    setExporting(true);
    setError(null);
    setSuccessMessage(null);
    try {
      const result = await gdprService.requestExport();
      setSuccessMessage(
        result.status === 'COMPLETED' && result.download_url
          ? 'Export ready. Download link available below.'
          : `Export ${result.status.toLowerCase()}. Refreshing list...`
      );
      await loadData();
      if (result.status === 'COMPLETED' && result.download_url) {
        window.open(result.download_url, '_blank', 'noopener,noreferrer');
      }
    } catch (err) {
      setError(normalizeError(err));
    } finally {
      setExporting(false);
    }
  };

  const handleRequestErasureClick = () => setShowErasureConfirm(true);
  const handleRequestErasureConfirm = async () => {
    setShowErasureConfirm(false);
    setErasing(true);
    setError(null);
    setSuccessMessage(null);
    try {
      await gdprService.requestErasure();
      setSuccessMessage('Erasure completed. You will be logged out.');
      await loadData();
      // Erasure typically logs the user out; redirect after short delay
      setTimeout(() => {
        window.location.href = '/login';
      }, 2000);
    } catch (err) {
      const normalized = normalizeError(err);
      setError(normalized);
      toast.error(normalized.error.message);
    } finally {
      setErasing(false);
    }
  };

  const formatStatus = (status: DataExportStatus | ErasureRequestStatus) => {
    const map: Record<string, string> = {
      PENDING: 'Pending',
      PROCESSING: 'Processing',
      COMPLETED: 'Completed',
      FAILED: 'Failed',
    };
    return map[status] ?? status;
  };

  const formatDate = (iso: string) => {
    try {
      return new Date(iso).toLocaleString();
    } catch {
      return iso;
    }
  };

  if (loading && exportJobs.length === 0 && erasureRequests.length === 0) {
    return <LoadingSpinner message="Loading privacy data..." />;
  }

  return (
    <div className="privacy-page" data-testid="privacy-page">
      <Breadcrumbs
        items={[
          { label: 'Home', href: '/' },
          { label: 'Settings', href: '/settings/profile' },
          { label: 'Privacy' },
        ]}
      />
      <div className="privacy-header">
        <h1>Privacy & Data</h1>
        <p className="privacy-description">
          Request a copy of your data (GDPR Article 20) or request erasure of your personal data
          (GDPR Article 17 - Right to be Forgotten).
        </p>
      </div>

      {error && (
        <ErrorDisplay error={error} title="Error" onRetry={() => loadData()} />
      )}

      {successMessage && (
        <div className="privacy-success" role="status">
          {successMessage}
        </div>
      )}

      <section className="privacy-section" data-testid="privacy-export-section">
        <h2>Data Export (Article 20)</h2>
        <p className="privacy-section-desc">
          Download a copy of your data stored in the platform (profile, audit events, assets,
          datasets, contracts).
        </p>
        <button
          type="button"
          className="btn-request-export"
          onClick={handleRequestExport}
          disabled={exporting}
          data-testid="btn-request-export"
        >
          {exporting ? 'Creating export...' : 'Request data export'}
        </button>

        {exportJobs.length > 0 && (
          <div className="privacy-table-wrap">
            <table className="privacy-table">
              <thead>
                <tr>
                  <th>Created</th>
                  <th>Status</th>
                  <th>Download</th>
                </tr>
              </thead>
              <tbody>
                {exportJobs.map((job) => (
                  <tr key={job.id}>
                    <td>{formatDate(job.created_at)}</td>
                    <td>
                      <span className={`status-badge status-${job.status.toLowerCase()}`}>
                        {formatStatus(job.status)}
                      </span>
                      {job.error_message && (
                        <span className="status-error" title={job.error_message}>
                          {' '}(error)
                        </span>
                      )}
                    </td>
                    <td>
                      {job.status === 'COMPLETED' && job.download_url ? (
                        <a
                          href={job.download_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="link-download"
                        >
                          Download
                        </a>
                      ) : (
                        '—'
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="privacy-section" data-testid="privacy-erasure-section">
        <h2>Data Erasure (Article 17)</h2>
        <p className="privacy-section-desc">
          Request permanent anonymization of your profile and revocation of all sessions. Your
          email and display name will be anonymized; some data may be retained for legal
          compliance.
        </p>
        <button
          type="button"
          className="btn-request-erasure"
          onClick={handleRequestErasureClick}
          disabled={erasing}
          data-testid="btn-request-erasure"
        >
          {erasing ? 'Processing...' : 'Request data erasure'}
        </button>

        {erasureRequests.length > 0 && (
          <div className="privacy-table-wrap">
            <table className="privacy-table">
              <thead>
                <tr>
                  <th>Requested</th>
                  <th>Completed</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {erasureRequests.map((req) => (
                  <tr key={req.id}>
                    <td>{formatDate(req.requested_at)}</td>
                    <td>{req.completed_at ? formatDate(req.completed_at) : '—'}</td>
                    <td>
                      <span className={`status-badge status-${req.status.toLowerCase()}`}>
                        {formatStatus(req.status)}
                      </span>
                      {req.error_message && (
                        <span className="status-error" title={req.error_message}>
                          {' '}(error)
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <ConfirmDialog
        isOpen={showErasureConfirm}
        onClose={() => setShowErasureConfirm(false)}
        onConfirm={handleRequestErasureConfirm}
        title="Request data erasure"
        message="This will permanently anonymize your profile and revoke all sessions. You will be logged out. This action cannot be undone. Continue?"
        confirmLabel="Continue"
        variant="danger"
      />
    </div>
  );
}
