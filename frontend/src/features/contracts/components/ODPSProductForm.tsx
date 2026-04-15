/**
 * ODPSProductForm — guided, form-based editor for Bitol ODPS v1.0.0 data
 * products. Owns a controlled ODPSFormData snapshot that the parent renders
 * and submits; collaborates with odpsDocumentBuilder for preview + validation.
 *
 * Layout:
 *  1. Product Details (required)
 *  2. Team (dynamic list)
 *  3. Data Schema (dynamic list — input schemas)
 *  4. Quality & SLA (collapsible)
 *  5. Marketplace (collapsible)
 *  6. Linking (AssetPicker + ContractPicker)
 *  + Live preview panel showing generated JSON or YAML.
 */

import { useMemo, useState, useCallback } from 'react';
import { AssetPicker, ContractPicker } from '../../../shared/components/pickers';
import { Button } from '../../../shared/components/Button';
import {
  buildODPSDocument,
  validateODPSFormData,
  BITOL_V1_SCHEMA_URL,
  type OutputFormat,
  type ValidationError,
} from '../utils/odpsDocumentBuilder';
import type {
  ODPSFormData,
  ODPSTeamMember,
  ODPSPort,
  ODPSInputSchema,
  ODPSQualityRule,
  ODPSSLAProperty,
  ODPSSchemaField,
} from '../../../shared/types/odps';
import './ODPSProductForm.css';

export interface ODPSProductFormProps {
  value: ODPSFormData;
  onChange: (next: ODPSFormData) => void;
  previewFormat?: OutputFormat;
  disabled?: boolean;
}

export function makeEmptyODPSFormData(): ODPSFormData {
  return {
    schema: BITOL_V1_SCHEMA_URL,
    apiVersion: 'v1.0.0',
    kind: 'DataProduct',
    language: 'en',
    productID: '',
    productName: '',
    productVersion: '1.0.0',
    productStatus: 'draft',
    productDescription: '',
    productDomain: '',
    productTenant: '',
    productVisibility: 'internal',
    productCategory: undefined,
    productType: undefined,
    team: [],
    outputPorts: [],
    inputPorts: [],
    inputSchemas: [],
    slaProperties: [],
    qualityRules: [],
    tags: [],
    categories: [],
    price: undefined,
    currency: undefined,
    licenseType: undefined,
    marketplaceListed: false,
    marketplaceDescription: undefined,
    linkedAssetId: null,
    linkedContractId: null,
  };
}

