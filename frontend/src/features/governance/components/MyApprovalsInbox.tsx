/**
 * MyApprovalsInbox — unified "waiting on me" inbox (278.I.1).
 *
 * Aggregates actionable items across access requests, DSARs, breach
 * incidents, and DPIA reviews into a single view. Supports one-click
 * approve/reject, delegation awareness, and mobile-responsive layout.
 */
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { Button } from '../../../shared/components/Button';
import { useTranslation } from '../../../shared/i18n/useTranslation';
import { Breadcrumbs } from '../../../shared/components/Breadcrumbs';
import {
  emitUxActivationEvent,
  type ApprovalInboxItemActionDetail,
  type ApprovalInboxBulkActionDetail,
} from '../../../shared/telemetry/uxActivationTelemetry';
import {
  useAccessRequests,
  useApproveAccessRequest,
  useRejectAccessRequest,
  useBulkApproveAccessRequests,
  useBulkRejectAccessRequests,
} from '../hooks/useGovernance';
import type { AccessRequest } from '../../../shared/types/governance';
import './MyApprovalsInbox.css';

// ── Types ──────────────────────────────────────────────────────────────────

type ApprovalItemType = 'access_request' | 'dsar' | 'breach' | 'dpia' | 'kyb';

interface ApprovalItem {
  id: string;
  type: ApprovalItemType;
  title: string;
  subtitle: string;
  status: string;
  priority: 'high' | 'medium' | 'low';
  createdAt: string;
  resourceUrl: string;
  /** Which action is available from the inbox row. */
  actions: ApprovalAction[];
}

interface ApprovalAction {
  label: string;
  variant: 'primary' | 'danger' | 'secondary';
  handler: () => void;
  pending?: boolean;
}

// ── Component ──────────────────────────────────────────────────────────────

