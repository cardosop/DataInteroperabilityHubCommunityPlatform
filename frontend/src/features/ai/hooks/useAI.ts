/**
 * AI Features React Query Hooks
 */

import { useMutation } from '@tanstack/react-query';
import { aiService } from '../services/aiService';
import type {
  NaturalLanguageSearchRequest,
  SchemaMatchingRequest,
} from '../../../shared/types/ai';

export function useNaturalLanguageSearch() {
  return useMutation({
    mutationFn: (data: NaturalLanguageSearchRequest) => aiService.naturalLanguageSearch(data),
  });
}

export function useSchemaMatching() {
  return useMutation({
    mutationFn: (data: SchemaMatchingRequest) => aiService.schemaMatching(data),
  });
}
