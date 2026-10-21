import { DataHubClient } from './client';

export class GovernanceAPI {
  private client: DataHubClient;

  constructor(client: DataHubClient) {
    this.client = client;
  }

  async listAccessRequests(params?: any): Promise<any> {
    return this.client.get('governance/access-requests/', { params });
  }

  async getAccessRequest(id: string): Promise<any> {
    return this.client.get(`governance/access-requests/${id}/`);
  }

  async createAccessRequest(data: any): Promise<any> {
    return this.client.post('governance/access-requests/', data);
  }

  async approveAccessRequest(id: string, comments?: string): Promise<any> {
    return this.client.post(`governance/access-requests/${id}/approve/`, { comments });
  }

  async rejectAccessRequest(id: string, reason: string): Promise<any> {
    return this.client.post(`governance/access-requests/${id}/reject/`, { reason });
  }

  async getClassification(assetId: string): Promise<any> {
    return this.client.get(`governance/analytics/`, { params: { asset_id: assetId } });
  }

  async classifyAsset(assetId: string, data: any): Promise<any> {
    return this.client.post(`assets/${assetId}/classify/`, data);
  }

  async listRetentionPolicies(assetId: string): Promise<any> {
    return this.client.get('governance/retention-policies/', { params: { asset_id: assetId } });
  }

  async createRetentionPolicy(assetId: string, data: any): Promise<any> {
    return this.client.post('governance/retention-policies/', { ...data, asset_id: assetId });
  }
}
