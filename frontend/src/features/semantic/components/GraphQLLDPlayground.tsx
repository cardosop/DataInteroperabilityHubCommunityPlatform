/**
 * GraphQL-LD Playground (Phase 230.13.9 / REQ-SEM-GQL-001).
 *
 * Minimal in-bundle playground — textarea + Run button + JSON
 * response viewer.  Reasons we don't ship the full ``graphiql``
 * library here:
 *
 * 1. ``graphiql`` pulls 600+ KB minified into the main bundle;
 *    Phase 230.13.10 caps growth at +5%.  An in-bundle minimal UI
 *    keeps the cost in the kilobytes range.
 * 2. The endpoint enforces depth ≤ 5 / complexity ≤ 100 / 10s
 *    timeout / 60 q/min — most of GraphiQL's affordances (subscriptions,
 *    persisted queries, prettier) are out-of-scope for a bounded
 *    surface.
 * 3. The component is lazy-loaded via ``React.lazy()`` from
 *    ``SemanticPage.tsx``, so even this minimal bundle never enters
 *    the main chunk for users who never click the tab.
 *
 * If a future operator needs the full GraphiQL UX, swap the body of
 * this file for a ``<GraphiQL>`` import — the lazy boundary is
 * unchanged.
 */

import { useCallback, useState } from 'react';
import { Button } from '../../../shared/components/Button';
import { CodeBlock } from '../../../shared/components/CodeBlock';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { apiClient } from '../../../shared/api/client';
import type { ApiError } from '../../../shared/types/api';
import { normalizeError } from '../../../shared/utils/errorUtils';

const DEFAULT_QUERY = `# Phase 230.13 — GraphQL-LD endpoint
# Depth ≤ 5, complexity ≤ 100, 10s timeout, 60 q/min throttle.
{
  assets {
    id
    name
  }
}
`;

interface GraphQLResponse {
  data?: unknown;
  errors?: Array<{ message: string; path?: string[] | null }>;
  detail?: string;
  code?: string;
}

export default function GraphQLLDPlayground() {
  const [query, setQuery] = useState<string>(DEFAULT_QUERY);
  const [variables, setVariables] = useState<string>('{}');
  const [response, setResponse] = useState<GraphQLResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  const onRun = useCallback(async () => {
    setError(null);
    setResponse(null);
    let parsedVars: unknown = undefined;
    if (variables.trim()) {
      try {
        parsedVars = JSON.parse(variables);
      } catch (e) {
        setError({
          error: {
            code: 'INVALID_VARIABLES',
            message: `Variables JSON is invalid: ${(e as Error).message}`,
            // Client-side validation error never went through the
            // backend, so http_status/request_id/timestamp don't exist
            // on a real wire response. Synthesise them so the shape
            // matches `ApiError` and downstream renderers don't have
            // to special-case client errors.
            http_status: 0,
            request_id: 'client',
            timestamp: new Date().toISOString(),
          },
        });
        return;
      }
    }
    setLoading(true);
    try {
      const result = await apiClient.getClient().post<GraphQLResponse>(
        'semantic/graphql',
        { query, variables: parsedVars ?? null },
        // Bypass the response-shape interceptor — GraphQL standard
        // shape is ``{ data, errors }`` and is decoded as-is.
        { headers: { 'Content-Type': 'application/json' } },
      );
      setResponse(result.data ?? null);
    } catch (e) {
      setError(normalizeError(e));
    } finally {
      setLoading(false);
    }
  }, [query, variables]);

  return (
    <section
      className="semantic-graphql-playground"
      data-testid="semantic-graphql-playground"
    >
      <h2>GraphQL-LD Playground</h2>
      <p className="semantic-tab-description">
        Authenticated GraphQL queries against your tenant&apos;s named graph.
        Subject to depth ≤ 5, complexity ≤ 100, 10s timeout, and 60 q/min
        throttle (REQ-SEM-GQL-001).
      </p>

      <div className="graphql-playground-grid">
        <div className="graphql-playground-input">
          <label htmlFor="graphql-query-input">
            <span>Query</span>
            <textarea
              id="graphql-query-input"
              data-testid="graphql-query-input"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              rows={14}
              spellCheck={false}
              className="graphql-playground-textarea"
              aria-label="GraphQL query"
            />
          </label>

          <label htmlFor="graphql-variables-input">
            <span>Variables (JSON)</span>
            <textarea
              id="graphql-variables-input"
              data-testid="graphql-variables-input"
              value={variables}
              onChange={(e) => setVariables(e.target.value)}
              rows={4}
              spellCheck={false}
              className="graphql-playground-textarea"
              aria-label="GraphQL variables JSON"
            />
          </label>

          <div className="graphql-playground-actions">
            <Button
              variant="primary"
              onClick={onRun}
              disabled={loading}
              data-testid="graphql-run-button"
            >
              {loading ? 'Running…' : 'Run'}
            </Button>
          </div>
        </div>

        <div className="graphql-playground-output">
          <h3>Response</h3>
          {error && (
            <ErrorDisplay error={error} title="GraphQL request failed" />
          )}
          {response && (
            <CodeBlock
              code={JSON.stringify(response, null, 2)}
              language="json"
              data-testid="graphql-response-block"
            />
          )}
          {!response && !error && !loading && (
            <p className="semantic-tab-empty">
              Click <strong>Run</strong> to execute the query.
            </p>
          )}
        </div>
      </div>
    </section>
  );
}
