import { DataHubClient } from './client';

export class TransformationAPI {
  private client: DataHubClient;

  constructor(client: DataHubClient) {
    this.client = client;
  }

  async listPipelines(params?: any): Promise<any> {
    return this.client.get('transformation/pipelines/', { params });
  }

  async getPipeline(id: string): Promise<any> {
    return this.client.get(`transformation/pipelines/${id}/`);
  }

  async createPipeline(data: any): Promise<any> {
    return this.client.post('transformation/pipelines/', data);
  }

  async updatePipeline(id: string, data: any): Promise<any> {
    return this.client.patch(`transformation/pipelines/${id}/`, data);
  }

  async deletePipeline(id: string): Promise<any> {
    return this.client.delete(`transformation/pipelines/${id}/`);
  }

  async validatePipeline(id: string): Promise<any> {
    return this.client.post(`transformation/pipelines/${id}/validate/`);
  }

  async executePipeline(id: string, params?: any): Promise<any> {
    return this.client.post(`transformation/pipelines/${id}/execute/`, params);
  }

  async listExecutions(params?: any): Promise<any> {
    return this.client.get('transformation/executions/', { params });
  }

  async getExecution(id: string): Promise<any> {
    return this.client.get(`transformation/executions/${id}/`);
  }

  async cancelExecution(id: string): Promise<any> {
    return this.client.post(`transformation/executions/${id}/cancel/`);
  }
}
