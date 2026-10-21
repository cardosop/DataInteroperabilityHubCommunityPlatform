import { DataHubClient } from './client';

export class MarketplaceAPI {
  private client: DataHubClient;

  constructor(client: DataHubClient) {
    this.client = client;
  }

  async listListings(params?: any): Promise<any> {
    return this.client.get('marketplace/listings/', { params });
  }

  async getListing(id: string): Promise<any> {
    return this.client.get(`marketplace/listings/${id}/`);
  }

  async createListing(data: any): Promise<any> {
    return this.client.post('marketplace/listings/', data);
  }

  async updateListing(id: string, data: any): Promise<any> {
    return this.client.patch(`marketplace/listings/${id}/`, data);
  }

  async publishListing(id: string): Promise<any> {
    return this.client.post(`marketplace/listings/${id}/publish/`);
  }

  async listOrders(params?: any): Promise<any> {
    return this.client.get('marketplace/orders/', { params });
  }

  async createOrder(listingId: string): Promise<any> {
    return this.client.post('marketplace/orders/', { listing_id: listingId });
  }

  async approveOrder(id: string, comments?: string): Promise<any> {
    return this.client.post(`marketplace/orders/${id}/approve/`, { comments });
  }

  async rejectOrder(id: string, reason: string): Promise<any> {
    return this.client.post(`marketplace/orders/${id}/reject/`, { reason });
  }

  async listEntitlements(params?: any): Promise<any> {
    return this.client.get('marketplace/entitlements/', { params });
  }

  async checkAccess(assetId: string): Promise<any> {
    return this.client.post('marketplace/entitlements/check-access/', { asset_id: assetId });
  }
}
