/**
 * AI Features Types
 * Based on backend AI serializers
 */

export interface NaturalLanguageSearchRequest {
  query: string;
  result_types?: ('assets' | 'contracts' | 'datasets')[];
  filters?: Record<string, unknown>;
}

export interface StructuredQuery {
  type: string;
  filters: Record<string, unknown>;
}

export interface InterpretedQuery {
  intent: string;
  entities: string[];
  time_range?: string | null;
  structured_query: StructuredQuery;
}

export interface NaturalLanguageSearchResponse {
  query: string;
  interpreted_query: InterpretedQuery;
  results: {
    assets?: { total: number; items: unknown[] };
    contracts?: { total: number; items: unknown[] };
    datasets?: { total: number; items: unknown[] };
  };
  execution_time_ms: number;
  cached: boolean;
}

export interface SchemaMatchingRequest {
  source_schema: Record<string, unknown>;
  target_schema: Record<string, unknown>;
  context?: Record<string, unknown>;
}

export interface FieldMatch {
  source_field: string;
  target_field: string;
  confidence: number;
  match_type: 'exact' | 'fuzzy' | 'semantic';
}

export interface SchemaMatchingResponse {
  matches: FieldMatch[];
  confidence: number;
  suggestions: string[];
  execution_time_ms: number;
}
