/**
 * Marketplace Connectors React Query Hooks
 */

import { useQuery } from '@tanstack/react-query';
import { marketplaceConnectorService } from '../services/marketplaceConnectorService';

export function useMarketplaceConnectors() {
  return useQuery({
    queryKey: ['integrations', 'marketplace', 'connectors', 'list'],
    queryFn: () => marketplaceConnectorService.list(),
  });
}

export function useMarketplaceConnector(connectorType: string | null) {
  return useQuery({
    queryKey: ['integrations', 'marketplace', 'connectors', 'detail', connectorType],
    queryFn: () => marketplaceConnectorService.getByType(connectorType!),
    enabled: !!connectorType,
  });
}
