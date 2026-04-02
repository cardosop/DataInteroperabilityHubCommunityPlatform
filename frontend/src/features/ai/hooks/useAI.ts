/**
 * AI Features React Query Hooks
 */

import { useMutationWithNotification } from '../../../shared/hooks/useMutationWithNotification';
import { aiService } from '../services/aiService';
import type {
  NaturalLanguageSearchRequest,
  SchemaMatchingRequest,
} from '../../../shared/types/ai';

export function useNaturalLanguageSearch() {
  return useMutationWithNotification({
    mutationFn: (data: NaturalLanguageSearchRequest) => aiService.naturalLanguageSearch(data),
    successMessage: 'Search completed',
    errorMessage: 'Failed to perform search',
  });
}

export function useSchemaMatching() {
  return useMutationWithNotification({
    mutationFn: (data: SchemaMatchingRequest) => aiService.schemaMatching(data),
    successMessage: 'Schema matching completed',
    errorMessage: 'Failed to match schemas',
  });
}
