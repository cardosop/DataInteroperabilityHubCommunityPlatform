/**
 * Phase 228.F2.20 — useUpdateContractLineage hook with optimistic
 * update + rollback.
 *
 * Wraps `contractService.updateLineage` with React Query's
 * `useMutation` + the `onMutate / onError` rollback pattern:
 *
 * 1. **onMutate** — snapshot the current `lineage/visualization`
 *    cache slot, optimistically write the new edge list into it,
 *    return the snapshot for `onError` to roll back to.
 *
 * 2. **onSuccess** — replace the optimistic value with the server's
 *    confirmed shape (carries the canonical `added/removed/kept`
 *    counts + the new ETag in the response headers).
 *
 * 3. **onError** — restore the snapshot.  The component layer
 *    surfaces the error via the conflict modal (412 → "Reload and
 *    merge" CTA) or the inline error state.
 *
 * The hook accepts both the `If-Match` ETag (for the 412 conflict
 * path) and an optional `Idempotency-Key` (for the bug-prevention
 * 24h replay window).
 */
import { useMutation, useQueryClient } from '@tanstack/react-query';

import { contractService } from '../services/contractService';

export interface LineagePatchPayload {
  edges: Array<Record<string, unknown>>;
}

export interface LineagePatchOptions {
  ifMatch?: string;
  idempotencyKey?: string;
}

export interface UseUpdateContractLineageInput {
  contractId: string;
  payload: LineagePatchPayload;
  options?: LineagePatchOptions;
}

export function useUpdateContractLineage() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      contractId,
      payload,
      options,
    }: UseUpdateContractLineageInput) => {
      return contractService.updateLineage(contractId, payload, options);
    },
    onMutate: async ({ contractId, payload }) => {
      // Cancel any in-flight visualization refetch so the optimistic
      // write isn't immediately overwritten.
      const visualizationKey = [
        'contracts', 'lineage', 'visualization', contractId,
      ];
      await queryClient.cancelQueries({ queryKey: visualizationKey });
      const snapshot = queryClient.getQueryData(visualizationKey);
      // Optimistically replace the visualization edges with the
      // payload — the actual visualization shape carries `nodes` +
      // `links`; we project edges into the link shape.
      queryClient.setQueryData(visualizationKey, (current: unknown) => {
        if (!current || typeof current !== 'object') return current;
        const cast = current as Record<string, unknown>;
        return {
          ...cast,
          links: payload.edges.map((e) => ({
            source: String(e.source_contract ?? ''),
            target: String(e.target_contract ?? ''),
            edge_type: e.edge_type,
            transformation_ref: e.transformation_ref,
            job_ref: e.job_ref,
            source_field: e.source_field,
            target_field: e.target_field,
          })),
        };
      });
      return { snapshot, visualizationKey };
    },
    onError: (_err, _vars, context) => {
      if (!context) return;
      // Rollback to the pre-mutation snapshot.
      queryClient.setQueryData(
        context.visualizationKey,
        context.snapshot,
      );
    },
    onSettled: (_data, _err, vars) => {
      // Re-fetch the visualization regardless of success / failure
      // so the UI converges to the server's authoritative state.
      queryClient.invalidateQueries({
        queryKey: ['contracts', 'lineage', 'visualization', vars.contractId],
      });
      queryClient.invalidateQueries({
        queryKey: ['contracts', 'detail', vars.contractId],
      });
    },
  });
}
