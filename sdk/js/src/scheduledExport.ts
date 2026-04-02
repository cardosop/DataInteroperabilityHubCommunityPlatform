import { DataHubClient } from './client';

export class ScheduledExportAPI {
  private client: DataHubClient;

  constructor(client: DataHubClient) {
    this.client = client;
  }

  async list(params?: any): Promise<any> {
    return this.client.get('scheduled-exports/', { params });
  }

  async get(id: string): Promise<any> {
    return this.client.get(`scheduled-exports/${id}/`);
  }

  async create(data: any): Promise<any> {
    return this.client.post('scheduled-exports/', data);
  }

  async update(id: string, data: any): Promise<any> {
    return this.client.patch(`scheduled-exports/${id}/`, data);
  }

  async delete(id: string): Promise<any> {
    return this.client.delete(`scheduled-exports/${id}/`);
  }

  async trigger(id: string): Promise<any> {
    return this.client.post(`scheduled-exports/${id}/trigger/`);
  }

  async listRuns(id: string, params?: any): Promise<any> {
    return this.client.get('scheduled-exports/runs/', { params: { export_id: id, ...params } });
  }
}
