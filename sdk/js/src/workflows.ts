import { DataHubClient } from './client';

export class WorkflowsAPI {
  private client: DataHubClient;

  constructor(client: DataHubClient) {
    this.client = client;
  }

  async list(params?: any): Promise<any> {
    return this.client.get('workflows/', { params });
  }

  async get(id: string): Promise<any> {
    return this.client.get(`workflows/${id}/`);
  }

  async trigger(id: string): Promise<any> {
    return this.client.post(`workflows/${id}/trigger/`);
  }

  async retry(id: string): Promise<any> {
    return this.client.post(`workflows/${id}/trigger/`, { retry: true });
  }
}
