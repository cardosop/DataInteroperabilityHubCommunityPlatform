import { DataHubClient } from './client';

export class MeshAPI {
  private client: DataHubClient;

  constructor(client: DataHubClient) {
    this.client = client;
  }

  async listDomains(params?: any): Promise<any> {
    return this.client.get('mesh/domains/', { params });
  }

  async getDomain(id: string): Promise<any> {
    return this.client.get(`mesh/domains/${id}/`);
  }

  async createDomain(data: any): Promise<any> {
    return this.client.post('mesh/domains/', data);
  }

  async updateDomain(id: string, data: any): Promise<any> {
    return this.client.patch(`mesh/domains/${id}/`, data);
  }

  async deleteDomain(id: string): Promise<any> {
    return this.client.delete(`mesh/domains/${id}/`);
  }

  async listPolicies(domainId: string): Promise<any> {
    return this.client.get(`mesh/domains/${domainId}/policies/`);
  }

  async createPolicy(domainId: string, data: any): Promise<any> {
    return this.client.post(`mesh/domains/${domainId}/policies/apply/`, data);
  }

  async getTopology(): Promise<any> {
    return this.client.get('mesh/topology/');
  }

  async getDataProducts(domainId: string): Promise<any> {
    return this.client.get(`mesh/domains/${domainId}/assets/`);
  }

  async getDomainMetrics(domainId: string): Promise<any> {
    return this.client.get(`mesh/domains/${domainId}/analytics/`);
  }
}
