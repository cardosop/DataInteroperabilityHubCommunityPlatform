/**
 * Schema Matching Page
 * AI-powered schema matching between source and target schemas
 */

import { useState } from 'react';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import type { SchemaMatchingRequest } from '../../../shared/types/ai';
import { useSchemaMatching } from '../hooks/useAI';
import './SchemaMatchingPage.css';
import { Button } from '../../../shared/components/Button';

export function SchemaMatchingPage() {
  const [sourceSchema, setSourceSchema] = useState(
    '{\n  "properties": {\n    "customer_id": { "type": "string" },\n    "email": { "type": "string" },\n    "age": { "type": "number" }\n  }\n}'
  );
  const [targetSchema, setTargetSchema] = useState(
    '{\n  "properties": {\n    "id": { "type": "string" },\n    "email_address": { "type": "string" },\n    "years_old": { "type": "integer" }\n  }\n}'
  );
  const [context, setContext] = useState('');
  const [schemaError, setSchemaError] = useState<{ source?: string; target?: string }>({});

  const matchingMutation = useSchemaMatching();

  const validateJSON = (
    jsonString: string
  ): { valid: boolean; data?: Record<string, unknown>; error?: string } => {
    try {
      const parsed = JSON.parse(jsonString);
      if (typeof parsed !== 'object' || parsed === null) {
        return { valid: false, error: 'Schema must be a JSON object' };
      }
      return { valid: true, data: parsed };
    } catch (e) {
      return { valid: false, error: e instanceof Error ? e.message : 'Invalid JSON' };
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSchemaError({});

    // Validate source schema
    const sourceValidation = validateJSON(sourceSchema);
    if (!sourceValidation.valid) {
      setSchemaError({ source: sourceValidation.error });
      return;
    }

    // Validate target schema
    const targetValidation = validateJSON(targetSchema);
    if (!targetValidation.valid) {
      setSchemaError({ target: targetValidation.error });
      return;
    }

    // Build request
    const request: SchemaMatchingRequest = {
      source_schema: sourceValidation.data!,
      target_schema: targetValidation.data!,
    };

    // Add context if provided
    if (context.trim()) {
      try {
        const contextParsed = JSON.parse(context.trim());
        if (typeof contextParsed === 'object' && contextParsed !== null) {
          request.context = contextParsed;
        }
      } catch {
        // Context is optional, ignore parse errors
      }
    }

    try {
      await matchingMutation.mutateAsync(request);
    } catch (err) {
      // Error handled by mutation
      console.error('Schema matching failed:', err);
    }
  };

  const getMatchTypeBadgeClass = (matchType: string) => {
    switch (matchType) {
      case 'exact':
        return 'match-badge-exact';
      case 'fuzzy':
        return 'match-badge-fuzzy';
      case 'semantic':
        return 'match-badge-semantic';
      default:
        return 'match-badge-default';
    }
  };

  const formatConfidence = (confidence: number) => {
    return `${Math.round(confidence * 100)}%`;
  };

  return (
    <div className="schema-matching-page" data-testid="schema-matching-page">
      <div className="schema-matching-header">
        <h1>AI Schema Matching</h1>
        <p className="subtitle">
          Match fields between source and target schemas using AI-powered analysis
        </p>
      </div>

      <form onSubmit={handleSubmit} className="schema-matching-form">
        <div className="schema-inputs-container">
          <div className="schema-input-group">
            <label htmlFor="source-schema">
              Source Schema <span className="required">*</span>
            </label>
            <textarea
              id="source-schema"
              className={`schema-input ${schemaError.source ? 'error' : ''}`}
              value={sourceSchema}
              onChange={(e) => {
                setSourceSchema(e.target.value);
                if (schemaError.source) setSchemaError({ ...schemaError, source: undefined });
              }}
              rows={12}
              placeholder='{"properties": {"field1": {"type": "string"}}}'
            />
            {schemaError.source && <div className="schema-error">{schemaError.source}</div>}
          </div>

          <div className="schema-input-group">
            <label htmlFor="target-schema">
              Target Schema <span className="required">*</span>
            </label>
            <textarea
              id="target-schema"
              className={`schema-input ${schemaError.target ? 'error' : ''}`}
              value={targetSchema}
              onChange={(e) => {
                setTargetSchema(e.target.value);
                if (schemaError.target) setSchemaError({ ...schemaError, target: undefined });
              }}
              rows={12}
              placeholder='{"properties": {"field_a": {"type": "string"}}}'
            />
            {schemaError.target && <div className="schema-error">{schemaError.target}</div>}
          </div>
        </div>

        <div className="context-input-group">
          <label htmlFor="context">Context (Optional)</label>
          <textarea
            id="context"
            className="context-input"
            value={context}
            onChange={(e) => setContext(e.target.value)}
            rows={3}
            placeholder='{"domain": "customer_data", "notes": "Additional context for matching"}'
          />
          <small>Optional JSON object with domain, notes, or other context</small>
        </div>

        <div className="form-actions">
          <Button
 type="submit"
 variant="primary"
 disabled={matchingMutation.isPending || !sourceSchema.trim() || !targetSchema.trim()}>
            {matchingMutation.isPending ? 'Matching...' : 'Match Schemas'}
          </Button>
        </div>
      </form>

      {!!matchingMutation.error && (
        <ErrorDisplay
          error={matchingMutation.error}
          title="Schema matching failed"
          onRetry={() => matchingMutation.reset()}
        />
      )}

      {matchingMutation.isPending && (
        <div className="matching-loading">
          <LoadingSpinner message="Analyzing schemas and finding matches..." />
          <p className="loading-note">
            This may take up to 15 seconds. AI is analyzing field names, types, and semantic
            relationships.
          </p>
        </div>
      )}

      {matchingMutation.data && (
        <div className="matching-results" data-testid="schema-matching-results">
          <h2>Matching Results</h2>

          <div className="results-summary">
            <div className="summary-item">
              <span className="summary-label">Overall Confidence:</span>
              <span className="summary-value confidence-value">
                {formatConfidence(matchingMutation.data.confidence)}
              </span>
            </div>
            <div className="summary-item">
              <span className="summary-label">Matches Found:</span>
              <span className="summary-value">{matchingMutation.data.matches.length}</span>
            </div>
            <div className="summary-item">
              <span className="summary-label">Execution Time:</span>
              <span className="summary-value">{matchingMutation.data.execution_time_ms}ms</span>
            </div>
          </div>

          {matchingMutation.data.matches.length > 0 ? (
            <div className="matches-list">
              <h3>Field Matches</h3>
              <table className="matches-table">
                <thead>
                  <tr>
                    <th>Source Field</th>
                    <th>Target Field</th>
                    <th>Match Type</th>
                    <th>Confidence</th>
                  </tr>
                </thead>
                <tbody>
                  {matchingMutation.data.matches.map((match, index) => (
                    <tr key={index}>
                      <td className="field-name">{match.source_field}</td>
                      <td className="field-name">{match.target_field}</td>
                      <td>
                        <span className={`match-badge ${getMatchTypeBadgeClass(match.match_type)}`}>
                          {match.match_type}
                        </span>
                      </td>
                      <td className="confidence-cell">
                        <div className="confidence-bar-container">
                          <div
                            className="confidence-bar"
                            style={{ width: `${match.confidence * 100}%` }}
                          />
                          <span className="confidence-text">
                            {formatConfidence(match.confidence)}
                          </span>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="no-matches">
              <p>No matches found between the schemas.</p>
            </div>
          )}

          {matchingMutation.data.suggestions && matchingMutation.data.suggestions.length > 0 && (
            <div className="suggestions-section">
              <h3>Suggestions</h3>
              <ul className="suggestions-list">
                {matchingMutation.data.suggestions.map((suggestion, index) => (
                  <li key={index}>{suggestion}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
