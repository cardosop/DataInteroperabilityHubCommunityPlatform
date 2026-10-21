import { DataHubClient } from './client';

export class AssetsAPI {
  private client: DataHubClient;

  constructor(client: DataHubClient) {
    this.client = client;
  }

  async list(params?: any): Promise<any> {
    return this.client.get('assets/', { params });
  }

  async get(id: string, include?: string): Promise<any> {
    return this.client.get(`assets/${id}/`, { params: include ? { include } : undefined });
  }

  async create(data: any): Promise<any> {
    return this.client.post('assets/', data);
  }

  async update(id: string, data: any): Promise<any> {
    return this.client.patch(`assets/${id}/`, data);
  }

  async delete(id: string): Promise<any> {
    return this.client.delete(`assets/${id}/`);
  }

  async activate(id: string): Promise<any> {
    return this.client.post(`assets/${id}/activate/`);
  }

  async getHealthScore(id: string): Promise<any> {
    return this.client.get(`assets/${id}/health-score/`);
  }

  async getRecommendations(id: string): Promise<any> {
    return this.client.get('assets/recommendations/', { params: { asset_id: id } });
  }

  async getPopularity(id: string): Promise<any> {
    return this.client.get(`assets/${id}/analytics/`);
  }

  async classify(id: string, data: any): Promise<any> {
    return this.client.post(`assets/${id}/classify/`, data);
  }
}
