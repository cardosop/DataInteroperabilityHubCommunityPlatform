/**
 * AlertingRuleManager tests — Phase 240.4.A.12.
 *
 * Covers: role-gating (non-admin → blocked), list rendering, create
 * happy path with field-level validation, edit, delete-confirm.
 */
import { type ReactNode } from 'react';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { HttpClient } from '../../../shared/types/api';

vi.mock('../../../shared/api/client');

import { apiClient } from '../../../shared/api/client';
import { useAuthStore } from '../../auth/store/authStore';
import { AlertingRuleManager } from './AlertingRuleManager';

function setUserRoles(roles: string[]) {
  // useAuthStore is a Zustand store — we can call setState directly.
  useAuthStore.setState({
    user: { id: 'u-1', email: 'admin@test', roles } as never,
  });
}

describe('AlertingRuleManager', () => {
  let queryClient: QueryClient;
  let mock: HttpClient;

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <RouterProvider
          router={createMemoryRouter([{ path: '/', element: children }], { initialEntries: ['/'] })}
        />
      </QueryClientProvider>
    );
  }

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    mock = apiClient.getClient();
    vi.mocked(mock.get).mockResolvedValue({
      data: {
        count: 0,
        results: [],
        page: 1,
        page_size: 20,
        total_pages: 0,
        has_next: false,
        has_previous: false,
      },
    });
    setUserRoles(['TENANT_ADMIN']);
  });

  it('blocks non-admin viewers with a tenant-admin-required notice', async () => {
    setUserRoles(['DATA_PROVIDER']);
    render(<AlertingRuleManager />, { wrapper: Wrapper });
    expect(
      await screen.findByText(/tenant admin access required/i),
    ).toBeTruthy();
  });

  it('renders list view + new-rule button for tenant admins', async () => {
    render(<AlertingRuleManager />, { wrapper: Wrapper });
    expect(
      await screen.findByRole('heading', { name: /alerting rules/i }),
    ).toBeTruthy();
    expect(screen.getByTestId('rule-new-btn')).toBeTruthy();
  });

  it('shows the create form when "New rule" is clicked', async () => {
    render(<AlertingRuleManager />, { wrapper: Wrapper });
    fireEvent.click(await screen.findByTestId('rule-new-btn'));
    expect(await screen.findByTestId('rule-form')).toBeTruthy();
    // EMAIL is selected by default → the ``emails`` channel-config field
    // (labelled "Recipients") should appear.
    expect(screen.getByLabelText(/recipients/i)).toBeTruthy();
  });

  it('blocks submit when threshold is missing or non-numeric', async () => {
    render(<AlertingRuleManager />, { wrapper: Wrapper });
    fireEvent.click(await screen.findByTestId('rule-new-btn'));
    fireEvent.change(screen.getByLabelText(/^name/i), {
      target: { value: 'Quality drop' },
    });
    fireEvent.change(screen.getByLabelText(/recipients/i), {
      target: { value: 'oncall@example.com' },
    });
    // threshold left blank → validate() should reject.
    fireEvent.submit(screen.getByTestId('rule-form'));
    expect(await screen.findByTestId('rule-form-error')).toBeTruthy();
    expect(mock.post).not.toHaveBeenCalled();
  });

  it('posts a create payload when the form is fully valid', async () => {
    vi.mocked(mock.post).mockResolvedValue({
      data: {
        id: 'rule-1',
        tenant: 't-1',
        name: 'Quality drop',
        description: '',
        metric_type: 'quality_score',
        threshold: 80,
        comparison_operator: '<',
        severity: 'MEDIUM',
        alert_channels: ['EMAIL'],
        // Backend canonical shape: the read serializer omits
        // channel_config entirely; this mock mirrors the create response.
        channel_config: { emails: ['oncall@example.com'] },
        enabled: true,
        created_at: '2026-05-01T00:00:00Z',
        updated_at: '2026-05-01T00:00:00Z',
      },
    });
    render(<AlertingRuleManager />, { wrapper: Wrapper });
    fireEvent.click(await screen.findByTestId('rule-new-btn'));
    fireEvent.change(screen.getByLabelText(/^name/i), {
      target: { value: 'Quality drop' },
    });
    fireEvent.change(screen.getByLabelText(/^threshold/i), {
      target: { value: '80' },
    });
    fireEvent.change(screen.getByLabelText(/recipients/i), {
      target: { value: 'oncall@example.com' },
    });
    fireEvent.submit(screen.getByTestId('rule-form'));
    await waitFor(() => {
      expect(mock.post).toHaveBeenCalled();
    });
    const [calledPath, body] = vi.mocked(mock.post).mock.calls[0] as [
      string,
      Record<string, unknown>,
    ];
    expect(calledPath).toContain('dq/alerting-rules/');
    expect(body.threshold).toBe(80);
    expect(body.alert_channels).toEqual(['EMAIL']);
    // Backend contract: EMAIL channel_config uses ``emails`` (list), NOT
    // ``recipients`` — the old key 400'd every create (b7 E2E).
    expect(body.channel_config).toEqual({ emails: ['oncall@example.com'] });
  });

  it('splits comma-separated recipients into the emails list', async () => {
    render(<AlertingRuleManager />, { wrapper: Wrapper });
    fireEvent.click(await screen.findByTestId('rule-new-btn'));
    fireEvent.change(screen.getByLabelText(/^name/i), {
      target: { value: 'Quality drop' },
    });
    fireEvent.change(screen.getByLabelText(/^threshold/i), {
      target: { value: '80' },
    });
    fireEvent.change(screen.getByLabelText(/recipients/i), {
      target: { value: 'ops@example.com, oncall@example.com' },
    });
    fireEvent.submit(screen.getByTestId('rule-form'));
    await waitFor(() => {
      expect(mock.post).toHaveBeenCalled();
    });
    const [, body] = vi.mocked(mock.post).mock.calls[0] as [
      string,
      Record<string, unknown>,
    ];
    expect(body.channel_config).toEqual({
      emails: ['ops@example.com', 'oncall@example.com'],
    });
  });

  it('maps every channel to its backend channel_config key', async () => {
    render(<AlertingRuleManager />, { wrapper: Wrapper });
    fireEvent.click(await screen.findByTestId('rule-new-btn'));

    // Swap EMAIL for SLACK + WEBHOOK + PAGERDUTY: the form must send
    // webhook_url / url / integration_key — the keys
    // DQAlertingRule.clean() and the delivery clients consume.
    const email = screen.getByRole('checkbox', { name: /email/i });
    fireEvent.click(email);
    for (const channel of ['SLACK', 'WEBHOOK', 'PAGERDUTY']) {
      fireEvent.click(screen.getByRole('checkbox', { name: new RegExp(channel, 'i') }));
    }
    fireEvent.change(screen.getByLabelText(/^name/i), {
      target: { value: 'Multi-channel' },
    });
    fireEvent.change(screen.getByLabelText(/^threshold/i), {
      target: { value: '90' },
    });
    // Two fields share the "Webhook URL" label (SLACK + WEBHOOK) — index
    // them: [0] = SLACK webhook_url, [1] = WEBHOOK url.
    const webhookInputs = screen.getAllByLabelText(/^webhook url/i);
    fireEvent.change(webhookInputs[0], {
      target: { value: 'https://hooks.slack.com/x' },
    });
    fireEvent.change(webhookInputs[1], {
      target: { value: 'https://partner.example.com/dq' },
    });
    fireEvent.change(screen.getByLabelText(/^integration key/i), {
      target: { value: 'pd-int-key-1234' },
    });
    fireEvent.submit(screen.getByTestId('rule-form'));
    await waitFor(() => {
      expect(mock.post).toHaveBeenCalled();
    });
    const [, body] = vi.mocked(mock.post).mock.calls[0] as [
      string,
      Record<string, unknown>,
    ];
    expect(body.alert_channels).toEqual(['SLACK', 'WEBHOOK', 'PAGERDUTY']);
    expect(body.channel_config).toEqual({
      webhook_url: 'https://hooks.slack.com/x',
      url: 'https://partner.example.com/dq',
      integration_key: 'pd-int-key-1234',
    });
  });

  it('surfaces the backend message when create is rejected', async () => {
    vi.mocked(mock.post).mockRejectedValue({
      error: {
        code: 'VALIDATION_ERROR',
        message: "EMAIL channel requires 'emails' in channel_config",
        http_status: 400,
        request_id: 'req-1',
        timestamp: '2026-05-01T00:00:00Z',
        details: { error: "EMAIL channel requires 'emails' in channel_config" },
      },
    });
    render(<AlertingRuleManager />, { wrapper: Wrapper });
    fireEvent.click(await screen.findByTestId('rule-new-btn'));
    fireEvent.change(screen.getByLabelText(/^name/i), {
      target: { value: 'Quality drop' },
    });
    fireEvent.change(screen.getByLabelText(/^threshold/i), {
      target: { value: '80' },
    });
    fireEvent.change(screen.getByLabelText(/recipients/i), {
      target: { value: 'oncall@example.com' },
    });
    fireEvent.submit(screen.getByTestId('rule-form'));
    expect(
      await screen.findByText(/EMAIL channel requires 'emails'/i),
    ).toBeTruthy();
    // The form stays open so the user can correct the payload.
    expect(screen.getByTestId('rule-form')).toBeTruthy();
  });

  it('opens the edit form even when the API omits channel_config', async () => {
    vi.mocked(mock.get).mockResolvedValue({
      data: {
        count: 1,
        results: [
          {
            id: 'rule-1',
            tenant: 't-1',
            name: 'Quality drop',
            description: '',
            metric_type: 'quality_score',
            threshold: 80,
            comparison_operator: '<',
            severity: 'MEDIUM',
            alert_channels: ['EMAIL'],
            enabled: true,
            created_at: '2026-05-01T00:00:00Z',
            updated_at: '2026-05-01T00:00:00Z',
            // No channel_config — the read serializer omits it because
            // the stored value is encrypted.
          },
        ],
        page: 1,
        page_size: 20,
        total_pages: 1,
        has_next: false,
        has_previous: false,
      },
    });
    render(<AlertingRuleManager />, { wrapper: Wrapper });
    await screen.findByTestId('rule-row-rule-1');
    fireEvent.click(screen.getByTestId('rule-edit-rule-1'));
    // No TypeError from Object.entries(undefined); form renders with the
    // required channel-config input empty.
    expect(await screen.findByTestId('rule-form')).toBeTruthy();
    expect((screen.getByLabelText(/recipients/i) as HTMLInputElement).value).toBe('');
  });

  it('opens delete confirmation when delete is clicked on an existing rule', async () => {
    vi.mocked(mock.get).mockResolvedValue({
      data: {
        count: 1,
        results: [
          {
            id: 'rule-1',
            tenant: 't-1',
            name: 'Quality drop',
            description: '',
            metric_type: 'quality_score',
            threshold: 80,
            comparison_operator: '<',
            severity: 'MEDIUM',
            alert_channels: ['EMAIL'],
            channel_config: { emails: ['oncall@example.com'] },
            enabled: true,
            created_at: '2026-05-01T00:00:00Z',
            updated_at: '2026-05-01T00:00:00Z',
          },
        ],
        page: 1,
        page_size: 20,
        total_pages: 1,
        has_next: false,
        has_previous: false,
      },
    });
    render(<AlertingRuleManager />, { wrapper: Wrapper });
    expect(await screen.findByTestId('rule-row-rule-1')).toBeTruthy();
    fireEvent.click(screen.getByTestId('rule-delete-rule-1'));
    expect(await screen.findByText(/delete alerting rule/i)).toBeTruthy();
  });
});
