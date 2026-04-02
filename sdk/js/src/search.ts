import { DataHubClient } from './client';

export class SearchAPI {
  private client: DataHubClient;

  constructor(client: DataHubClient) {
    this.client = client;
  }

  async search(query: string, params?: any): Promise<any> {
    return this.client.get('search/search/', { params: { q: query, ...params } });
  }

  async suggest(query: string): Promise<any> {
    return this.client.get('search/suggestions/', { params: { q: query } });
  }

  async getSearchFilters(): Promise<any> {
    return this.client.get('search/analytics/');
  }
}
