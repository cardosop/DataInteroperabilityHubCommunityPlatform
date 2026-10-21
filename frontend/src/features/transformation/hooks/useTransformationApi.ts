/**
 * 285.9.4 — useTransformationApi hook.
 *
 * Provides transformation API methods for the wizard and validation pages.
 */
import { useCallback } from 'react';
import { apiClient } from '../../../shared/api/client';

export interface ContractPreviewResponse {
  contract: Record<string, unknown>;
  files: Record<string, string>;
  schema: Record<string, unknown>;
}

export interface ValidationResultResponse {
  is_valid: boolean;
  errors: string[];
  warnings: string[];
}

export function useTransformationApi() {
  const getContractPreview = useCallback(
    async (pipelineId: string) =>
      apiClient.getClient().get<ContractPreviewResponse>(
        `/api/v1/transformation/pipelines/${pipelineId}/contract/`,
      ),
    [],
  );

  const validateOutput = useCallback(
    async (
      pipelineId: string,
      params: Record<string, string>,
    ) =>
      apiClient.getClient().post<ValidationResultResponse>(
        `/api/v1/transformation/pipelines/${pipelineId}/validate-output/`,
        params,
      ),
    [],
  );

  const scaffoldModel = useCallback(
    async (pipelineId: string, contractId: string) =>
      apiClient.getClient().post(
        `/api/v1/transformation/pipelines/${pipelineId}/scaffold/`,
        { contract_id: contractId },
      ),
    [],
  );

  const updatePipeline = useCallback(
    async (pipelineId: string, data: Record<string, unknown>) =>
      apiClient.getClient().patch(
        `/api/v1/transformation/pipelines/${pipelineId}/`,
        data,
      ),
    [],
  );

  const executeDbt = useCallback(
    async (pipelineId: string, assetId: string) =>
      apiClient.getClient().post(
        `/api/v1/transformation/pipelines/${pipelineId}/execute/`,
        { asset_id: assetId, execution_mode: 'ASYNC' },
      ),
    [],
  );

  return {
    getContractPreview,
    validateOutput,
    scaffoldModel,
    updatePipeline,
    executeDbt,
  };
}
