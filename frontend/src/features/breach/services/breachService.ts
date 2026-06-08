/**
 * Phase 232.3 — Breach Notification API client.
 *
 * Mirrors the convention established by `assetService`, `datasetService`,
 * and friends: a single `breachService` object that owns every URL +
 * payload shape for the subsystem. Components import `breachService`
 * and never reach into `apiClient` directly — that keeps URLs in one
 * place, payload types named, and the surface mockable in tests.
 */
import { apiClient } from '../../../shared/api/client';

const INCIDENTS_BASE = 'governance/breach-incidents';
const NOTIFICATIONS_BASE = 'governance/breach-notifications';
const TEMPLATES_BASE = 'governance/breach-templates';
const TEMPLATE_OVERRIDES_BASE = 'governance/breach-template-overrides';
const DASHBOARD_PATH = 'governance/breach-dashboard/';

// ---------------------------------------------------------------------------
// Response shapes — public surface used by the components.
// ---------------------------------------------------------------------------

export interface BreachDashboardIncidentSummary {
  id: string;
  title: string;
  status: string;
  statutory_authority_deadline_utc: string | null;
  hours_remaining: number | null;
}

export interface BreachDashboardPayload {
  open_incidents_count: number;
  pending_notifications_count: number;
  incidents: BreachDashboardIncidentSummary[];
}

export interface BreachNotification {
  id: string;
  regime: string;
  supervisory_authority_id: string;
  status: string;
  statutory_due_at_utc: string;
}

export interface BreachIncidentDetail {
  id: string;
  title: string;
  summary: string;
  status: string;
  statutory_authority_deadline_utc: string;
  notifications: BreachNotification[];
}

export interface BreachTemplate {
  regime: string;
  template_version: number;
  subject_template: string;
  body_template: string;
}

export interface BreachTemplateCatalog {
  templates: BreachTemplate[];
}

export interface CreateBreachIncidentRequest {
  title: string;
  summary: string;
  regimes: string[];
  discovered_at: string;
}

export interface CreateBreachIncidentResponse {
  id: string;
}

export interface MarkNotificationSentRequest {
  outbound_reference: string;
}

export interface PatchIncidentStatusRequest {
  status: string;
  notes?: string;
}

export interface UpsertTemplateOverrideRequest {
  regime: string;
  subject_template: string;
  body_template: string;
}

// ---------------------------------------------------------------------------
// Service
// ---------------------------------------------------------------------------

export const breachService = {
  async getDashboard(): Promise<BreachDashboardPayload> {
    const res = await apiClient
      .getClient()
      .get<BreachDashboardPayload>(DASHBOARD_PATH);
    return res.data;
  },

  async getIncident(id: string): Promise<BreachIncidentDetail> {
    const res = await apiClient
      .getClient()
      .get<BreachIncidentDetail>(`${INCIDENTS_BASE}/${id}/`);
    return res.data;
  },

  async createIncident(
    payload: CreateBreachIncidentRequest,
  ): Promise<CreateBreachIncidentResponse> {
    const res = await apiClient
      .getClient()
      .post<CreateBreachIncidentResponse>(`${INCIDENTS_BASE}/`, payload);
    return res.data;
  },

  async patchIncidentStatus(
    id: string,
    payload: PatchIncidentStatusRequest,
  ): Promise<void> {
    await apiClient.getClient().patch(`${INCIDENTS_BASE}/${id}/status/`, payload);
  },

  async markNotificationSent(
    notificationId: string,
    payload: MarkNotificationSentRequest,
  ): Promise<void> {
    await apiClient
      .getClient()
      .post(`${NOTIFICATIONS_BASE}/${notificationId}/mark-sent/`, payload);
  },

  async getTemplateCatalog(): Promise<BreachTemplateCatalog> {
    const res = await apiClient
      .getClient()
      .get<BreachTemplateCatalog>(`${TEMPLATES_BASE}/catalog/`);
    return res.data;
  },

  async upsertTemplateOverride(
    payload: UpsertTemplateOverrideRequest,
  ): Promise<void> {
    await apiClient
      .getClient()
      .post(`${TEMPLATE_OVERRIDES_BASE}/upsert/`, payload);
  },
};