export function ODPSProductForm({
  value,
  onChange,
  previewFormat = 'YAML',
  disabled = false,
}: ODPSProductFormProps) {
  const [format, setFormat] = useState<OutputFormat>(previewFormat);
  const [qualityOpen, setQualityOpen] = useState(false);
  const [marketplaceOpen, setMarketplaceOpen] = useState(false);

  const errors = useMemo(() => validateODPSFormData(value), [value]);
  const errorByField = useMemo(() => {
    const map = new Map<string, string>();
    errors.forEach((e: ValidationError) => {
      if (!map.has(e.field)) map.set(e.field, e.message);
    });
    return map;
  }, [errors]);

  const preview = useMemo(() => {
    try {
      return buildODPSDocument(value, format);
    } catch (err) {
      return `# Preview error: ${(err as Error).message}`;
    }
  }, [value, format]);

  const set = useCallback(
    <K extends keyof ODPSFormData>(key: K, v: ODPSFormData[K]) => {
      onChange({ ...value, [key]: v });
    },
    [value, onChange],
  );

  // ---------------- Team ----------------
  const addTeamMember = () =>
    set('team', [...value.team, { name: '', email: '', role: '' }]);
  const updateTeamMember = (i: number, patch: Partial<ODPSTeamMember>) =>
    set(
      'team',
      value.team.map((m, idx) => (idx === i ? { ...m, ...patch } : m)),
    );
  const removeTeamMember = (i: number) =>
    set('team', value.team.filter((_, idx) => idx !== i));

  // ---------------- Output ports ----------------
  const addOutputPort = () =>
    set('outputPorts', [...value.outputPorts, { name: '', contractId: '', tags: [] }]);
  const updateOutputPort = (i: number, patch: Partial<ODPSPort>) =>
    set(
      'outputPorts',
      value.outputPorts.map((p, idx) => (idx === i ? { ...p, ...patch } : p)),
    );
  const removeOutputPort = (i: number) =>
    set('outputPorts', value.outputPorts.filter((_, idx) => idx !== i));

  // ---------------- Input schemas ----------------
  const addInputSchema = () =>
    set('inputSchemas', [...value.inputSchemas, { name: '', fields: [] }]);
  const updateInputSchema = (i: number, patch: Partial<ODPSInputSchema>) =>
    set(
      'inputSchemas',
      value.inputSchemas.map((s, idx) => (idx === i ? { ...s, ...patch } : s)),
    );
  const removeInputSchema = (i: number) =>
    set('inputSchemas', value.inputSchemas.filter((_, idx) => idx !== i));
  const addSchemaField = (schemaIdx: number) =>
    updateInputSchema(schemaIdx, {
      fields: [...value.inputSchemas[schemaIdx].fields, { name: '', type: 'string' }],
    });
  const updateSchemaField = (
    schemaIdx: number,
    fieldIdx: number,
    patch: Partial<ODPSSchemaField>,
  ) =>
    updateInputSchema(schemaIdx, {
      fields: value.inputSchemas[schemaIdx].fields.map((f, idx) =>
        idx === fieldIdx ? { ...f, ...patch } : f,
      ),
    });
  const removeSchemaField = (schemaIdx: number, fieldIdx: number) =>
    updateInputSchema(schemaIdx, {
      fields: value.inputSchemas[schemaIdx].fields.filter((_, idx) => idx !== fieldIdx),
    });

  // ---------------- Quality / SLA ----------------
  const addSLA = () =>
    set('slaProperties', [
      ...value.slaProperties,
      { property: '', value: '' } as ODPSSLAProperty,
    ]);
  const updateSLA = (i: number, patch: Partial<ODPSSLAProperty>) =>
    set(
      'slaProperties',
      value.slaProperties.map((s, idx) => (idx === i ? { ...s, ...patch } : s)),
    );
  const removeSLA = (i: number) =>
    set('slaProperties', value.slaProperties.filter((_, idx) => idx !== i));
  const addQuality = () =>
    set('qualityRules', [...value.qualityRules, { name: '' } as ODPSQualityRule]);
  const updateQuality = (i: number, patch: Partial<ODPSQualityRule>) =>
    set(
      'qualityRules',
      value.qualityRules.map((q, idx) => (idx === i ? { ...q, ...patch } : q)),
    );
  const removeQuality = (i: number) =>
    set('qualityRules', value.qualityRules.filter((_, idx) => idx !== i));

  const updateTags = (raw: string) =>
    set(
      'tags',
      raw.split(',').map((t) => t.trim()).filter(Boolean),
    );
  const updateCategories = (raw: string) =>
    set(
      'categories',
      raw.split(',').map((t) => t.trim()).filter(Boolean),
    );

  return (
    <div className="odps-product-form">
      <div className="odps-product-form__editor">
        {/* ----- Product Details ----- */}
        <section className="form-section" aria-labelledby="odps-section-details">
          <h2 id="odps-section-details">Product Details</h2>

          <div className="odps-grid-2">
            <div className="form-group">
              <label htmlFor="odps-productID">
                Product ID <span className="required">*</span>
              </label>
              <input
                id="odps-productID"
                type="text"
                value={value.productID}
                disabled={disabled}
                onChange={(e) => set('productID', e.target.value)}
                className={errorByField.has('productID') ? 'error' : ''}
                aria-invalid={errorByField.has('productID')}
              />
              {errorByField.has('productID') && (
                <span className="error-message">{errorByField.get('productID')}</span>
              )}
            </div>

            <div className="form-group">
              <label htmlFor="odps-productName">
                Name <span className="required">*</span>
              </label>
              <input
                id="odps-productName"
                type="text"
                value={value.productName}
                disabled={disabled}
                onChange={(e) => set('productName', e.target.value)}
                className={errorByField.has('productName') ? 'error' : ''}
                aria-invalid={errorByField.has('productName')}
              />
              {errorByField.has('productName') && (
                <span className="error-message">{errorByField.get('productName')}</span>
              )}
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="odps-productDescription">Description</label>
            <textarea
              id="odps-productDescription"
              rows={3}
              value={value.productDescription}
              disabled={disabled}
              onChange={(e) => set('productDescription', e.target.value)}
            />
          </div>

          <div className="odps-grid-3">
            <div className="form-group">
              <label htmlFor="odps-language">Language</label>
              <input
                id="odps-language"
                type="text"
                value={value.language}
                disabled={disabled}
                onChange={(e) => set('language', e.target.value)}
                placeholder="en"
              />
            </div>
            <div className="form-group">
              <label htmlFor="odps-productVersion">Version</label>
              <input
                id="odps-productVersion"
                type="text"
                value={value.productVersion}
                disabled={disabled}
                onChange={(e) => set('productVersion', e.target.value)}
              />
            </div>
            <div className="form-group">
              <label htmlFor="odps-productStatus">Status</label>
              <select
                id="odps-productStatus"
                value={value.productStatus}
                disabled={disabled}
                onChange={(e) => set('productStatus', e.target.value)}
              >
                <option value="draft">draft</option>
                <option value="active">active</option>
                <option value="deprecated">deprecated</option>
                <option value="retired">retired</option>
              </select>
            </div>
          </div>

          <div className="odps-grid-3">
            <div className="form-group">
              <label htmlFor="odps-productDomain">Domain</label>
              <input
                id="odps-productDomain"
                type="text"
                value={value.productDomain}
                disabled={disabled}
                onChange={(e) => set('productDomain', e.target.value)}
              />
            </div>
            <div className="form-group">
              <label htmlFor="odps-productTenant">Tenant</label>
              <input
                id="odps-productTenant"
                type="text"
                value={value.productTenant}
                disabled={disabled}
                onChange={(e) => set('productTenant', e.target.value)}
              />
            </div>
            <div className="form-group">
              <label htmlFor="odps-productVisibility">Visibility</label>
              <select
                id="odps-productVisibility"
                value={value.productVisibility}
                disabled={disabled}
                onChange={(e) => set('productVisibility', e.target.value)}
              >
                <option value="private">private</option>
                <option value="internal">internal</option>
                <option value="public">public</option>
              </select>
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="odps-schema">Schema URL</label>
            <input
              id="odps-schema"
              type="text"
              value={value.schema}
              disabled={disabled}
              onChange={(e) => set('schema', e.target.value)}
              className={errorByField.has('schema') ? 'error' : ''}
              aria-invalid={errorByField.has('schema')}
            />
            {errorByField.has('schema') && (
              <span className="error-message">{errorByField.get('schema')}</span>
            )}
          </div>
        </section>

        {/* ----- Team ----- */}
        <section className="form-section" aria-labelledby="odps-section-team">
          <div className="odps-section-header">
            <h2 id="odps-section-team">Team</h2>
            <Button variant="secondary" onClick={addTeamMember} disabled={disabled}>
              + Add Member
            </Button>
          </div>
          {value.team.length === 0 && (
            <p className="odps-empty-hint">No team members yet.</p>
          )}
          {value.team.map((member, i) => (
            <div className="odps-row" key={i}>
              <input
                type="text"
                placeholder="Name"
                value={member.name}
                disabled={disabled}
                onChange={(e) => updateTeamMember(i, { name: e.target.value })}
                aria-label={`Team member ${i + 1} name`}
              />
              <input
                type="email"
                placeholder="Email"
                value={member.email}
                disabled={disabled}
                onChange={(e) => updateTeamMember(i, { email: e.target.value })}
                aria-label={`Team member ${i + 1} email`}
              />
              <input
                type="text"
                placeholder="Role"
                value={member.role ?? ''}
                disabled={disabled}
                onChange={(e) => updateTeamMember(i, { role: e.target.value })}
                aria-label={`Team member ${i + 1} role`}
              />
              <Button variant="ghost" onClick={() => removeTeamMember(i)} disabled={disabled}>
                Remove
              </Button>
            </div>
          ))}
        </section>

        {/* ----- Data Schema (output ports + input schemas) ----- */}
        <section className="form-section" aria-labelledby="odps-section-schema">
          <div className="odps-section-header">
            <h2 id="odps-section-schema">Data Schema</h2>
          </div>

          <h3 className="odps-subheading">Output Ports</h3>
          <div className="odps-inline-actions">
            <Button variant="secondary" onClick={addOutputPort} disabled={disabled}>
              + Add Output Port
            </Button>
          </div>
          {value.outputPorts.length === 0 && (
            <p className="odps-empty-hint">No output ports defined.</p>
          )}
          {value.outputPorts.map((port, i) => (
            <div className="odps-row" key={i}>
              <input
                type="text"
                placeholder="Port name"
                value={port.name}
                disabled={disabled}
                onChange={(e) => updateOutputPort(i, { name: e.target.value })}
                aria-label={`Output port ${i + 1} name`}
              />
              <input
                type="text"
                placeholder="Contract ID (optional)"
                value={port.contractId ?? ''}
                disabled={disabled}
                onChange={(e) => updateOutputPort(i, { contractId: e.target.value })}
                aria-label={`Output port ${i + 1} contractId`}
              />
              <input
                type="text"
                placeholder="tags (comma separated)"
                value={(port.tags ?? []).join(', ')}
                disabled={disabled}
                onChange={(e) =>
                  updateOutputPort(i, {
                    tags: e.target.value.split(',').map((t) => t.trim()).filter(Boolean),
                  })
                }
                aria-label={`Output port ${i + 1} tags`}
              />
              <Button variant="ghost" onClick={() => removeOutputPort(i)} disabled={disabled}>
                Remove
              </Button>
            </div>
          ))}

          <h3 className="odps-subheading">Input Schemas</h3>
          <div className="odps-inline-actions">
            <Button variant="secondary" onClick={addInputSchema} disabled={disabled}>
              + Add Schema
            </Button>
          </div>
          {value.inputSchemas.length === 0 && (
            <p className="odps-empty-hint">No input schemas defined.</p>
          )}
          {value.inputSchemas.map((schema, i) => (
            <div className="odps-subsection" key={i}>
              <div className="odps-row">
                <input
                  type="text"
                  placeholder="Schema name"
                  value={schema.name}
                  disabled={disabled}
                  onChange={(e) => updateInputSchema(i, { name: e.target.value })}
                  aria-label={`Schema ${i + 1} name`}
                />
                <Button variant="ghost" onClick={() => removeInputSchema(i)} disabled={disabled}>
                  Remove Schema
                </Button>
              </div>
              <div className="odps-inline-actions">
                <Button
                  variant="secondary"
                  onClick={() => addSchemaField(i)}
                  disabled={disabled}
                >
                  + Add Field
                </Button>
              </div>
              {schema.fields.map((field, fi) => (
                <div className="odps-row" key={fi}>
                  <input
                    type="text"
                    placeholder="Field name"
                    value={field.name}
                    disabled={disabled}
                    onChange={(e) => updateSchemaField(i, fi, { name: e.target.value })}
                    aria-label={`Schema ${i + 1} field ${fi + 1} name`}
                  />
                  <input
                    type="text"
                    placeholder="Type"
                    value={field.type}
                    disabled={disabled}
                    onChange={(e) => updateSchemaField(i, fi, { type: e.target.value })}
                    aria-label={`Schema ${i + 1} field ${fi + 1} type`}
                  />
                  <label className="odps-inline-check">
                    <input
                      type="checkbox"
                      checked={!!field.required}
                      disabled={disabled}
                      onChange={(e) =>
                        updateSchemaField(i, fi, { required: e.target.checked })
                      }
                    />
                    required
                  </label>
                  <Button
                    variant="ghost"
                    onClick={() => removeSchemaField(i, fi)}
                    disabled={disabled}
                  >
                    Remove
                  </Button>
                </div>
              ))}
            </div>
          ))}
        </section>

        {/* ----- Quality & SLA ----- */}
        <section className="form-section form-section--collapsible">
          <button
            type="button"
            className="odps-collapse-toggle"
            onClick={() => setQualityOpen((o) => !o)}
            aria-expanded={qualityOpen}
          >
            <span>Quality & SLA</span>
            <span aria-hidden="true">{qualityOpen ? '−' : '+'}</span>
          </button>
          {qualityOpen && (
            <div className="odps-collapse-body">
              <h3 className="odps-subheading">SLA Properties</h3>
              <div className="odps-inline-actions">
                <Button variant="secondary" onClick={addSLA} disabled={disabled}>
                  + Add SLA
                </Button>
              </div>
              {value.slaProperties.map((sla, i) => (
                <div className="odps-row" key={i}>
                  <input
                    type="text"
                    placeholder="Property (e.g. availability)"
                    value={sla.property}
                    disabled={disabled}
                    onChange={(e) => updateSLA(i, { property: e.target.value })}
                  />
                  <input
                    type="text"
                    placeholder="Value"
                    value={sla.value}
                    disabled={disabled}
                    onChange={(e) => updateSLA(i, { value: e.target.value })}
                  />
                  <input
                    type="text"
                    placeholder="Unit"
                    value={sla.unit ?? ''}
                    disabled={disabled}
                    onChange={(e) => updateSLA(i, { unit: e.target.value })}
                  />
                  <Button variant="ghost" onClick={() => removeSLA(i)} disabled={disabled}>
                    Remove
                  </Button>
                </div>
              ))}

              <h3 className="odps-subheading">Quality Rules</h3>
              <div className="odps-inline-actions">
                <Button variant="secondary" onClick={addQuality} disabled={disabled}>
                  + Add Rule
                </Button>
              </div>
              {value.qualityRules.map((rule, i) => (
                <div className="odps-row" key={i}>
                  <input
                    type="text"
                    placeholder="Rule name"
                    value={rule.name}
                    disabled={disabled}
                    onChange={(e) => updateQuality(i, { name: e.target.value })}
                  />
                  <input
                    type="text"
                    placeholder="Type"
                    value={rule.type ?? ''}
                    disabled={disabled}
                    onChange={(e) => updateQuality(i, { type: e.target.value })}
                  />
                  <input
                    type="text"
                    placeholder="Expression"
                    value={rule.expression ?? ''}
                    disabled={disabled}
                    onChange={(e) => updateQuality(i, { expression: e.target.value })}
                  />
                  <Button variant="ghost" onClick={() => removeQuality(i)} disabled={disabled}>
                    Remove
                  </Button>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* ----- Marketplace ----- */}
        <section className="form-section form-section--collapsible">
          <button
            type="button"
            className="odps-collapse-toggle"
            onClick={() => setMarketplaceOpen((o) => !o)}
            aria-expanded={marketplaceOpen}
          >
            <span>Marketplace</span>
            <span aria-hidden="true">{marketplaceOpen ? '−' : '+'}</span>
          </button>
          {marketplaceOpen && (
            <div className="odps-collapse-body">
              <div className="form-group">
                <label>
                  <input
                    type="checkbox"
                    checked={value.marketplaceListed}
                    disabled={disabled}
                    onChange={(e) => set('marketplaceListed', e.target.checked)}
                  />{' '}
                  List on marketplace
                </label>
              </div>
              <div className="odps-grid-2">
                <div className="form-group">
                  <label htmlFor="odps-price">Price</label>
                  <input
                    id="odps-price"
                    type="number"
                    step="0.01"
                    value={value.price ?? ''}
                    disabled={disabled || !value.marketplaceListed}
                    onChange={(e) =>
                      set('price', e.target.value ? Number(e.target.value) : undefined)
                    }
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="odps-currency">Currency</label>
                  <input
                    id="odps-currency"
                    type="text"
                    value={value.currency ?? ''}
                    disabled={disabled || !value.marketplaceListed}
                    onChange={(e) => set('currency', e.target.value || undefined)}
                    placeholder="USD"
                  />
                </div>
              </div>
              <div className="form-group">
                <label htmlFor="odps-license">License Type</label>
                <input
                  id="odps-license"
                  type="text"
                  value={value.licenseType ?? ''}
                  disabled={disabled || !value.marketplaceListed}
                  onChange={(e) => set('licenseType', e.target.value || undefined)}
                />
              </div>
              <div className="form-group">
                <label htmlFor="odps-marketplace-description">Marketplace Description</label>
                <textarea
                  id="odps-marketplace-description"
                  rows={2}
                  value={value.marketplaceDescription ?? ''}
                  disabled={disabled || !value.marketplaceListed}
                  onChange={(e) =>
                    set('marketplaceDescription', e.target.value || undefined)
                  }
                />
              </div>
              <div className="form-group">
                <label htmlFor="odps-tags">Tags (comma-separated)</label>
                <input
                  id="odps-tags"
                  type="text"
                  value={value.tags.join(', ')}
                  disabled={disabled}
                  onChange={(e) => updateTags(e.target.value)}
                />
              </div>
              <div className="form-group">
                <label htmlFor="odps-categories">Categories (comma-separated)</label>
                <input
                  id="odps-categories"
                  type="text"
                  value={value.categories.join(', ')}
                  disabled={disabled}
                  onChange={(e) => updateCategories(e.target.value)}
                />
              </div>
            </div>
          )}
        </section>

        {/* ----- Linking ----- */}
        <section className="form-section" aria-labelledby="odps-section-linking">
          <h2 id="odps-section-linking">Linking</h2>
          <div className="form-group">
            <label>Linked Asset</label>
            <AssetPicker
              value={value.linkedAssetId}
              onChange={(id) => set('linkedAssetId', id)}
              disabled={disabled}
              data-testid="odps-asset-picker"
            />
          </div>
          <div className="form-group">
            <label>Linked Contract (ODCS)</label>
            <ContractPicker
              value={value.linkedContractId}
              onChange={(id) => set('linkedContractId', id)}
              disabled={disabled}
              specType="ODCS"
              data-testid="odps-contract-picker"
            />
          </div>
        </section>
      </div>

      {/* ----- Live preview ----- */}
      <aside className="odps-product-form__preview" aria-label="Document preview">
        <div className="odps-preview-header">
          <h3>Preview</h3>
          <div className="odps-preview-format">
            <label>
              <input
                type="radio"
                name="odps-preview-format"
                value="YAML"
                checked={format === 'YAML'}
                onChange={() => setFormat('YAML')}
              />
              YAML
            </label>
            <label>
              <input
                type="radio"
                name="odps-preview-format"
                value="JSON"
                checked={format === 'JSON'}
                onChange={() => setFormat('JSON')}
              />
              JSON
            </label>
          </div>
        </div>
        <pre className="odps-preview-body" data-testid="odps-preview">
          {preview}
        </pre>
        {errors.length > 0 && (
          <div className="odps-preview-errors">
            <strong>Validation errors:</strong>
            <ul>
              {errors.map((e, i) => (
                <li key={i}>
                  <code>{e.field}</code>: {e.message}
                </li>
              ))}
            </ul>
          </div>
        )}
      </aside>
    </div>
  );
}
