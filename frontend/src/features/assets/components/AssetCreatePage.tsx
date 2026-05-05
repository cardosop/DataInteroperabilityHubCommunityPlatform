/**
 * AssetCreatePage — unified adaptive form for creating assets.
 *
 * Always-visible: Name (auto-populates Key), Key, Domain, Visibility.
 * Collapsible: "+ Add data file" (FileUpload), "+ Add contract" (ContractFileReader).
 *
 * Submit orchestration branches on what the user provided:
 * - metadata only → POST /assets/
 * - data only → POST /assets/data-first/
 * - contract only → POST /assets/ + contract pipeline
 * - data + contract → POST /assets/ + POST /datasets/ + contract pipeline
 */

import { useState, useCallback } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useCreateAsset, useDataFirstAsset } from '../hooks/useAssets';
import { useCreateContract, useCreateODPSProduct } from '../../contracts/hooks/useContracts';
import { useCreateDataset } from '../../datasets/hooks/useDatasets';
import { ContractFileReader } from '../../../shared/components/ContractFileReader';
import { FileUpload } from '../../files/components/FileUpload';
import { CreateAssetSummary } from './CreateAssetSummary';
import {
  SchemaDriftBanner,
  type SchemaDriftPayload,
} from './SchemaDriftBanner';
import {
  AssetTypePickerStep,
  type AssetTypeKind,
} from './AssetTypePickerStep';
import { shouldSkipTypePicker } from './AssetTypePickerStep.utils';
import { useAssetCreationBlockedReason } from '../../../shared/hooks/useAssetCreationBlockedReason';
import { Breadcrumbs } from '../../../shared/components/Breadcrumbs';
import { Button } from '../../../shared/components/Button';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { useToast } from '../../../shared/components/Toast';
import type { DetectedSpec } from '../../../shared/utils/detectSpecType';
import type { File as AppFile } from '../../../shared/types/files';
import './AssetCreatePage.css';

const BREADCRUMBS = [
  { label: 'Home', href: '/' },
  { label: 'Assets', href: '/assets' },
  { label: 'Create' },
];

function slugify(name: string): string {
  return name
    .replace(/[^a-z0-9]+/gi, '-')
    .replace(/^-|-$/g, '')
    .toLowerCase() || '';
}

