import { DataHubClient } from './client';

export class ObservabilityAPI {
  private client: DataHubClient;

  constructor(client: DataHubClient) {
    this.client = client;
  }

  async getMetrics(params?: any): Promise<any> {
    return this.client.get('observability/metrics/', { params });
  }

  async getLogs(params?: any): Promise<any> {
    return this.client.get('observability/pipelines/', { params });
  }

  async getTraces(params?: any): Promise<any> {
    return this.client.get('observability/lineage/', { params });
  }

  async getAlerts(params?: any): Promise<any> {
    return this.client.get('observability/incidents/', { params });
  }

  async getHealth(): Promise<any> {
    return this.client.get('observability/freshness/');
  }

  async getDashboard(): Promise<any> {
    return this.client.get('observability/volume/');
  }

  async getServiceStatus(): Promise<any> {
    return this.client.get('observability/slas/');
  }
}
