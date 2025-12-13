/**
 * Lineage operations for DataHub SDK.
 */

import { DataHubClient } from './client';

export interface GetFullLineageParams {
  maxContractDepth?: number;
  maxModelDepth?: number;
  maxFieldDepth?: number;
}

export interface GetImpactAnalysisParams {
  depth?: number;
  includeFields?: boolean;
}

/**
 * Lineage API.
 */
export class LineageAPI {
  private client: DataHubClient;

  constructor(client: DataHubClient) {
    this.client = client;
  }

  /**
   * Get contract-level lineage.
   */
  async getContractLineage(contractId: string): Promise<any> {
    return this.client.get(`contracts/${contractId}/lineage/contracts/`);
  }

  /**
   * Get model-level lineage.
   */
  async getModelLineage(contractId: string, modelName: string): Promise<any> {
    return this.client.get(`contracts/${contractId}/models/${modelName}/lineage/`);
  }

  /**
   * Get field-level lineage.
   */
  async getFieldLineage(contractId: string, modelName: string, fieldName: string): Promise<any> {
    return this.client.get(`contracts/${contractId}/fields/${modelName}/${fieldName}/lineage/`);
  }

  /**
   * Get complete hierarchical lineage.
   */
  async getFullLineage(contractId: string, params: GetFullLineageParams = {}): Promise<any> {
    const queryParams: any = {
      max_contract_depth: params.maxContractDepth || 10,
      max_model_depth: params.maxModelDepth || 10,
      max_field_depth: params.maxFieldDepth || 10,
    };
    return this.client.get(`contracts/${contractId}/lineage/full/`, { params: queryParams });
  }

  /**
   * Get lineage visualization.
   */
  async getVisualization(contractId: string, format: 'json' | 'dot' | 'mermaid' = 'json'): Promise<any> {
    const response = await this.client.request({
      method: 'GET',
      url: `contracts/${contractId}/lineage/visualization/`,
      params: { format },
    });

    if (format === 'dot' || format === 'mermaid') {
      return { format, content: response.data };
    }

    return response.data;
  }

  /**
   * Get impact analysis.
   */
  async getImpactAnalysis(contractId: string, params: GetImpactAnalysisParams = {}): Promise<any> {
    const queryParams: any = {
      depth: params.depth || 10,
      include_fields: params.includeFields !== false,
    };
    return this.client.get(`contracts/${contractId}/impact-analysis/`, { params: queryParams });
  }
}