export function AssetCreatePage() {
  const navigate = useNavigate();
  const location = useLocation();
  const toast = useToast();

  // Phase 250.6.B — type-picker step is rendered FIRST unless
  // ``?skip=picker`` is in the URL (deep-link bypass). When the
  // user picks an option, ``pickedType`` is set and the form
  // renders with ``showDataFile`` / ``showContract`` pre-set
  // per the picked shape. The state lives in-page only — no URL
  // change — per the 250.6.B.3 contract.
  const [pickedType, setPickedType] = useState<AssetTypeKind | null>(
    shouldSkipTypePicker(location.search) ? 'metadata' : null,
  );

  // Metadata
  const [name, setName] = useState('');
  const [key, setKey] = useState('');
  const [keyEdited, setKeyEdited] = useState(false);
  const [description, setDescription] = useState('');
  const [domain, setDomain] = useState('');
  // Phase 250.3.B.5 (D250.4) — visibility is no longer captured on
  // the create form. The server derives it from `status` (DRAFT-on-
  // create → INTERNAL); to make an asset public, the user transitions
  // it to status=PUBLIC after creation. The legacy state slot was
  // removed; the request body no longer carries `visibility`.

  // Collapsible sections
  const [showDataFile, setShowDataFile] = useState(false);
  const [showContract, setShowContract] = useState(false);

  // Phase 250.6.B — when the user picks a type, pre-configure the
  // collapsible-section toggles. ``metadata`` keeps both collapsed;
  // ``data`` opens the data-file section; ``contract`` opens the
  // contract section; ``both`` opens both. The user can still
  // toggle either section after the picker.
  const handleTypeSelect = useCallback((kind: AssetTypeKind) => {
    setPickedType(kind);
    setShowDataFile(kind === 'data' || kind === 'both');
    setShowContract(kind === 'contract' || kind === 'both');
  }, []);

  const handleSkipPicker = useCallback(() => {
    setPickedType('metadata');
  }, []);

  // Phase 250.6.D.3 — read the runtime block reason. When the tenant
  // hasn't yet completed onboarding, the picker renders an
  // onboarding-incomplete variant with a CTA to /onboarding instead
  // of the four kind cards. The DISABLED_BY_OPS reason is handled
  // upstream by the CapabilityRoute redirect; we ONLY branch on
  // ONBOARDING_INCOMPLETE here.
  const { reason: blockedReason } = useAssetCreationBlockedReason();
  const onboardingIncomplete = blockedReason === 'ONBOARDING_INCOMPLETE';
  const handleCompleteOnboarding = useCallback(() => {
    navigate('/onboarding');
  }, [navigate]);

  // Data file state
  const [uploadedFile, setUploadedFile] = useState<AppFile | null>(null);

  // Contract state
  const [contractContent, setContractContent] = useState('');
  const [contractFormat, setContractFormat] = useState('yaml');
  const [detected, setDetected] = useState<DetectedSpec | null>(null);

  // Submit state
  const [submitting, setSubmitting] = useState(false);
  const [currentStep, setCurrentStep] = useState('');
  const [error, setError] = useState<Error | null>(null);
  // Phase 250.2.B.5 — schema-drift payload returned by the
  // data-first endpoint. Captured here so the SchemaDriftBanner can
  // render inline on the page WITHOUT a follow-up fetch — the
  // server already paid the cost of computing it during workflow
  // execution. Cleared on every new submit attempt.
  const [schemaDrift, setSchemaDrift] = useState<SchemaDriftPayload | null>(
    null,
  );
  // 250.2.B audit-pass — track the asset_id of a successfully created
  // asset whose auto-navigate was suppressed by drift detection. With
  // both this AND ``schemaDrift.detected`` set, the form renders an
  // explicit "Continue to asset" CTA so the user has an obvious next
  // action — without it the create button is the only visible CTA and
  // re-clicking it submits a duplicate asset (or hits a dedup error,
  // also bad UX).
  const [createdAssetId, setCreatedAssetId] = useState<string | null>(null);

  // Mutations
  const createAsset = useCreateAsset();
  const dataFirstAsset = useDataFirstAsset();
  const createContract = useCreateContract();
  const createODPS = useCreateODPSProduct();
  const createDataset = useCreateDataset();

  const hasDataFile = !!uploadedFile;
  const hasContract = contractContent.trim().length > 0;
  const isODPS = detected?.type === 'ODPS';

  // Auto-populate key from name (unless user edited key manually)
  const handleNameChange = useCallback((value: string) => {
    setName(value);
    if (!keyEdited) {
      setKey(slugify(value));
    }
  }, [keyEdited]);

  const handleKeyChange = useCallback((value: string) => {
    setKey(value);
    setKeyEdited(true);
  }, []);

  const handleContentChange = useCallback((content: string, format: string) => {
    setContractContent(content);
    setContractFormat(format);
  }, []);

  const handleDetection = useCallback((result: DetectedSpec) => {
    setDetected(result);
  }, []);

  const handleFileUploadComplete = useCallback((file: AppFile) => {
    setUploadedFile(file);
    // Auto-fill name from filename if empty
    if (!name) {
      const fileName = file.name.replace(/\.[^/.]+$/, '');
      handleNameChange(fileName);
    }
  }, [name, handleNameChange]);

  const handleSubmit = async () => {
    if (!name.trim() || !key.trim()) {
      toast.error('Name and Key are required');
      return;
    }

    setSubmitting(true);
    setError(null);
    // 250.2.B audit-pass — clear stale state from a prior submit so a
    // second attempt doesn't render last run's banner / continue CTA.
    setSchemaDrift(null);
    setCreatedAssetId(null);
    let assetId: string | undefined;
    // Phase 250.6.C audit-pass — capture the workflow_instance_id
    // from the data-first response so we can pass it to the
    // AssetDetailPage via React Router navigation state. Without
    // this, the WorkflowProgressWidget on the detail page has
    // nothing to poll. Local-scoped (not React state) for the same
    // closure-stale reason as ``localDrift`` above — `setX(...)`
    // doesn't mutate the variable for this handler invocation.
    let localWorkflowInstanceId: string | null = null;
    // 250.2.B audit-pass — capture drift in a local in addition to
    // React state so the post-submit branch below can read it
    // synchronously. ``setSchemaDrift`` queues a re-render; the value
    // isn't visible to ``schemaDrift`` until the next render, so a
    // direct ``schemaDrift?.detected`` read here would always be
    // ``false`` on the first submit and auto-navigate would fire
    // through, defeating the whole "user sees the banner" guarantee.
    let localDrift: SchemaDriftPayload | null = null;

    try {
      if (hasDataFile && !hasContract) {
        // Data-first: single API call
        setCurrentStep('Creating asset with dataset...');
        const result = await dataFirstAsset.mutateAsync({
          file_id: uploadedFile!.id,
          key: key.trim(),
          name: name.trim(),
          description: description.trim() || undefined,
          domain: domain.trim() || undefined,
        });
        assetId = result.asset_id;
        // Phase 250.6.C audit-pass — capture workflow_instance_id so
        // the next-page navigate carries it as React Router state.
        localWorkflowInstanceId = result.workflow_instance_id ?? null;
        // Phase 250.2.B.5 — capture the drift payload (may be null
        // if the workflow had no contract to compare against).
        const drift = (result as unknown as {
          result_summary?: { schema_drift?: SchemaDriftPayload | null };
        }).result_summary?.schema_drift;
        localDrift = drift ?? null;
        setSchemaDrift(localDrift);
      } else {
        // Step 1: Create asset
        setCurrentStep('Creating asset...');
        const asset = await createAsset.mutateAsync({
          key: key.trim(),
          name: name.trim(),
          description: description.trim() || undefined,
          domain: domain.trim() || undefined,
        });
        assetId = asset.id;

        // Step 2: Create dataset if file was uploaded (data + contract case)
        if (hasDataFile && uploadedFile) {
          setCurrentStep('Creating dataset...');
          try {
            await createDataset.mutateAsync({
              file_id: uploadedFile.id,
              asset_id: assetId,
            });
          } catch (datasetErr) {
            toast.error(`Asset created but dataset failed: ${(datasetErr as Error).message}`);
          }
        }

        // Step 3: Create contract if provided
        if (hasContract) {
          setCurrentStep('Processing contract...');
          const format = contractFormat === 'json' ? 'JSON' : 'YAML';
          try {
            if (isODPS) {
              await createODPS.mutateAsync({
                original_raw: contractContent,
                original_format: format,
                asset_id: assetId,
              });
            } else {
              await createContract.mutateAsync({
                original_raw: contractContent,
                original_format: format,
                original_spec_type: detected?.type,
                asset_id: assetId,
              });
            }
          } catch (contractErr) {
            toast.error(`Asset created but contract failed: ${(contractErr as Error).message}`);
          }
        }
      }

      if (assetId) {
        // Phase 250.2.B.5 — when the workflow surfaced schema drift,
        // keep the user on the create page so they can read the
        // SchemaDriftBanner inline. Auto-navigate only on a clean
        // run (no drift detected). When suppressing the navigate, we
        // ALSO surface the asset_id via ``createdAssetId`` so the form
        // can render an explicit "Continue to asset" CTA — without it
        // the user sees the banner but has no obvious next action.
        // ``localDrift`` (not ``schemaDrift``) is the load-bearing
        // read — see the closure-stale comment above.
        const driftDetected =
          localDrift !== null && localDrift.detected === true;
        if (driftDetected) {
          setCreatedAssetId(assetId);
        } else {
          // Phase 250.6.C audit-pass — pass workflow_instance_id via
          // React Router navigation state so AssetDetailPage can
          // forward it to the OnboardingChecklist's
          // ``workflowInstanceId`` prop. The state is null for
          // metadata-only / contract-only paths (no workflow
          // tracked); the widget short-circuits in that case.
          navigate(`/assets/${assetId}`, {
            state: localWorkflowInstanceId
              ? { workflowInstanceId: localWorkflowInstanceId }
              : undefined,
          });
        }
      }
    } catch (err) {
      setError(err as Error);
    } finally {
      setSubmitting(false);
      setCurrentStep('');
    }
  };

  // Phase 250.6.B — render the type-picker step BEFORE the form
  // when no type has been picked AND the URL didn't carry the
  // ``?skip=picker`` shortcut. The picker is in-page (no route
  // change), so the form's data-testid stays addressable for E2E
  // selectors that bypass the picker via the skip handler.
  // Phase 250.6.D.3 — when onboarding is incomplete, render the
  // picker's blocked variant REGARDLESS of ``pickedType`` (even if
  // the URL carried ``?skip=picker``, the user still hits the
  // onboarding CTA — they can't bypass an incomplete-onboarding
  // gate by deep-linking). The form below is unreachable until
  // onboarding completes, so we short-circuit here.
  if (onboardingIncomplete) {
    return (
      <div className="asset-create-page" data-testid="asset-create-page">
        <div className="asset-create-header">
          <Breadcrumbs items={BREADCRUMBS} />
          <h1>Create Asset</h1>
        </div>
        <AssetTypePickerStep
          onSelect={handleTypeSelect}
          selected={pickedType}
          onboardingIncomplete
          onCompleteOnboarding={handleCompleteOnboarding}
        />
      </div>
    );
  }

  if (pickedType === null) {
    return (
      <div className="asset-create-page" data-testid="asset-create-page">
        <div className="asset-create-header">
          <Breadcrumbs items={BREADCRUMBS} />
          <h1>Create Asset</h1>
        </div>
        <AssetTypePickerStep
          onSelect={handleTypeSelect}
          onSkip={handleSkipPicker}
          selected={pickedType}
        />
      </div>
    );
  }

  return (
    // Phase 226.F1.b — testid for stable e2e selector.
    <div className="asset-create-page" data-testid="asset-create-page">
      <div className="asset-create-header">
        <Breadcrumbs items={BREADCRUMBS} />
        <h1>Create Asset</h1>
      </div>

      <div className="asset-create-form" data-testid="asset-create-form">
        {/* Always-visible metadata */}
        <div className="form-group">
          <label htmlFor="asset-name">Name <span className="required">*</span></label>
          <input
            id="asset-name"
            data-testid="asset-create-name"
            type="text"
            value={name}
            onChange={(e) => handleNameChange(e.target.value)}
            placeholder="My Asset"
            required
          />
        </div>

        <div className="form-group">
          <label htmlFor="asset-key">Key <span className="required">*</span></label>
          <input
            id="asset-key"
            data-testid="asset-create-key"
            type="text"
            value={key}
            onChange={(e) => handleKeyChange(e.target.value)}
            placeholder="my-asset-key"
            required
          />
          <p className="field-hint">Unique identifier (auto-generated from name)</p>
        </div>

        <div className="form-group">
          <label htmlFor="asset-description">Description</label>
          <textarea
            id="asset-description"
            data-testid="asset-create-description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            placeholder="Brief description of this asset..."
          />
        </div>

        <div className="form-group">
          <label htmlFor="asset-domain">Domain</label>
          <input
            id="asset-domain"
            data-testid="asset-create-domain"
            type="text"
            list="domain-suggestions"
            value={domain}
            onChange={(e) => setDomain(e.target.value)}
            placeholder="marketing, sales, etc."
          />
          <datalist id="domain-suggestions">
            <option value="marketing" />
            <option value="sales" />
            <option value="finance" />
            <option value="engineering" />
            <option value="analytics" />
            <option value="operations" />
            <option value="product" />
            <option value="customer-success" />
          </datalist>
          <p className="field-hint">Select or type a domain</p>
        </div>

        {/*
         * Phase 250.3.B.5 (D250.4) — the legacy "Visibility" select
         * was removed: visibility is now derived server-side from
         * `status` (DRAFT/ACTIVE/RETIRED → INTERNAL; PUBLIC → PUBLIC).
         * To make an asset publicly visible, the operator transitions
         * its `status` after creation (the asset detail page exposes
         * the status-transition button). Leaving the form input in
         * place would be misleading — pre-phase-2 it was silently
         * ignored, post-phase-2 it 400s.
         */}

        {/* Collapsible: Add data file */}
        <div className="asset-create-section">
          <button
            type="button"
            className="asset-create-section__toggle"
            aria-expanded={showDataFile}
            aria-controls="data-file-section"
            onClick={() => setShowDataFile(!showDataFile)}
          >
            {showDataFile ? '− Remove data file' : '+ Add data file'}
          </button>
          {showDataFile && (
            <div id="data-file-section" className="asset-create-section__content">
              <FileUpload
                onUploadComplete={handleFileUploadComplete}
                accept=".csv,.json,.parquet,.xlsx"
              />
              {uploadedFile && (
                <p className="asset-create-section__file-name">
                  Uploaded: {uploadedFile.name}
                </p>
              )}
            </div>
          )}
        </div>

        {/* Collapsible: Add contract */}
        <div className="asset-create-section">
          <button
            type="button"
            className="asset-create-section__toggle"
            aria-expanded={showContract}
            aria-controls="contract-section"
            onClick={() => setShowContract(!showContract)}
          >
            {showContract ? '− Remove contract' : '+ Add contract'}
          </button>
          {showContract && (
            <div id="contract-section" className="asset-create-section__content">
              <ContractFileReader
                onContentChange={handleContentChange}
                onDetection={handleDetection}
              />
            </div>
          )}
        </div>

        {/* Summary */}
        <CreateAssetSummary
          hasDataFile={hasDataFile}
          hasContract={hasContract}
          detectedSpecType={detected?.type !== 'UNKNOWN' ? detected?.type : undefined}
          submitting={submitting}
          currentStep={currentStep}
        />

        {/*
         * Phase 250.2.B.5 — schema-drift banner. Renders inline
         * after a successful data-first creation when the workflow
         * detected drift between the contract and the dataset
         * schema. ``SchemaDriftBanner`` returns null when there's
         * nothing to show (no drift, or no contract+dataset to
         * compare), so this is a zero-cost render path on the
         * happy path.
         */}
        <SchemaDriftBanner drift={schemaDrift} />

        {error && (
          <ErrorDisplay
            error={error}
            title="Failed to create asset"
            onRetry={() => setError(null)}
          />
        )}

        {/* Actions */}
        <div className="form-actions">
          <Button
            variant="primary"
            onClick={handleSubmit}
            disabled={
              !name.trim() ||
              !key.trim() ||
              submitting ||
              createdAssetId !== null
            }
            data-testid="asset-create-submit"
          >
            {submitting ? 'Creating...' : 'Create Asset'}
          </Button>
          {/*
           * 250.2.B audit-pass — Continue CTA. Renders only when the
           * asset already landed but auto-navigate was suppressed by
           * drift detection. Disabling the Create button (above) while
           * ``createdAssetId`` is set prevents accidental re-submit
           * (which would either create a duplicate asset or, with the
           * unique key constraint, trip a 409). The button is the
           * obvious "I've read the banner, take me to the asset" path.
           */}
          {createdAssetId !== null && (
            <Button
              variant="primary"
              onClick={() => navigate(`/assets/${createdAssetId}`)}
              data-testid="asset-create-continue-after-drift"
            >
              Continue to asset
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
