import { apiClient } from '@/shared/api/client';
/**
 * Databricks SSO API service (task 0b.12) — the login button / workspace
 * chooser / session-countdown backend surface.
 */

import { DatabricksApiError } from './databricksService';

const BASE = '/api/v1/databricks/sso';

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${BASE}${url}`, {
    headers: {
      ...apiClient._buildHeaders(init?.method ?? 'GET', `${BASE}${url}`),
    },
    ...init,
  });
  const body = (await resp.json().catch(() => ({}))) as Record<string, unknown>;
  if (!resp.ok) {
    // Envelope shapes vary: the SSO gate returns {error: {code, message}}
    // while validation errors return {error: <string>, code: <top-level>}.
    // Merging both keeps the typed code either way — a generic
    // "Request failed with HTTP 400" masks the code from the UI
    // (observed: DATABRICKS_SSO_DISABLED journey showed a code-less 400).
    const nested =
      typeof body.error === 'object' && body.error !== null
        ? (body.error as Record<string, unknown>)
        : {};
    const envelope = { ...nested, ...body } as {
      code?: string;
      message?: string;
    };
    throw new DatabricksApiError(
      envelope.message || `Request failed with HTTP ${resp.status}`,
      envelope.code,
      resp.status
    );
  }
  return body as T;
}

export interface SsoWorkspace {
  id: string;
  name: string;
  host: string;
  cloud: string;
}

export interface SessionCountdownState {
  countdown: { active: boolean; seconds_remaining: number | null };
  hub_reauth_deadline: string;
}

export function ssoWorkspaces(tenantId: string): Promise<SsoWorkspace[]> {
  return request<{ workspaces: SsoWorkspace[] }>(
    `/workspaces/?tenant_id=${encodeURIComponent(tenantId)}`
  ).then((data) => data.workspaces ?? []);
}

export function ssoLoginUrl(
  tenantId: string,
  workspaceId: string,
  redirectUri: string
): Promise<{ login_url: string }> {
  const params = new URLSearchParams({
    tenant_id: tenantId,
    workspace_id: workspaceId,
    redirect_uri: redirectUri,
  });
  return request<{ login_url: string }>(`/login-url/?${params.toString()}`);
}

export function ssoSession(): Promise<SessionCountdownState> {
  return request<SessionCountdownState>('/session/');
}