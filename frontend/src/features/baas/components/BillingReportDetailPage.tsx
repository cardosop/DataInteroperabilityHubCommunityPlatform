/**
 * Billing Report Detail Page — Phase 116C.3
 * Shows report details with finalize/send/void actions.
 */

import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  useBillingReport,
  useFinalizeBillingReport,
  useSendBillingReport,
  useVoidBillingReport,
} from '../hooks/useBaaS';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { BillingReportStatus } from '../../../shared/types/baas';
import { Button } from '../../../shared/components/Button';
import { ConfirmDialog } from '../../../shared/components/ConfirmDialog';
import { InvoicePreview } from './InvoicePreview';
import { statusBadgeClass } from './billingUtils';

type ConfirmAction = 'send' | 'void' | null;

export function BillingReportDetailPage() {
  const { reportId } = useParams<{ reportId: string }>();
  const navigate = useNavigate();
  const { data: report, isLoading, error, refetch } = useBillingReport(reportId || null);
  const finalizeMutation = useFinalizeBillingReport();
  const sendMutation = useSendBillingReport();
  const voidMutation = useVoidBillingReport();
  const [confirmAction, setConfirmAction] = useState<ConfirmAction>(null);

  if (isLoading) return <LoadingSpinner message="Loading report..." />;
  if (error) return <ErrorDisplay error={error} title="Failed to load report" />;
  if (!report) return <ErrorDisplay error={new Error('Report not found')} title="Not found" />;

  const handleFinalize = async () => {
    await finalizeMutation.mutateAsync(report.id);
    refetch();
  };
  const handleSendConfirm = async () => {
    setConfirmAction(null);
    await sendMutation.mutateAsync(report.id);
    refetch();
  };
  const handleVoidConfirm = async () => {
    setConfirmAction(null);
    await voidMutation.mutateAsync({ id: report.id, reason: 'Voided from UI' });
    refetch();
  };

  return (
    <div className="billing-report-detail-page">
      <Button variant="secondary" onClick={() => navigate('/settings/baas')}>
        Back
      </Button>

      <div className="report-header">
        <h2>Billing Report</h2>
        <span className={statusBadgeClass(report.status)}>{report.status}</span>
      </div>

      <div className="report-meta-grid">
        <div className="meta-item">
          <label>Customer</label>
          <span>{report.customer_name || '—'}</span>
        </div>
        <div className="meta-item">
          <label>Customer ID</label>
          <span><code>{report.customer_id}</code></span>
        </div>
        <div className="meta-item">
          <label>Email</label>
          <span>{report.customer_email || '—'}</span>
        </div>
        <div className="meta-item">
          <label>Period</label>
          <span>
            {new Date(report.period_start).toLocaleDateString()} –{' '}
            {new Date(report.period_end).toLocaleDateString()}
          </span>
        </div>
        <div className="meta-item">
          <label>Created</label>
          <span>{new Date(report.created_at).toLocaleString()}</span>
        </div>
        {report.finalized_at && (
          <div className="meta-item">
            <label>Finalized</label>
            <span>{new Date(report.finalized_at).toLocaleString()}</span>
          </div>
        )}
        {report.sent_at && (
          <div className="meta-item">
            <label>Sent</label>
            <span>{new Date(report.sent_at).toLocaleString()}</span>
          </div>
        )}
      </div>

      {/* Invoice preview */}
      <InvoicePreview report={report} />

      {/* Actions */}
      <div className="report-actions">
        {report.status === BillingReportStatus.DRAFT && (
          <>
            <Button
              variant="primary"
              onClick={handleFinalize}
              loading={finalizeMutation.isPending}
            >
              Finalize
            </Button>
            <Button
              variant="danger"
              onClick={() => setConfirmAction('void')}
              loading={voidMutation.isPending}
            >
              Void
            </Button>
          </>
        )}
        {report.status === BillingReportStatus.FINALIZED && (
          <>
            <Button
              variant="primary"
              onClick={() => setConfirmAction('send')}
              loading={sendMutation.isPending}
            >
              Send to Customer
            </Button>
            <Button
              variant="danger"
              onClick={() => setConfirmAction('void')}
              loading={voidMutation.isPending}
            >
              Void
            </Button>
          </>
        )}
      </div>

      <ConfirmDialog
        isOpen={confirmAction === 'send'}
        onClose={() => setConfirmAction(null)}
        onConfirm={handleSendConfirm}
        title="Send billing report"
        message={`Send this billing report (${report.total_amount} ${report.currency}) to ${report.customer_email || 'the customer'}? This will generate a PDF invoice and email it.`}
        confirmLabel="Send"
        variant="info"
      />

      <ConfirmDialog
        isOpen={confirmAction === 'void'}
        onClose={() => setConfirmAction(null)}
        onConfirm={handleVoidConfirm}
        title="Void billing report"
        message="Are you sure you want to void this billing report? This action cannot be undone."
        confirmLabel="Void Report"
        variant="danger"
      />
    </div>
  );
}
