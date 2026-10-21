import { DataHubClient } from './client';

export class DatasetsAPI {
  private client: DataHubClient;

  constructor(client: DataHubClient) {
    this.client = client;
  }

  async list(params?: any): Promise<any> {
    return this.client.get('datasets/', { params });
  }

  async get(id: string): Promise<any> {
    return this.client.get(`datasets/${id}/`);
  }

  async create(data: any): Promise<any> {
    return this.client.post('datasets/', data);
  }

  async delete(id: string): Promise<any> {
    return this.client.delete(`datasets/${id}/`);
  }

  async listVersions(id: string, params?: any): Promise<any> {
    return this.client.get(`datasets/${id}/versions/`, { params });
  }

  async getVersion(id: string, versionId: string): Promise<any> {
    return this.client.get(`datasets/${id}/versions/${versionId}/`);
  }
}
