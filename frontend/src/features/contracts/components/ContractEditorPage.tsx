/**
 * Contract Editor Page
 * Edit contract with form + raw YAML/JSON editor + validation panel
 */

import { useParams, useNavigate } from 'react-router-dom';
import { useContract, useUpdateContract, useValidateContract } from '../hooks/useContracts';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { useState, useEffect, useMemo, useCallback } from 'react';
import { ContractFormat, type ContractValidationResult } from '../../../shared/types/contracts';
import { ODPSProductForm, makeEmptyODPSFormData } from './ODPSProductForm';
import {
  parseODPSDocument,
  mergeODPSDocument,
  validateODPSFormData,
} from '../utils/odpsDocumentBuilder';
import type { ODPSFormData } from '../../../shared/types/odps';
import './ContractEditorPage.css';
import { Button } from '../../../shared/components/Button';

type EditMode = 'form' | 'structured' | 'raw';

export function ContractEditorPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
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
  }, [contract, parseRawIntoODPSForm]);

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
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                />
              </div>
              <div className="form-group">
                <label>Description</label>
                <textarea
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
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
