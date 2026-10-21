/**
 * Phase 233.2 — Webhook delivery history panel.
 *
 * Pins the following Requirements from
 * `openspec/changes/preprod01/specs/webhook-delivery-history-ui/spec.md`:
 *
 *   REQ-WH-UI-001  Detail-page panel mount + pagination + error view.
 *   REQ-WH-UI-002  FAILED-first default ordering + status filter.
 *   REQ-WH-UI-003  Per-row diagnostics + retry button (FAILED/DEAD_LETTER only).
 *   REQ-WH-UI-004  Expanded panel with PII-sanitised payload + response body.
 *   REQ-WH-UI-005  Service methods are typed + tested (lives in webhookService).
 *
 * No mocks; consumes the real `useWebhookDeliveries` + `useRetryWebhookDelivery`
 * hooks which call the backend WebhookViewSet.deliveries action +
 * WebhookDeliveryViewSet.retry_delivery action respectively.
 */

import { useMemo, useState } from 'react';
import { Button } from '../../../shared/components/Button';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import {
  useRetryWebhookDelivery,
  useWebhookDeliveries,
} from '../hooks/useWebhooks';
import {
  DeliveryStatus,
  type WebhookDelivery,
} from '../../../shared/types/webhooks';
import { redactAndPrettyPrint } from '../utils/redactPii';
import './WebhookDeliveryHistory.css';

const PAGE_SIZE = 25;
const URL_TRUNCATE_AT = 40;

// Failure-class statuses (REQ-WH-UI-002): rendered first when the
// "Failures first" pill is selected.
const FAILURE_STATUSES: ReadonlyArray<DeliveryStatus> = [
  DeliveryStatus.FAILED,
  DeliveryStatus.DEAD_LETTER,
  DeliveryStatus.RATE_LIMITED,
];

// REQ-WH-UI-003 Scenario 2 + 3: Retry button is hidden for SUCCESS (no need
// to retry) and RATE_LIMITED (rate-limited deliveries retry on the next
// minute boundary, not via manual retry).
const RETRYABLE_STATUSES: ReadonlySet<DeliveryStatus> = new Set([
  DeliveryStatus.FAILED,
  DeliveryStatus.DEAD_LETTER,
]);

type StatusFilter =
  | { kind: 'failures-first' } // default; shows failures first then successes
  | { kind: 'all' }
  | { kind: 'single'; status: DeliveryStatus };

interface WebhookDeliveryHistoryProps {
  webhookId: string;
}

export function WebhookDeliveryHistory({ webhookId }: WebhookDeliveryHistoryProps) {
  const [page, setPage] = useState(1);
  const [filter, setFilter] = useState<StatusFilter>({ kind: 'failures-first' });
  const [expandedId, setExpandedId] = useState<string | null>(null);

  // Translate the filter into the service-layer status[] (or undefined to
  // request all rows). For "failures-first" we still ask the server for ALL
  // statuses; the ordering is applied client-side after pagination.
  const apiStatusFilter: DeliveryStatus[] | undefined =
    filter.kind === 'single' ? [filter.status] : undefined;

  const query = useWebhookDeliveries(webhookId, {
    page,
    page_size: PAGE_SIZE,
    status: apiStatusFilter?.join(','),
  });
  const retryMutation = useRetryWebhookDelivery(webhookId);

  // Apply the FAILED-first ordering on top of the server response when the
  // active filter is "failures-first" (REQ-WH-UI-002 default).
  const orderedRows = useMemo<WebhookDelivery[]>(() => {
    const rows = query.data?.results ?? [];
    if (filter.kind !== 'failures-first') return rows;
    const failures = rows.filter((r) =>
      (FAILURE_STATUSES as ReadonlyArray<DeliveryStatus>).includes(r.status),
    );
    const successes = rows.filter(
      (r) => !(FAILURE_STATUSES as ReadonlyArray<DeliveryStatus>).includes(r.status),
    );
    return [...failures, ...successes];
  }, [query.data?.results, filter.kind]);

  const handleRetry = (delivery: WebhookDelivery) => {
    if (!RETRYABLE_STATUSES.has(delivery.status)) return;
    retryMutation.mutate(delivery.id);
  };

  if (query.error) {
    return (
      <ErrorDisplay
        error={query.error as Error}
        title="Failed to load delivery history"
        onRetry={() => query.refetch()}
      />
    );
  }

  return (
    <section
      className="webhook-delivery-history"
      data-testid="webhook-delivery-history"
      aria-label="Webhook delivery history"
    >
      <header className="webhook-delivery-history-header">
        <h2>Delivery history</h2>
        <FilterPills active={filter} onChange={(f) => { setFilter(f); setPage(1); }} />
      </header>

      {query.isLoading && <DeliveryHistorySkeleton />}

      {!query.isLoading && orderedRows.length === 0 && (
        <p
          className="webhook-delivery-empty"
          data-testid="webhook-delivery-history-empty"
        >
          No deliveries yet.
        </p>
      )}

      {!query.isLoading && orderedRows.length > 0 && (
        <table className="webhook-delivery-table" role="table">
          <thead>
            <tr>
              <th scope="col">Event</th>
              <th scope="col">Target</th>
              <th scope="col">Status</th>
              <th scope="col">Code</th>
              <th scope="col">Time</th>
              <th scope="col">Retries</th>
              <th scope="col" aria-label="Actions" />
            </tr>
          </thead>
          <tbody>
            {orderedRows.map((d) => (
              <DeliveryRow
                key={d.id}
                delivery={d}
                expanded={expandedId === d.id}
                onToggleExpand={() =>
                  setExpandedId(expandedId === d.id ? null : d.id)
                }
                onRetry={() => handleRetry(d)}
                isRetrying={retryMutation.isPending}
              />
            ))}
          </tbody>
        </table>
      )}

      {!query.isLoading && query.data && (
        <Pagination
          page={page}
          hasPrev={!!query.data.has_previous}
          hasNext={!!query.data.has_next}
          onChange={setPage}
        />
      )}
    </section>
  );
}

