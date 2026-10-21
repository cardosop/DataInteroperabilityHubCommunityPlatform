import { DataHubClient } from './client';

export class VersioningAPI {
  private client: DataHubClient;

  constructor(client: DataHubClient) {
    this.client = client;
  }

  async listVersions(datasetId: string, params?: any): Promise<any> {
    return this.client.get('versioning/versions/', { params: { dataset_id: datasetId, ...params } });
  }

  async getVersion(datasetId: string, versionId: string): Promise<any> {
    return this.client.get(`versioning/versions/${versionId}/`);
  }

  async createVersion(datasetId: string, data: any): Promise<any> {
    return this.client.post('versioning/versions/', { dataset_id: datasetId, ...data });
  }

  async compareVersions(datasetId: string, v1: string, v2: string): Promise<any> {
    return this.client.get('versioning/compare/', { params: { dataset_id: datasetId, version_a: v1, version_b: v2 } });
  }

  async getImpact(datasetId: string, versionId: string): Promise<any> {
    return this.client.get(`versioning/versions/${versionId}/`, { params: { include: 'impact' } });
  }
}