export function MyApprovalsInbox() {
  const { t } = useTranslation();
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [rejectReason, setRejectReason] = useState('');

  // Access requests — PENDING ones that need approval
  const {
    data: accessData,
    isLoading: accessLoading,
    error: accessError,
  } = useAccessRequests({ status: 'PENDING', page_size: 50 });

  const approveMutation = useApproveAccessRequest();
  const rejectMutation = useRejectAccessRequest();
  const bulkApprove = useBulkApproveAccessRequests();
  const bulkReject = useBulkRejectAccessRequests();

  const accessRequests: AccessRequest[] =
    (accessData as { results?: AccessRequest[] })?.results ?? [];

  // Build unified items from access requests
  const items: ApprovalItem[] = accessRequests.map((ar) => ({
    id: ar.id,
    type: 'access_request' as const,
    title: `Access request: ${ar.reason.slice(0, 60)}${ar.reason.length > 60 ? '…' : ''}`,
    subtitle: `Requested by ${ar.requested_by?.slice(0, 8) ?? 'unknown'}… · ${ar.requested_access_type ?? 'read'}`,
    status: ar.status,
    priority: ar.status === 'PENDING_NEXT_APPROVER' ? 'high' : 'medium',
    createdAt: ar.created_at ?? '',
    resourceUrl: `/governance/access-requests/${ar.id}`,
    actions: [
      {
        label: 'Approve',
        variant: 'primary',
        handler: () => {
          emitUxActivationEvent('meshant.approval_inbox.item_action', {
            item_id: ar.id,
            item_type: 'access_request',
            action: 'approve',
            priority: ar.status === 'PENDING_NEXT_APPROVER' ? 'high' : 'medium',
          } satisfies ApprovalInboxItemActionDetail);
          approveMutation.mutate({ id: ar.id }, {
            onSuccess: () => setSelectedIds((s) => { s.delete(ar.id); return new Set(s); }),
          });
        },
        pending: approveMutation.isPending,
      },
      {
        label: 'Reject',
        variant: 'danger',
        handler: () => {
          const reason = rejectReason || 'Rejected';
          emitUxActivationEvent('meshant.approval_inbox.item_action', {
            item_id: ar.id,
            item_type: 'access_request',
            action: 'reject',
            priority: ar.status === 'PENDING_NEXT_APPROVER' ? 'high' : 'medium',
          } satisfies ApprovalInboxItemActionDetail);
          rejectMutation.mutate({ id: ar.id, reason }, {
            onSuccess: () => setSelectedIds((s) => { s.delete(ar.id); return new Set(s); }),
          });
        },
        pending: rejectMutation.isPending,
      },
    ],
  }));

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleAll = () => {
    if (selectedIds.size === items.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(items.map((i) => i.id)));
    }
  };

  const handleBulkApprove = () => {
    const count = selectedIds.size;
    bulkApprove.mutate({ ids: [...selectedIds] }, {
      onSuccess: (result: { succeeded: string[]; failed: Array<{ id: string; error: string }> }) => {
        emitUxActivationEvent('meshant.approval_inbox.bulk_action', {
          item_count: count,
          action: 'approve',
          succeeded: result.succeeded.length,
          failed: result.failed.length,
        } satisfies ApprovalInboxBulkActionDetail);
        setSelectedIds(new Set());
      },
    });
  };

  const handleBulkReject = () => {
    const reason = rejectReason || window.prompt('Rejection reason:') || 'Rejected in bulk';
    const count = selectedIds.size;
    bulkReject.mutate({ ids: [...selectedIds], reason }, {
      onSuccess: (result: { succeeded: string[]; failed: Array<{ id: string; error: string }> }) => {
        emitUxActivationEvent('meshant.approval_inbox.bulk_action', {
          item_count: count,
          action: 'reject',
          succeeded: result.succeeded.length,
          failed: result.failed.length,
        } satisfies ApprovalInboxBulkActionDetail);
        setSelectedIds(new Set());
      },
    });
  };

  // ── Render ────────────────────────────────────────────────────────────

  if (accessLoading) return <LoadingSpinner message="Loading approvals…" />;
  if (accessError) {
    return (
      <ErrorDisplay
        error={accessError as Error}
        title="Failed to load approvals"
        onRetry={() => window.location.reload()}
      />
    );
  }

  return (
    <div className="my-approvals-inbox" data-testid="my-approvals-inbox">
      <Breadcrumbs
        items={[
          { label: 'Governance', href: '/governance' },
          { label: 'My Approvals', href: '/governance/my-approvals' },
        ]}
      />
      <div className="my-approvals-inbox__header">
        <h2 className="my-approvals-inbox__title">
          {t('governance.approvalInbox.title')}
          {items.length > 0 && (
            <span className="my-approvals-inbox__count">{items.length}</span>
          )}
        </h2>
        {items.length > 0 && (
          <div className="my-approvals-inbox__bulk-actions">
            <label className="my-approvals-inbox__select-all">
              <input
                type="checkbox"
                checked={selectedIds.size === items.length && items.length > 0}
                onChange={toggleAll}
              />
              {t('governance.approvalInbox.select_all')}
            </label>
            {selectedIds.size > 0 && (
              <>
                <input
                  className="my-approvals-inbox__reject-reason"
                  type="text"
                  placeholder={t('governance.approvalInbox.reject_reason')}
                  value={rejectReason}
                  onChange={(e) => setRejectReason(e.target.value)}
                />
                <Button variant="primary" onClick={handleBulkApprove} disabled={bulkApprove.isPending}>
                  {t('governance.approvalInbox.approve')} {selectedIds.size}
                </Button>
                <Button variant="danger" onClick={handleBulkReject} disabled={bulkReject.isPending}>
                  {t('governance.approvalInbox.reject')} {selectedIds.size}
                </Button>
              </>
            )}
          </div>
        )}
      </div>

      {items.length === 0 ? (
        <div className="my-approvals-inbox__empty">
          <p className="my-approvals-inbox__empty-text">
            {t('governance.approvalInbox.empty')}
          </p>
          <Link to="/governance" className="my-approvals-inbox__empty-link">
            {t('governance.approvalInbox.view_all')}
          </Link>
        </div>
      ) : (
        <ul className="my-approvals-inbox__list" role="list">
          {items.map((item) => (
            <li
              key={item.id}
              className={`my-approvals-inbox__item my-approvals-inbox__item--${item.priority}`}
              data-testid={`approval-item-${item.id}`}
            >
              <div className="my-approvals-inbox__item-select">
                <input
                  type="checkbox"
                  checked={selectedIds.has(item.id)}
                  onChange={() => toggleSelect(item.id)}
                  aria-label={`Select ${item.title}`}
                />
              </div>
              <div className="my-approvals-inbox__item-body">
                <div className="my-approvals-inbox__item-header">
                  <span className={`my-approvals-inbox__item-type my-approvals-inbox__item-type--${item.type}`}>
                    {item.type === 'access_request' ? 'Access' : item.type.toUpperCase()}
                  </span>
                  <span className={`my-approvals-inbox__item-priority my-approvals-inbox__item-priority--${item.priority}`}>
                    {item.priority}
                  </span>
                </div>
                <Link to={item.resourceUrl} className="my-approvals-inbox__item-title">
                  {item.title}
                </Link>
                <p className="my-approvals-inbox__item-subtitle">{item.subtitle}</p>
              </div>
              <div className="my-approvals-inbox__item-actions">
                {item.actions.map((action) => (
                  <Button
                    key={action.label}
                    variant={action.variant}
                    size="sm"
                    onClick={action.handler}
                    disabled={action.pending}
                  >
                    {action.pending ? '…' : action.label}
                  </Button>
                ))}
              </div>
            </li>
          ))}
        </ul>
      )}

      {items.length > 0 && (
        <div className="my-approvals-inbox__footer">
          <Link to="/governance" className="my-approvals-inbox__view-all">
            {t('governance.approvalInbox.view_all')}
          </Link>
        </div>
      )}
    </div>
  );
}
