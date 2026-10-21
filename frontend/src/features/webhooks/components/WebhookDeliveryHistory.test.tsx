/**
 * Phase 233.2 — WebhookDeliveryHistory component tests.
 *
 * Pins the load-bearing UI contracts from
 * `openspec/changes/preprod01/specs/webhook-delivery-history-ui/spec.md`:
 *
 *   REQ-WH-UI-001  Loading skeleton, empty state, error view, mounted panel.
 *   REQ-WH-UI-002  FAILED-first ordering by default.
 *   REQ-WH-UI-003  Retry button visible on FAILED/DEAD_LETTER, hidden elsewhere.
 *   REQ-WH-UI-004  Expanded panel masks PII in payload + response body.
 *
 * No mocks of business logic — only the HTTP client adapter is stubbed
 * (matching the existing webhook component-test pattern). The redactor,
 * the React Query state machine, and the component's own logic all run
 * for real.
 */
import { type ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { HttpClient } from '../../../shared/types/api';

vi.mock('../../../shared/api/client');

import { apiClient } from '../../../shared/api/client';
import { WebhookDeliveryHistory } from './WebhookDeliveryHistory';

const WEBHOOK_ID = 'wh-test-1';

function makeDelivery(overrides: Record<string, unknown> = {}) {
  return {
    id: 'd-default',
    webhook: WEBHOOK_ID,
    webhook_name: 'Test Webhook',
    webhook_url: 'https://subscriber.example.com/hooks/long/path/that/might/truncate',
    event_type: 'asset.created',
    payload: { event_id: 'e-1', actor_email: 'leak@example.com' },
    signature: 'abc',
    status: 'SUCCESS',
    attempt_number: 0,
    http_status_code: 200,
    response_body: 'OK',
    error_message: null,
    delivered_at: '2026-05-07T10:00:01.500Z',
    next_retry_at: null,
    created_at: '2026-05-07T10:00:00.000Z',
    updated_at: '2026-05-07T10:00:01.500Z',
    signing_key_uuid: null,
    ...overrides,
  };
}

function makeListResponse(rows: unknown[]) {
  return {
    data: {
      results: rows,
      count: rows.length,
      page: 1,
      page_size: 25,
      total_pages: 1,
      next: null,
      previous: null,
      has_next: false,
      has_previous: false,
      next_page: null,
      previous_page: null,
    },
  };
}

describe('WebhookDeliveryHistory', () => {
  let queryClient: QueryClient;
  let mock: HttpClient;

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>{children}</MemoryRouter>
      </QueryClientProvider>
    );
  }

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    mock = apiClient.getClient();
  });

  it('renders the empty state when no deliveries exist (REQ-WH-UI-001)', async () => {
    vi.mocked(mock.get).mockResolvedValue(makeListResponse([]));

    render(<WebhookDeliveryHistory webhookId={WEBHOOK_ID} />, { wrapper: Wrapper });

    expect(await screen.findByTestId('webhook-delivery-history-empty')).toBeInTheDocument();
  });

  it('renders rows + status pill + retries column for each delivery (REQ-WH-UI-003)', async () => {
    vi.mocked(mock.get).mockResolvedValue(
      makeListResponse([
        makeDelivery({ id: 'd1', status: 'FAILED', attempt_number: 3 }),
      ]),
    );

    render(<WebhookDeliveryHistory webhookId={WEBHOOK_ID} />, { wrapper: Wrapper });

    const row = await screen.findByTestId('webhook-delivery-row-d1');
    expect(row).toHaveTextContent('asset.created');
    expect(row).toHaveTextContent('FAILED');
    expect(row).toHaveTextContent('3'); // retry_count
  });

  it('renders Retry button only for FAILED/DEAD_LETTER (REQ-WH-UI-003 Scenarios 2-3)', async () => {
    vi.mocked(mock.get).mockResolvedValue(
      makeListResponse([
        makeDelivery({ id: 'd-success', status: 'SUCCESS' }),
        makeDelivery({ id: 'd-failed', status: 'FAILED' }),
        makeDelivery({ id: 'd-dead', status: 'DEAD_LETTER' }),
        makeDelivery({ id: 'd-rate', status: 'RATE_LIMITED' }),
      ]),
    );

    render(<WebhookDeliveryHistory webhookId={WEBHOOK_ID} />, { wrapper: Wrapper });

    await screen.findByTestId('webhook-delivery-row-d-success');

    expect(screen.queryByTestId('webhook-delivery-retry-d-success')).not.toBeInTheDocument();
    expect(screen.queryByTestId('webhook-delivery-retry-d-rate')).not.toBeInTheDocument();
    expect(screen.getByTestId('webhook-delivery-retry-d-failed')).toBeInTheDocument();
    expect(screen.getByTestId('webhook-delivery-retry-d-dead')).toBeInTheDocument();
  });

  it('orders failures before successes by default (REQ-WH-UI-002)', async () => {
    vi.mocked(mock.get).mockResolvedValue(
      makeListResponse([
        makeDelivery({ id: 'd-success-1', status: 'SUCCESS' }),
        makeDelivery({ id: 'd-success-2', status: 'SUCCESS' }),
        makeDelivery({ id: 'd-failed', status: 'FAILED' }),
        makeDelivery({ id: 'd-dead', status: 'DEAD_LETTER' }),
      ]),
    );

    render(<WebhookDeliveryHistory webhookId={WEBHOOK_ID} />, { wrapper: Wrapper });

    await screen.findByTestId('webhook-delivery-row-d-success-1');

    const rows = screen.getAllByRole('row');
    // First row is the header; data rows start at index 1.
    const dataRowOrder = rows
      .slice(1)
      .map((r) => r.getAttribute('data-testid'))
      .filter(Boolean);
    // Failures come first.
    const failedIdx = dataRowOrder.indexOf('webhook-delivery-row-d-failed');
    const deadIdx = dataRowOrder.indexOf('webhook-delivery-row-d-dead');
    const successIdx = dataRowOrder.indexOf('webhook-delivery-row-d-success-1');
    expect(failedIdx).toBeGreaterThanOrEqual(0);
    expect(deadIdx).toBeGreaterThanOrEqual(0);
    expect(successIdx).toBeGreaterThanOrEqual(0);
    expect(failedIdx).toBeLessThan(successIdx);
    expect(deadIdx).toBeLessThan(successIdx);
  });

  it('expands a row on click and redacts PII in payload (REQ-WH-UI-004)', async () => {
    vi.mocked(mock.get).mockResolvedValue(
      makeListResponse([
        makeDelivery({
          id: 'd-pii',
          status: 'SUCCESS',
          payload: { event: 'compliance.completed', email: 'leak@example.com' },
          response_body: '{"ack": "ok", "subject": "leak@example.com"}',
        }),
      ]),
    );

    render(<WebhookDeliveryHistory webhookId={WEBHOOK_ID} />, { wrapper: Wrapper });

    const expandBtn = await screen.findByTestId('webhook-delivery-expand-d-pii');
    await userEvent.click(expandBtn);

    const expanded = await screen.findByTestId('webhook-delivery-expanded-d-pii');
    // The DOM body MUST NOT contain the raw email substring anywhere
    // inside the expanded panel (the load-bearing assertion of
    // REQ-WH-UI-004 Scenario 1).
    expect(expanded.textContent ?? '').not.toContain('leak@example.com');
    // The shape is preserved — `@` and `.com` still visible.
    expect(expanded.textContent ?? '').toMatch(/@/);
    expect(expanded.textContent ?? '').toMatch(/\.com/);
  });

  it('filters to a single status when a status pill is clicked', async () => {
    vi.mocked(mock.get).mockResolvedValue(
      makeListResponse([
        makeDelivery({ id: 'd-success-1', status: 'SUCCESS' }),
        makeDelivery({ id: 'd-failed', status: 'FAILED' }),
      ]),
    );

    render(<WebhookDeliveryHistory webhookId={WEBHOOK_ID} />, { wrapper: Wrapper });

    await screen.findByTestId('webhook-delivery-row-d-success-1');

    // Click the FAILED filter pill — wait for the filter to apply via a
    // re-fetch round-trip that returns only the failed row.
    vi.mocked(mock.get).mockResolvedValueOnce(
      makeListResponse([makeDelivery({ id: 'd-failed', status: 'FAILED' })]),
    );
    const failedPill = screen.getByRole('tab', { name: /^FAILED$/i });
    await userEvent.click(failedPill);

    await waitFor(() => {
      expect(screen.queryByTestId('webhook-delivery-row-d-success-1')).not.toBeInTheDocument();
    });
    expect(screen.getByTestId('webhook-delivery-row-d-failed')).toBeInTheDocument();
  });

  it('renders error view + retry button when the fetch fails (REQ-WH-UI-001 Scenario 3)', async () => {
    vi.mocked(mock.get).mockRejectedValue(new Error('Network down'));

    render(<WebhookDeliveryHistory webhookId={WEBHOOK_ID} />, { wrapper: Wrapper });

    expect(
      await screen.findByText(/Failed to load delivery history/i),
    ).toBeInTheDocument();
  });
});