// ---------------------------------------------------------------------------
// FilterPills — the status filter (REQ-WH-UI-002).
// ---------------------------------------------------------------------------

interface FilterPillsProps {
  active: StatusFilter;
  onChange: (next: StatusFilter) => void;
}

function FilterPills({ active, onChange }: FilterPillsProps) {
  const isPillActive = (kind: StatusFilter['kind'], status?: DeliveryStatus) => {
    if (active.kind !== kind) return false;
    // Narrow on ``active.kind`` (not on the ``kind`` parameter): TypeScript's
    // discriminated-union narrowing keys off the discriminator field of the
    // value being narrowed. Comparing the parameter ``kind === 'single'``
    // does not narrow ``active``, so ``active.status`` would be a TS2339
    // error. Comparing ``active.kind`` does narrow it.
    if (active.kind === 'single') return active.status === status;
    return true;
  };

  return (
    <div className="webhook-delivery-filter-pills" role="tablist">
      <button
        type="button"
        role="tab"
        aria-selected={isPillActive('failures-first')}
        className={`pill ${isPillActive('failures-first') ? 'pill-active' : ''}`}
        onClick={() => onChange({ kind: 'failures-first' })}
      >
        Failures first
      </button>
      <button
        type="button"
        role="tab"
        aria-selected={isPillActive('all')}
        className={`pill ${isPillActive('all') ? 'pill-active' : ''}`}
        onClick={() => onChange({ kind: 'all' })}
      >
        All
      </button>
      {[
        DeliveryStatus.SUCCESS,
        DeliveryStatus.FAILED,
        DeliveryStatus.DEAD_LETTER,
        DeliveryStatus.RATE_LIMITED,
      ].map((s) => (
        <button
          key={s}
          type="button"
          role="tab"
          aria-selected={isPillActive('single', s)}
          className={`pill pill-${s.toLowerCase()} ${
            isPillActive('single', s) ? 'pill-active' : ''
          }`}
          onClick={() => onChange({ kind: 'single', status: s })}
        >
          {s.replace('_', ' ')}
        </button>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// DeliveryRow — single row + expandable panel (REQ-WH-UI-003 + 004).
// ---------------------------------------------------------------------------

interface DeliveryRowProps {
  delivery: WebhookDelivery;
  expanded: boolean;
  onToggleExpand: () => void;
  onRetry: () => void;
  isRetrying: boolean;
}

function DeliveryRow({
  delivery,
  expanded,
  onToggleExpand,
  onRetry,
  isRetrying,
}: DeliveryRowProps) {
  const truncatedTarget =
    (delivery.webhook_url ?? '').length > URL_TRUNCATE_AT
      ? `${(delivery.webhook_url ?? '').slice(0, URL_TRUNCATE_AT)}…`
      : delivery.webhook_url ?? '—';

  const responseTime = computeResponseTimeMs(delivery);
  const showRetry = RETRYABLE_STATUSES.has(delivery.status);

  return (
    <>
      <tr
        className="webhook-delivery-row"
        data-status={delivery.status}
        data-testid={`webhook-delivery-row-${delivery.id}`}
      >
        <td className="event">{delivery.event_type}</td>
        <td className="target" title={delivery.webhook_url ?? ''}>
          {truncatedTarget}
        </td>
        <td>
          <StatusPill status={delivery.status} />
        </td>
        <td>{delivery.http_status_code ?? '—'}</td>
        <td>{responseTime != null ? `${responseTime} ms` : '—'}</td>
        <td>{delivery.attempt_number}</td>
        <td className="actions">
          {showRetry && (
            <Button
              variant="secondary"
              size="sm"
              onClick={onRetry}
              loading={isRetrying}
              data-testid={`webhook-delivery-retry-${delivery.id}`}
            >
              Retry
            </Button>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={onToggleExpand}
            aria-expanded={expanded}
            aria-label={expanded ? 'Collapse delivery details' : 'Expand delivery details'}
            data-testid={`webhook-delivery-expand-${delivery.id}`}
          >
            {expanded ? '−' : '+'}
          </Button>
        </td>
      </tr>
      {expanded && (
        <tr className="webhook-delivery-expanded-row">
          <td colSpan={7}>
            <ExpandedPanel delivery={delivery} />
          </td>
        </tr>
      )}
    </>
  );
}

function computeResponseTimeMs(d: WebhookDelivery): number | null {
  // Backend doesn't yet expose `response_time_ms` directly. Derive it from
  // delivered_at - created_at when both are present (SUCCESS path); for
  // FAILED rows where delivered_at is null, return null and the row shows
  // "—" per REQ-WH-UI-003 contract.
  if (!d.delivered_at) return null;
  try {
    const created = new Date(d.created_at).getTime();
    const delivered = new Date(d.delivered_at).getTime();
    if (Number.isNaN(created) || Number.isNaN(delivered)) return null;
    const diff = delivered - created;
    return diff >= 0 ? diff : null;
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// StatusPill — small colour-coded status indicator.
// ---------------------------------------------------------------------------

function StatusPill({ status }: { status: DeliveryStatus }) {
  return (
    <span
      className={`webhook-status-pill webhook-status-pill-${status.toLowerCase()}`}
      data-status={status}
    >
      {status.replace('_', ' ')}
    </span>
  );
}

// ---------------------------------------------------------------------------
// ExpandedPanel — PII-sanitised payload + response body (REQ-WH-UI-004).
// ---------------------------------------------------------------------------

function ExpandedPanel({ delivery }: { delivery: WebhookDelivery }) {
  const requestPayload = useMemo(
    () => redactAndPrettyPrint(delivery.payload),
    [delivery.payload],
  );
  const responseBody = useMemo(
    () => redactAndPrettyPrint(delivery.response_body ?? ''),
    [delivery.response_body],
  );

  return (
    <div
      className="webhook-delivery-expanded-panel"
      data-testid={`webhook-delivery-expanded-${delivery.id}`}
    >
      <dl className="webhook-delivery-expanded-meta">
        <dt>Full URL</dt>
        <dd>{delivery.webhook_url ?? '—'}</dd>
        <dt>Created at</dt>
        <dd>{new Date(delivery.created_at).toLocaleString()}</dd>
        {delivery.delivered_at && (
          <>
            <dt>Delivered at</dt>
            <dd>{new Date(delivery.delivered_at).toLocaleString()}</dd>
          </>
        )}
        {delivery.error_message && (
          <>
            <dt>Error</dt>
            <dd className="webhook-delivery-error">{delivery.error_message}</dd>
          </>
        )}
        {delivery.signing_key_uuid && (
          <>
            <dt>Signing key</dt>
            <dd>
              <code>{delivery.signing_key_uuid}</code>
            </dd>
          </>
        )}
      </dl>
      <h3>Request payload (PII redacted)</h3>
      <pre
        className="webhook-delivery-payload"
        data-testid="webhook-delivery-payload-pre"
      >
        {requestPayload}
      </pre>
      <h3>Response body (PII redacted)</h3>
      <pre
        className="webhook-delivery-response"
        data-testid="webhook-delivery-response-pre"
      >
        {responseBody || '—'}
      </pre>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Pagination — minimal prev/next.
// ---------------------------------------------------------------------------

interface PaginationProps {
  page: number;
  hasPrev: boolean;
  hasNext: boolean;
  onChange: (next: number) => void;
}

function Pagination({ page, hasPrev, hasNext, onChange }: PaginationProps) {
  return (
    <nav className="webhook-delivery-pagination" aria-label="Delivery history pagination">
      <Button
        variant="ghost"
        size="sm"
        onClick={() => onChange(page - 1)}
        disabled={!hasPrev}
      >
        ← Previous
      </Button>
      <span className="webhook-delivery-pagination-page">Page {page}</span>
      <Button
        variant="ghost"
        size="sm"
        onClick={() => onChange(page + 1)}
        disabled={!hasNext}
        data-testid="webhook-delivery-next-page"
      >
        Next →
      </Button>
    </nav>
  );
}

// ---------------------------------------------------------------------------
// Skeleton — minimal loading state (matches the platform's skeleton style).
// ---------------------------------------------------------------------------

function DeliveryHistorySkeleton() {
  return (
    <div
      className="webhook-delivery-skeleton"
      data-testid="webhook-delivery-history-loading"
      aria-busy="true"
    >
      {[0, 1, 2].map((i) => (
        <div key={i} className="webhook-delivery-skeleton-row" />
      ))}
    </div>
  );
}
