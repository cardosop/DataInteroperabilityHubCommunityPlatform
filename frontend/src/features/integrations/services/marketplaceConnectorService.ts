/**
 * Marketplace Connector Service
 * API client for marketplace connector information
 */

import { apiClient } from '../../../shared/api/client';
import type { MarketplaceConnector } from '../../../shared/types/integrations';

const CONNECTORS_BASE_PATH = 'integrations/marketplace/connectors';

export const marketplaceConnectorService = {
  /**
   * List all available connectors
   */
  async list(): Promise<MarketplaceConnector[]> {
    const response = await apiClient.getClient().get<MarketplaceConnector[]>(`${CONNECTORS_BASE_PATH}/`);
    return response.data;
  },

  /**
   * Get connector information by type
   */
  async getByType(connectorType: string): Promise<MarketplaceConnector> {
    const response = await apiClient.getClient().get<MarketplaceConnector>(
      `${CONNECTORS_BASE_PATH}/${connectorType}/`
    );
    return response.data;
  },
};
