import { DataHubClient } from './client';

export class BaaSAPI {
  private client: DataHubClient;

  constructor(client: DataHubClient) {
    this.client = client;
  }

  async listApiKeys(params?: any): Promise<any> {
    return this.client.get('baas/api-keys/', { params });
  }

  async createApiKey(data: any): Promise<any> {
    return this.client.post('baas/api-keys/', data);
  }

  async getApiKey(id: string): Promise<any> {
    return this.client.get(`baas/api-keys/${id}/`);
  }

  async updateApiKey(id: string, data: any): Promise<any> {
    return this.client.patch(`baas/api-keys/${id}/`, data);
  }

  async revokeApiKey(id: string): Promise<any> {
    return this.client.delete(`baas/api-keys/${id}/`);
  }

  async rotateApiKey(id: string, graceHours?: number): Promise<any> {
    return this.client.post(`baas/api-keys/${id}/`, { rotate: true, grace_hours: graceHours });
  }

  async getUsageStats(params?: any): Promise<any> {
    return this.client.get('baas/usage/', { params });
  }

  async getUsageByEndpoint(params?: any): Promise<any> {
    return this.client.get('baas/usage/', { params: { group_by: 'endpoint', ...params } });
  }

  async listCustomers(params?: any): Promise<any> {
    return this.client.get('baas/billing-reports/', { params });
  }

  async getCustomerUsage(customerId: string, period?: string): Promise<any> {
    return this.client.get(`baas/billing-reports/${customerId}/`, { params: { period } });
  }

  async listBillingReports(params?: any): Promise<any> {
    return this.client.get('baas/billing-reports/', { params });
  }

  async generateBillingReport(period: string): Promise<any> {
    return this.client.post('baas/billing-reports/', { period });
  }

  async getBillingReport(id: string): Promise<any> {
    return this.client.get(`baas/billing-reports/${id}/`);
  }
}
