/**
 * ESLint rule: `mutation-guards/no-mutation-isloading`
 *
 * W5.4 (R2-F5) — "adopt `isPending` everywhere; lint rule".
 *
 * Forbids destructuring `isLoading` out of a mutation hook
 * (`useMutation`, `useMutationWithNotification`, `useOptimisticMutation`,
 * and any `use*Mutation` convention). On React Query v5 `isLoading` is
 * the deprecated v4 alias; on MUTATIONS it is not the submit-state flag
 * the UI cares about — `isPending` is. A submit button keyed off
 * `isLoading` re-enables during background refetch races and invites
 * double submission.
 *
 * Queries (`useQuery`) keep `isLoading` legitimately (it means
 * `isPending && isFetching`) — this rule only looks at mutation hooks.
 *
 * Escape hatch: a site can opt out with
 * `// eslint-disable-next-line mutation-guards/no-mutation-isloading`
 * plus an inline justification, matching the e2e-guards convention.
 */

'use strict';

/**
 * Mutation-hook callee shapes: any `use*Mutation` hook — the certainty
 * boundary of a name-based rule without type information. Covers
 * `useMutation`, `useMutationWithNotification`, `useOptimisticMutation`
 * and every feature-local `useXxxMutation` convention. Query-like hook
 * names (useSavedSearches, useRecommendations, ...) are NOT flagged:
 * they may legitimately return a query's `isLoading`; a name-based rule
 * must not guess beyond the `Mutation` suffix.
 */
const WRAPPER_HOOKS = new Set(['useMutationWithNotification', 'useOptimisticMutation']);

function isMutationHookName(name) {
  return name.startsWith('use') && (name.endsWith('Mutation') || WRAPPER_HOOKS.has(name));
}

module.exports = {
  meta: {
    type: 'problem',
    docs: {
      description: 'Forbid isLoading destructured from mutation hooks; use isPending',
    },
    messages: {
      useIsPending:
        'Destructure `isPending` from {{ name }} — `isLoading` is the deprecated v4 alias and is NOT the submit-state flag on mutations.',
    },
    schema: [],
  },
  create(context) {
    return {
      VariableDeclarator(node) {
        const init = node.init;
        if (!init || init.type !== 'CallExpression') return;
        const callee = init.callee;
        const calleeName = callee.type === 'Identifier' ? callee.name : null;
        if (!calleeName || !isMutationHookName(calleeName)) return;
        if (!node.id || node.id.type !== 'ObjectPattern') return;

        const isLoadingProp = node.id.properties.find(
          (prop) =>
            prop &&
            prop.type === 'Property' &&
            prop.key.type === 'Identifier' &&
            prop.key.name === 'isLoading',
        );
        if (!isLoadingProp) return;

        context.report({
          node: isLoadingProp,
          messageId: 'useIsPending',
          data: { name: calleeName },
        });
      },
    };
  },
};
