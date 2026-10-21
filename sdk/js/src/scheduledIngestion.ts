import { DataHubClient } from './client';

export class ScheduledIngestionAPI {
  private client: DataHubClient;

  constructor(client: DataHubClient) {
    this.client = client;
  }

  async list(params?: any): Promise<any> {
    return this.client.get('scheduled-ingestions/', { params });
  }

  async get(id: string): Promise<any> {
    return this.client.get(`scheduled-ingestions/${id}/`);
  }

  async create(data: any): Promise<any> {
    return this.client.post('scheduled-ingestions/', data);
  }

  async update(id: string, data: any): Promise<any> {
    return this.client.patch(`scheduled-ingestions/${id}/`, data);
  }

  async delete(id: string): Promise<any> {
    return this.client.delete(`scheduled-ingestions/${id}/`);
  }

  async trigger(id: string): Promise<any> {
    return this.client.post(`scheduled-ingestions/${id}/trigger/`);
  }

  async listRuns(id: string, params?: any): Promise<any> {
    return this.client.get('scheduled-ingestions/runs/', { params: { ingestion_id: id, ...params } });
  }

  async getRunDetail(id: string, runId: string): Promise<any> {
    return this.client.get(`scheduled-ingestions/runs/${runId}/`);
  }
}
