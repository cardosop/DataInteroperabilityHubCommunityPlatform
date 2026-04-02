import { DataHubClient } from './client';

export class MLAPI {
  private client: DataHubClient;

  constructor(client: DataHubClient) {
    this.client = client;
  }

  async listModels(params?: any): Promise<any> {
    return this.client.get('ml/models/', { params });
  }

  async getModel(id: string): Promise<any> {
    return this.client.get(`ml/models/${id}/`);
  }

  async createModel(data: any): Promise<any> {
    return this.client.post('ml/models/', data);
  }

  async deleteModel(id: string): Promise<any> {
    return this.client.delete(`ml/models/${id}/`);
  }

  async deployModel(id: string, config?: any): Promise<any> {
    return this.client.post(`ml/models/${id}/deploy/`, config || {});
  }

  async undeployModel(id: string): Promise<any> {
    return this.client.post(`ml/models/${id}/cancel/`, { action: 'undeploy' });
  }

  async rollbackModel(id: string, version: string): Promise<any> {
    return this.client.post(`ml/models/${id}/sync-from-odh/`, { version });
  }

  async listTrainingJobs(params?: any): Promise<any> {
    return this.client.get('ml/training/jobs/', { params });
  }

  async getTrainingJob(id: string): Promise<any> {
    return this.client.get(`ml/training/jobs/${id}/`);
  }

  async createTrainingJob(data: any): Promise<any> {
    return this.client.post('ml/training/jobs/', data);
  }

  async listInferenceDeployments(params?: any): Promise<any> {
    return this.client.get('ml/inference/deployments/', { params });
  }

  async getInferenceDeployment(id: string): Promise<any> {
    return this.client.get(`ml/inference/deployments/${id}/`);
  }

  async getModelMetrics(id: string): Promise<any> {
    return this.client.get(`ml/inference/deployments/${id}/metrics/`);
  }

  async publishToMarketplace(id: string, pricingModel?: any): Promise<any> {
    return this.client.post(`ml/models/${id}/link-dataset/`, { pricing_model: pricingModel });
  }

  async getMlPlan(): Promise<any> {
    return this.client.get('billing/subscription/ml/current/');
  }

  async getMlPlanLimits(): Promise<any> {
    return this.client.get('billing/plans/', { params: { type: 'ml' } });
  }
}
