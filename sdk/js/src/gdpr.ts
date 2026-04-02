import { DataHubClient } from './client';

export class GDPRAPI {
  private client: DataHubClient;

  constructor(client: DataHubClient) {
    this.client = client;
  }

  async createErasureRequest(data: any): Promise<any> {
    return this.client.post('gdpr/erasure-requests/', data);
  }

  async listErasureRequests(params?: any): Promise<any> {
    return this.client.get('gdpr/erasure-requests/', { params });
  }

  async getErasureRequest(id: string): Promise<any> {
    return this.client.get(`gdpr/erasure-requests/${id}/`);
  }

  async executeErasure(id: string): Promise<any> {
    return this.client.post(`gdpr/erasure-requests/${id}/execute/`);
  }

  async getErasureStatus(id: string): Promise<any> {
    return this.client.get(`gdpr/erasure-requests/${id}/`);
  }

  async getDataExport(userId: string): Promise<any> {
    return this.client.get('gdpr/export-jobs/', { params: { user_id: userId } });
  }
}
