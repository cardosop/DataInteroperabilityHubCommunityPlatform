import { DataHubClient } from './client';

export class VirtualizationAPI {
  private client: DataHubClient;

  constructor(client: DataHubClient) {
    this.client = client;
  }

  async listDatasets(params?: any): Promise<any> {
    return this.client.get('virtualization/datasets/', { params });
  }

  async getDataset(id: string): Promise<any> {
    return this.client.get(`virtualization/datasets/${id}/`);
  }

  async createDataset(data: any): Promise<any> {
    return this.client.post('virtualization/datasets/', data);
  }

  async updateDataset(id: string, data: any): Promise<any> {
    return this.client.patch(`virtualization/datasets/${id}/`, data);
  }

  async deleteDataset(id: string): Promise<any> {
    return this.client.delete(`virtualization/datasets/${id}/`);
  }

  async executeQuery(id: string, data: any): Promise<any> {
    return this.client.post(`virtualization/datasets/${id}/queries/`, data);
  }

  async listExecutions(id: string, params?: any): Promise<any> {
    return this.client.get('virtualization/queries/', { params: { dataset_id: id, ...params } });
  }

  async getExecution(id: string, executionId: string): Promise<any> {
    return this.client.get(`virtualization/queries/${executionId}/`);
  }

  async cancelExecution(id: string, executionId: string): Promise<any> {
    return this.client.post(`virtualization/queries/${executionId}/cancel/`);
  }

  async getTopology(id: string): Promise<any> {
    return this.client.get(`virtualization/topology/`, { params: { dataset_id: id } });
  }
}
