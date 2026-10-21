import { DataHubClient } from './client';

export class WebhooksAPI {
  private client: DataHubClient;

  constructor(client: DataHubClient) {
    this.client = client;
  }

  async listWebhooks(params?: any): Promise<any> {
    return this.client.get('webhooks/webhooks/', { params });
  }

  async getWebhook(id: string): Promise<any> {
    return this.client.get(`webhooks/webhooks/${id}/`);
  }

  async createWebhook(data: any): Promise<any> {
    return this.client.post('webhooks/webhooks/', data);
  }

  async updateWebhook(id: string, data: any): Promise<any> {
    return this.client.patch(`webhooks/webhooks/${id}/`, data);
  }

  async deleteWebhook(id: string): Promise<any> {
    return this.client.delete(`webhooks/webhooks/${id}/`);
  }

  async testWebhook(id: string): Promise<any> {
    return this.client.post(`webhooks/webhooks/${id}/test/`);
  }
}
