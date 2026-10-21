import { DataHubClient } from './client';

export class TenantsAPI {
  private client: DataHubClient;

  constructor(client: DataHubClient) {
    this.client = client;
  }

  async getCurrentTenant(): Promise<any> {
    return this.client.get('tenants/me/config/');
  }

  async updateTenant(data: any): Promise<any> {
    return this.client.patch('tenants/me/config/', data);
  }
}
