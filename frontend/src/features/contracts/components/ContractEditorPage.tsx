/**
 * Contract Editor Page
 * Edit contract with form + raw YAML/JSON editor + validation panel
 */

import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { useContract, useUpdateContract, useValidateContract } from '../hooks/useContracts';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { useState, useEffect, useMemo, useCallback } from 'react';
import { ContractFormat, type ContractValidationResult } from '../../../shared/types/contracts';
import { ODPSProductForm, makeEmptyODPSFormData } from './ODPSProductForm';
import { ModelsEditor } from './ModelsEditor';
import {
  parseODPSDocument,
  mergeODPSDocument,
  validateODPSFormData,
} from '../utils/odpsDocumentBuilder';
import { parseFromSource } from '../lib/contractsCompiler';
import type { ODPSFormData } from '../../../shared/types/odps';
import type { SchemaEditorState } from '../../../shared/types/contracts';
import './ContractEditorPage.css';
import { Button } from '../../../shared/components/Button';

// Phase 227 Wave 1 (227.L5.3) — Schema editor tab is ALWAYS shown
// (no feature-flag gate per the 2026-04-30 ungate directive). Existing
// modify-role permissions still apply.
type EditMode = 'form' | 'structured' | 'schema' | 'raw';

export function ContractEditorPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  // Phase 227 Wave 1 (227.L5.3 + L5.7) — read ``?tab=schema`` so deep
  // links from the lineage empty-state CTA and the ContractHealthPage
  // open the editor directly on the Schema tab.
  const [searchParams] = useSearchParams();
  const initialTab = searchParams.get('tab');
  const { data: contract, isLoading, error, refetch } = useContract(id || null);
  const updateMutation = useUpdateContract();
  const validateMutation = useValidateContract();
  const [editMode, setEditMode] = useState<EditMode>('form');
  const [formData, setFormData] = useState({ name: '', description: '' });
  const [rawContent, setRawContent] = useState('');
  const [format, setFormat] = useState<ContractFormat>(ContractFormat.JSON);
  const [validationResult, setValidationResult] = useState<ContractValidationResult | null>(null);
  const [isValidating, setIsValidating] = useState(false);

  // Structured (ODPS form) state — only relevant for ODPS contracts.
  const [odpsForm, setOdpsForm] = useState<ODPSFormData>(() => makeEmptyODPSFormData());
  const [odpsUnknownFields, setOdpsUnknownFields] = useState<Record<string, unknown>>({});
  const [odpsParseError, setOdpsParseError] = useState<string | null>(null);

  // Phase 227 L5.2/L5.3 — Schema-editor state, derived from the contract
  // on load. Re-parsed when the user enters the Schema tab so any raw
  // edits made meanwhile are picked up.
  const [schemaEditorState, setSchemaEditorState] = useState<SchemaEditorState | null>(null);

  const isODPSContract = useMemo(
    () => (contract?.original_spec_type ?? '').toUpperCase() === 'ODPS',
    [contract],
  );

  const parseRawIntoODPSForm = useCallback((raw: string) => {
    try {
      const parsed = parseODPSDocument(raw);
      setOdpsForm(parsed.formData);
      setOdpsUnknownFields(parsed.unknownFields);
      setOdpsParseError(null);
      return true;
    } catch (err) {
      setOdpsParseError((err as Error).message);
      return false;
    }
  }, []);

  useEffect(() => {
    if (!contract) return;
    setFormData({ name: contract.name || '', description: contract.description || '' });
    setRawContent(contract.original_raw);
    setFormat(contract.original_format);

    if ((contract.original_spec_type ?? '').toUpperCase() === 'ODPS') {
      parseRawIntoODPSForm(contract.original_raw);
      // Default to the richest editor we can offer for ODPS contracts.
      setEditMode('structured');
    }

    // Phase 227 Wave 1 (227.L5.3) — honour the ``?tab=schema`` deep
    // link. Done after the default-mode logic above so the URL
    // parameter wins. Pre-seed the editor state from the just-loaded
    // contract so the user lands on a populated editor, not a
    // "Loading…" placeholder.
    if (initialTab === 'schema') {
      const next = parseFromSource(contract.original_raw, {
        specType:
          (contract.original_spec_type ?? '').toUpperCase() === 'ODPS' ? 'ODPS' : 'ODCS',
        specVersion:
          (contract as unknown as { original_spec_version?: string }).original_spec_version ?? '',
        etag: (contract as unknown as { etag?: string | null }).etag ?? null,
      });
      setSchemaEditorState(next);
      setEditMode('schema');
    }
  }, [contract, parseRawIntoODPSForm, initialTab]);

  /**
   * When the user switches into structured mode, re-seed the form from the
   * current raw content so any edits they made in the raw editor are picked
   * up — otherwise the structured view would show a stale snapshot and a
   * save would silently clobber raw edits.
   */
  const handleSwitchToStructured = useCallback(() => {
    if (parseRawIntoODPSForm(rawContent)) {
      setEditMode('structured');
    } else {
      // Leave edit mode unchanged; the disabled "Structured" tab surfaces the error.
      setEditMode((prev) => prev);
    }
  }, [rawContent, parseRawIntoODPSForm]);

  const handleValidate = async () => {
    if (!id) return;
    setIsValidating(true);
    try {
      const result = await validateMutation.mutateAsync(id);
      setValidationResult(result);
    } catch {
      // Error handled by mutation
    } finally {
      setIsValidating(false);
    }
  };

  const handleSave = async () => {
    if (!id) return;

    // Structured ODPS edit: merge form data with preserved unknown fields
    // so round-tripping never drops user-defined content.
    if (editMode === 'structured') {
      if (validateODPSFormData(odpsForm).length > 0) return;
      const merged = mergeODPSDocument(odpsForm, odpsUnknownFields, format);
      try {
        await updateMutation.mutateAsync({
          id,
          data: { original_raw: merged, original_format: format },
        });
        // Keep raw mirror in sync so a subsequent switch to Raw view shows the
        // just-saved document rather than the pre-edit snapshot.
        setRawContent(merged);
        refetch();
      } catch {
        // Error handled by mutation
      }
      return;
    }

    try {
      await updateMutation.mutateAsync({
        id,
        data: editMode === 'form'
          ? { name: formData.name, description: formData.description }
          : { original_raw: rawContent, original_format: format },
      });
      refetch();
    } catch {
      // Error handled by mutation
    }
  };

  if (error) {
    return <ErrorDisplay error={error} title="Failed to load contract" onRetry={() => refetch()} />;
  }

  if (isLoading || !contract) {
    return <LoadingSpinner message="Loading contract..." />;
  }

  return (
    <div className="contract-editor-page">
      <div className="contract-editor-header">
        <Button onClick={() => navigate(`/contracts/${id}`)} variant="ghost">
          ← Back to Contract
        </Button>
        <div className="editor-mode-toggle">
          <button
            onClick={() => setEditMode('form')}
            className={editMode === 'form' ? 'active' : ''}
            type="button"
          >
            Form
          </button>
          {isODPSContract && (
            <button
              onClick={handleSwitchToStructured}
              className={editMode === 'structured' ? 'active' : ''}
              type="button"
              disabled={!!odpsParseError}
              title={odpsParseError ?? undefined}
            >
              Structured
            </button>
          )}
          {/*
            Phase 227 Wave 1 (227.L5.3) — Schema tab is always visible,
            no feature-flag gate. The existing modify-role check still
            applies (a viewer-only user can still see the tab but
            can't save).
          */}
          <button
            onClick={() => {
              if (contract) {
                const next = parseFromSource(rawContent || contract.original_raw, {
                  specType:
                    (contract.original_spec_type ?? '').toUpperCase() === 'ODPS'
                      ? 'ODPS'
                      : 'ODCS',
                  specVersion:
                    (contract as unknown as { original_spec_version?: string })
                      .original_spec_version ?? '',
                  etag: null,
                });
                setSchemaEditorState(next);
              }
              setEditMode('schema');
            }}
            className={editMode === 'schema' ? 'active' : ''}
            type="button"
            data-testid="editor-tab-schema"
          >
            Schema
          </button>
          <button
            onClick={() => setEditMode('raw')}
            className={editMode === 'raw' ? 'active' : ''}
            type="button"
          >
            Raw {format}
          </button>
        </div>
        <div className="editor-actions">
          <Button
 onClick={handleValidate}
 disabled={isValidating}
 variant="secondary">
            {isValidating ? 'Validating...' : 'Validate'}
          </Button>
          <Button
 onClick={handleSave}
 loading={updateMutation.isPending}
 variant="primary">
            Save
          </Button>
        </div>
      </div>

      <div className="contract-editor-content">
        <div className="editor-main">
          {editMode === 'form' ? (
            <div className="editor-form">
              <div className="form-group">
                <label>Name</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData((prev) => ({ ...prev, name: e.target.value }))}
                />
              </div>
              <div className="form-group">
                <label>Description</label>
                <textarea
                  value={formData.description}
                  onChange={(e) => setFormData((prev) => ({ ...prev, description: e.target.value }))}
                  rows={4}
                />
              </div>
            </div>
          ) : editMode === 'structured' ? (
            <div className="editor-structured">
              {odpsParseError ? (
                <div className="validation-errors">
                  <p>Cannot open structured editor:</p>
                  <p>{odpsParseError}</p>
                </div>
              ) : (
                <ODPSProductForm value={odpsForm} onChange={setOdpsForm} />
              )}
            </div>
          ) : editMode === 'schema' ? (
            <div className="editor-schema">
              {schemaEditorState ? (
                <ModelsEditor
                  initialState={schemaEditorState}
                  onSave={async ({ raw, format: outFormat, ifMatch }) => {
                    if (!id) throw new Error('No contract id');
                    // Phase 227 L5.6 — pass the editor's stored ETag
                    // through to the mutation hook so axios attaches
                    // ``If-Match`` to the PATCH. On 412 the response
                    // body carries the typed PRECONDITION_FAILED code
                    // and the conflict dialog opens.
                    const updated = await updateMutation.mutateAsync({
                      id,
                      data: {
                        original_raw: raw,
                        original_format: outFormat as ContractFormat,
                      },
                      ifMatch: ifMatch ?? schemaEditorState?.etag ?? null,
                    });
                    setRawContent(raw);
                    return { etag: (updated as unknown as { etag?: string | null }).etag ?? null };
                  }}
                  onStateChange={setSchemaEditorState}
                />
              ) : (
                <div className="validation-errors">
                  <p>Loading schema editor…</p>
                </div>
              )}
            </div>
          ) : (
            <div className="editor-raw">
              <div className="raw-format-selector">
                <label>Format:</label>
                <select value={format} onChange={(e) => setFormat(e.target.value as ContractFormat)}>
                  <option value="JSON">JSON</option>
                  <option value="YAML">YAML</option>
                </select>
              </div>
              <textarea
                className="raw-editor"
                value={rawContent}
                onChange={(e) => setRawContent(e.target.value)}
                spellCheck={false}
              />
            </div>
          )}
        </div>

        <div className="validation-panel">
          <h3>Validation</h3>
          {validationResult ? (
            <div className={`validation-result ${validationResult.valid ? 'valid' : 'invalid'}`}>
              {validationResult.valid ? (
                <div className="validation-success">
                  <p>✓ Contract is valid</p>
                </div>
              ) : (
                <div className="validation-errors">
                  <p>✗ Contract has errors:</p>
                  <ul>
                    {validationResult.errors?.map((err, idx) => (
                      <li key={idx}>
                        {err.field && <strong>{err.field}:</strong>} {err.message}
                      </li>
                    ))}
                  </ul>
                  {validationResult.warnings && validationResult.warnings.length > 0 && (
                    <>
                      <p>Warnings:</p>
                      <ul>
                        {validationResult.warnings.map((warn, idx) => (
                          <li key={idx} className="warning">
                            {warn.field && <strong>{warn.field}:</strong>} {warn.message}
                          </li>
                        ))}
                      </ul>
                    </>
                  )}
                </div>
              )}
            </div>
          ) : (
            <p className="validation-placeholder">Click "Validate" to check the contract</p>
          )}
        </div>
      </div>

      {updateMutation.isError && (
        <ErrorDisplay error={updateMutation.error} title="Failed to update contract" onRetry={() => updateMutation.reset()} />
      )}
    </div>
  );
}
