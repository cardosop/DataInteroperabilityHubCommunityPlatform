import { DataHubClient } from './client';

export class DQAPI {
  private client: DataHubClient;

  constructor(client: DataHubClient) {
    this.client = client;
  }

  async createRun(data: any): Promise<any> {
    return this.client.post('dq/runs/', data);
  }

  async listRuns(params?: any): Promise<any> {
    return this.client.get('dq/runs/', { params });
  }

  async getRun(id: string): Promise<any> {
    return this.client.get(`dq/runs/${id}/`);
  }

  async getScorecard(assetId: string): Promise<any> {
    return this.client.get('dq/runs/', { params: { asset_id: assetId, include: 'scorecard' } });
  }

  async listAlerts(params?: any): Promise<any> {
    return this.client.get('dq/runs/', { params: { ...params, include: 'alerts' } });
  }

  async createAlert(data: any): Promise<any> {
    return this.client.post('dq/runs/', { ...data, type: 'alert' });
  }

  async getAnomalies(assetId: string): Promise<any> {
    return this.client.get('dq/runs/', { params: { asset_id: assetId, include: 'anomalies' } });
  }

  async getTrends(assetId: string): Promise<any> {
    return this.client.get('dq/runs/', { params: { asset_id: assetId, include: 'trends' } });
  }
}
