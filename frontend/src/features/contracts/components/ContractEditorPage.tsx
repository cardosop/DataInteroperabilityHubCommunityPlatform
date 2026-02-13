/**
 * Contract Editor Page
 * Edit contract with form + raw YAML/JSON editor + validation panel
 */

import { useParams, useNavigate } from 'react-router-dom';
import { useContract, useUpdateContract, useValidateContract } from '../hooks/useContracts';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { useState, useEffect } from 'react';
import { ContractFormat } from '../../../shared/types/contracts';
import './ContractEditorPage.css';

export function ContractEditorPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: contract, isLoading, error, refetch } = useContract(id || null);
  const updateMutation = useUpdateContract();
  const validateMutation = useValidateContract();
  const [editMode, setEditMode] = useState<'form' | 'raw'>('form');
  const [formData, setFormData] = useState({ name: '', description: '' });
  const [rawContent, setRawContent] = useState('');
  const [format, setFormat] = useState<ContractFormat>(ContractFormat.JSON);
  const [validationResult, setValidationResult] = useState<any>(null);
  const [isValidating, setIsValidating] = useState(false);

  useEffect(() => {
    if (contract) {
      setFormData({ name: contract.name || '', description: contract.description || '' });
      setRawContent(contract.original_raw);
      setFormat(contract.original_format);
    }
  }, [contract]);

  const handleValidate = async () => {
    if (!id) return;
    setIsValidating(true);
    try {
      const result = await validateMutation.mutateAsync(id);
      setValidationResult(result);
    } catch (err) {
      // Error handled by mutation
    } finally {
      setIsValidating(false);
    }
  };

  const handleSave = async () => {
    if (!id) return;
    try {
      await updateMutation.mutateAsync({
        id,
        data: editMode === 'form'
          ? { name: formData.name, description: formData.description }
          : { original_raw: rawContent, original_format: format },
      });
      refetch();
    } catch (err) {
      // Error handled by mutation
    }
  };

  if (isLoading) return <LoadingSpinner message="Loading contract..." />;
  if (error || !contract) {
    return <ErrorDisplay error={error || new Error('Contract not found')} title="Failed to load contract" onRetry={() => refetch()} />;
  }

  return (
    <div className="contract-editor-page">
      <div className="contract-editor-header">
        <button onClick={() => navigate(`/contracts/${id}`)} className="btn-back" type="button">
          ← Back to Contract
        </button>
        <div className="editor-mode-toggle">
          <button
            onClick={() => setEditMode('form')}
            className={editMode === 'form' ? 'active' : ''}
            type="button"
          >
            Form
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
          <button
            onClick={handleValidate}
            disabled={isValidating}
            className="btn-secondary"
            type="button"
          >
            {isValidating ? 'Validating...' : 'Validate'}
          </button>
          <button
            onClick={handleSave}
            disabled={updateMutation.isPending}
            className="btn-primary"
            type="button"
          >
            {updateMutation.isPending ? 'Saving...' : 'Save'}
          </button>
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
                    {validationResult.errors?.map((err: any, idx: number) => (
                      <li key={idx}>
                        {err.field && <strong>{err.field}:</strong>} {err.message}
                      </li>
                    ))}
                  </ul>
                  {validationResult.warnings && validationResult.warnings.length > 0 && (
                    <>
                      <p>Warnings:</p>
                      <ul>
                        {validationResult.warnings.map((warn: any, idx: number) => (
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
