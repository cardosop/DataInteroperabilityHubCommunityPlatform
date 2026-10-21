/**
 * Developer Portal Types
 * Based on backend Developer models and serializers
 */

export const PluginStatus = {
  AVAILABLE: 'AVAILABLE',
  DEPRECATED: 'DEPRECATED',
  BETA: 'BETA',
  ALPHA: 'ALPHA',
} as const;
export type PluginStatus = (typeof PluginStatus)[keyof typeof PluginStatus];

export const PluginCategory = {
  CONNECTOR: 'CONNECTOR',
  TRANSFORMER: 'TRANSFORMER',
  VALIDATOR: 'VALIDATOR',
  ANALYZER: 'ANALYZER',
  INTEGRATION: 'INTEGRATION',
  OTHER: 'OTHER',
} as const;
export type PluginCategory = (typeof PluginCategory)[keyof typeof PluginCategory];

export interface Plugin {
  id: string;
  name: string;
  description: string;
  version: string;
  author: string;
  category: PluginCategory;
  status: PluginStatus;
  download_count: number;
  rating?: number;
  metadata_json?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export const SDKLanguage = {
  PYTHON: 'python',
  JAVASCRIPT: 'javascript',
  TYPESCRIPT: 'typescript',
  R: 'r',
} as const;
export type SDKLanguage = (typeof SDKLanguage)[keyof typeof SDKLanguage];

export interface SDKDocumentation {
  id: string;
  language: SDKLanguage;
  version: string;
  documentation_url: string;
  download_url?: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface DeveloperListFilters {
  page?: number;
  page_size?: number;
  category?: PluginCategory;
  status?: PluginStatus;
  search?: string;
  sort?: 'popularity' | 'rating' | 'recency' | 'name';
  language?: SDKLanguage;
}
