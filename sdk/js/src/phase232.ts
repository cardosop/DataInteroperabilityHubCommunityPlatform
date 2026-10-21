/**
 * Phase 232.8.15 — list helpers for the seven compliance-programme API surfaces.
 */
import { DataHubClient } from './client';

export class Phase232ProgrammeAPI {
  private client: DataHubClient;

  constructor(client: DataHubClient) {
    this.client = client;
  }

  listComplianceRuns(params?: Record<string, unknown>): Promise<any> {
    return this.client.get('compliance/runs/', { params: params ?? {} });
  }

  listDpiaRecords(params?: Record<string, unknown>): Promise<any> {
    return this.client.get('dpia/records/', { params: params ?? {} });
  }

  listRopaGenerations(params?: Record<string, unknown>): Promise<any> {
    return this.client.get('ropa/generations/', { params: params ?? {} });
  }

  listBreachIncidents(params?: Record<string, unknown>): Promise<any> {
    return this.client.get('governance/breach-incidents/', { params: params ?? {} });
  }

  listDsarRequests(params?: Record<string, unknown>): Promise<any> {
    return this.client.get('governance/dsar-requests/', { params: params ?? {} });
  }

  listConsentPurposes(params?: Record<string, unknown>): Promise<any> {
    return this.client.get('governance/consent-purposes/', { params: params ?? {} });
  }

  listProcessorAgreements(params?: Record<string, unknown>): Promise<any> {
    return this.client.get('governance/processor-agreements/', { params: params ?? {} });
  }
}
