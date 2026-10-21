import { DataHubClient } from './client';

export class FilesAPI {
  private client: DataHubClient;

  constructor(client: DataHubClient) {
    this.client = client;
  }

  async initUpload(data: any): Promise<any> {
    return this.client.post('files/init/', data);
  }

  async completeUpload(id: string): Promise<any> {
    return this.client.post(`files/${id}/complete/`);
  }

  async list(params?: any): Promise<any> {
    return this.client.get('files/', { params });
  }

  async get(id: string): Promise<any> {
    return this.client.get(`files/${id}/`);
  }

  async delete(id: string): Promise<any> {
    return this.client.delete(`files/${id}/`);
  }

  async getDownloadUrl(id: string): Promise<any> {
    return this.client.get(`files/${id}/download/`);
  }
}
