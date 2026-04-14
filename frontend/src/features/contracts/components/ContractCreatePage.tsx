/**
 * ContractCreatePage — unified contract creation with auto-detection.
 *
 * Branched submit:
 * - ODPS detected → POST /api/v1/contracts/products/ (async workflow with progress)
 * - ODCS/HUB/UNKNOWN → POST /api/v1/contracts/ (synchronous)
 *
 * Optional ?asset_id query param links the contract to an asset.
 */

import { useState, useCallback, useEffect, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { ContractFileReader } from '../../../shared/components/ContractFileReader';
import { Breadcrumbs } from '../../../shared/components/Breadcrumbs';
import { Button } from '../../../shared/components/Button';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { useToast } from '../../../shared/components/Toast';
import { useDebouncedValue } from '../../../shared/hooks/useDebouncedValue';
import {
  useCreateContract,
  useCreateODPSProduct,
  useContractWorkflowStatus,
  useValidateDraft,
} from '../hooks/useContracts';
import { ValidationResultPanel } from './ValidationResultPanel';
import type { DetectedSpec } from '../../../shared/utils/detectSpecType';
import type { ContractFormat, DraftValidationResult } from '../../../shared/types/contracts';
import './ContractCreatePage.css';

const BREADCRUMBS = [
  { label: 'Home', href: '/' },
  { label: 'Contracts', href: '/contracts' },
  { label: 'Create' },
];

export function ContractCreatePage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const toast = useToast();

  const assetId = searchParams.get('asset_id') ?? undefined;

  // Form state
  const [content, setContent] = useState('');
  const [format, setFormat] = useState<string>('yaml');
  const [detected, setDetected] = useState<DetectedSpec | null>(null);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');

  // ODPS workflow state
  const [workflowId, setWorkflowId] = useState<string | null>(null);

  // Mutations
  const createContract = useCreateContract();
  const createODPS = useCreateODPSProduct();
  const validateDraft = useValidateDraft();

  // Pre-submit validation: debounce content changes (1.5s) then validate
  const debouncedContent = useDebouncedValue(content, 1500);
  const [validationResult, setValidationResult] = useState<DraftValidationResult | null>(null);

  useEffect(() => {
    if (!debouncedContent.trim()) {
      setValidationResult(null);
      return;
    }
    const contractFormat = format === 'json' ? 'JSON' : 'YAML';
    validateDraft.mutate(
      { original_raw: debouncedContent, original_format: contractFormat },
      { onSuccess: (data) => setValidationResult(data) },
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only trigger on debounced content/format changes
  }, [debouncedContent, format]);

  // ODPS workflow polling — only active when workflowId is set
  const workflowStatus = useContractWorkflowStatus(workflowId);

  // Track whether we've already handled the terminal workflow state
  // to prevent duplicate navigation/toasts on re-renders
  const handledWorkflowRef = useRef<string | null>(null);

  // React to workflow status changes via useEffect (not in render body)
  useEffect(() => {
    const status = workflowStatus.data?.status;
    if (!workflowId || !status) return;
    // Only handle each terminal state once
    if (handledWorkflowRef.current === workflowId) return;

    if (status === 'COMPLETED' && workflowStatus.data?.odps_contract?.id) {
      handledWorkflowRef.current = workflowId;
      navigate(`/contracts/${workflowStatus.data.odps_contract.id}`);
    } else if (status === 'FAILED') {
      handledWorkflowRef.current = workflowId;
      toast.error(workflowStatus.data?.message ?? 'ODPS workflow failed');
      setWorkflowId(null);
    }
  }, [workflowStatus.data, workflowId, navigate, toast]);

  const handleContentChange = useCallback((newContent: string, newFormat: string) => {
    setContent(newContent);
    setFormat(newFormat);
  }, []);

  const handleDetection = useCallback((result: DetectedSpec) => {
    setDetected(result);
  }, []);

  const isODPS = detected?.type === 'ODPS';
  const isPending = createContract.isPending || createODPS.isPending || !!workflowId;
  const hasContent = content.trim().length > 0;
  const validationBlocks = validationResult !== null && !validationResult.valid;

  const handleSubmit = useCallback(async () => {
    if (!hasContent) return;

    const contractFormat: ContractFormat = format === 'json' ? 'JSON' : 'YAML';

    try {
      if (isODPS) {
        // ODPS: async workflow via products endpoint
        const result = await createODPS.mutateAsync({
          original_raw: content,
          original_format: contractFormat,
          asset_id: assetId,
        });
        // Start polling for workflow status
        setWorkflowId(result.workflow_instance_id);
      } else {
        // ODCS/HUB/UNKNOWN: synchronous contract creation
        const contract = await createContract.mutateAsync({
          original_raw: content,
          original_format: contractFormat,
          original_spec_type: detected?.type,
          asset_id: assetId,
          name: name || undefined,
          description: description || undefined,
        });
        navigate(`/contracts/${contract.id}`);
      }
    } catch (err) {
      // Mutations show toast automatically via useMutationWithNotification
      // but catch here to prevent unhandled rejection
    }
  }, [
    hasContent, isODPS, content, format, detected, assetId,
    name, description, createContract, createODPS, navigate,
  ]);

  const error = (createContract.error ?? createODPS.error ?? null) as Error | null;
  const progressPct = workflowStatus.data?.progress_percentage ?? 0;
  const stepName = workflowStatus.data?.current_step_name ?? '';

  return (
    <div className="contract-create-page">
      <div className="contract-create-page__header">
        <Breadcrumbs items={BREADCRUMBS} />
        <h1 className="contract-create-page__title">Create Contract</h1>
      </div>

      {assetId && (
        <div className="contract-create-page__asset-link">
          Linked to asset: {assetId}
        </div>
      )}

      <div className="contract-create-page__form">
        <div className="contract-create-page__field">
          <label htmlFor="contract-name" className="contract-create-page__label">
            Name (optional)
          </label>
          <input
            id="contract-name"
            type="text"
            className="contract-create-page__input"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Contract name"
          />
        </div>

        <div className="contract-create-page__field">
          <label htmlFor="contract-description" className="contract-create-page__label">
            Description (optional)
          </label>
          <input
            id="contract-description"
            type="text"
            className="contract-create-page__input"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Brief description"
          />
        </div>

        <ContractFileReader
          onContentChange={handleContentChange}
          onDetection={handleDetection}
          data-testid="contract-file-reader"
        />

        <ValidationResultPanel
          result={validationResult}
          isLoading={validateDraft.isPending}
        />

        {workflowId && (
          <div className="contract-create-page__progress">
            <div className="contract-create-page__progress-bar">
              <div
                className="contract-create-page__progress-fill"
                style={{ width: `${progressPct}%` }}
              />
            </div>
            <p className="contract-create-page__progress-text">
              {stepName || 'Processing ODPS product...'} ({progressPct}%)
            </p>
          </div>
        )}

        {error && (
          <ErrorDisplay
            error={error}
            title="Failed to create contract"
            onRetry={() => {
              createContract.reset();
              createODPS.reset();
            }}
          />
        )}

        <div className="contract-create-page__actions">
          <Button
            variant="primary"
            onClick={handleSubmit}
            disabled={!hasContent || isPending || validationBlocks}
          >
            {isPending ? 'Creating...' : 'Create Contract'}
          </Button>
        </div>
      </div>
    </div>
  );
}
