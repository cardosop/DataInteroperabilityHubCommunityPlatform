/**
 * DQ React Query Hooks
 *
 * Phase 240.4.A — extended with hooks for advanced quality endpoints
 * (anomalies / trends / scorecards / root-cause-analysis) and DQ
 * alerting-rule CRUD.
 */

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useMutationWithNotification } from '../../../shared/hooks/useMutationWithNotification';
import { dqService } from '../services/dqService';
import type {
  DQAlertingRuleCreateRequest,
  DQAlertingRuleUpdateRequest,
  DQAnomaliesFilters,
  DQRootCauseFilters,
  DQRunCreateRequest,
  DQRunListFilters,
  DQTrendsFilters,
} from '../../../shared/types/dq';

export function useDQRuns(filters: DQRunListFilters = {}) {
  return useQuery({
    queryKey: ['dq', 'runs', 'list', filters],
    queryFn: () => dqService.list(filters),
    refetchInterval: (query) => {
      // Auto-refetch if there are running DQ runs
      const data = query.state.data;
      if (data?.results) {
        const hasRunningRuns = data.results.some(
          (run) => run.status === 'PENDING' || run.status === 'RUNNING'
        );
        return hasRunningRuns ? 2000 : false; // Poll every 2 seconds if running
      }
      return false;
    },
  });
}

export function useDQRun(id: string | null) {
  return useQuery({
    queryKey: ['dq', 'runs', 'detail', id],
    queryFn: () => dqService.getById(id!),
    enabled: !!id,
    refetchInterval: (query) => {
      // Auto-refetch if DQ run is running
      const run = query.state.data;
      if (run && (run.status === 'PENDING' || run.status === 'RUNNING')) {
        return 2000; // Poll every 2 seconds
      }
      return false;
    },
  });
}

export function useDQRunResults(id: string | null) {
  return useQuery({
    queryKey: ['dq', 'runs', 'results', id],
    queryFn: () => dqService.getResults(id!),
    enabled: !!id,
  });
}

export function useCreateDQRun() {
  const queryClient = useQueryClient();

  return useMutationWithNotification({
    mutationFn: (data: DQRunCreateRequest) => dqService.create(data),
    successMessage: 'DQ run created',
    errorMessage: 'Failed to create DQ run',
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dq', 'runs'] });
    },
  });
}

// ─── Phase 240.4.A.7 — Advanced quality endpoints ────────────────────

export function useDQAnomalies(filters: DQAnomaliesFilters = {}) {
  return useQuery({
    queryKey: ['dq', 'quality', 'anomalies', filters],
    queryFn: () => dqService.getAnomalies(filters),
  });
}

export function useDQTrends(filters: DQTrendsFilters = {}) {
  // The backend's ``calculate_trend`` returns ``[]`` when neither
  // ``asset_id`` nor ``dataset_id`` is supplied — gating the request
  // here avoids consuming a daily plan-limit budget for a guaranteed-
  // empty result.
  const enabled = !!(filters.asset_id || filters.dataset_id);
  return useQuery({
    queryKey: ['dq', 'quality', 'trends', filters],
    queryFn: () => dqService.getTrends(filters),
    enabled,
    // Trends are computationally heavier than anomalies (per-action
    // 30/min throttle on the backend); don't refetch on focus.
    refetchOnWindowFocus: false,
  });
}

export function useDQScorecards(
  filters: { asset_id?: string; time_range?: number } = {},
) {
  return useQuery({
    queryKey: ['dq', 'quality', 'scorecards', filters],
    queryFn: () => dqService.getScorecards(filters),
    refetchOnWindowFocus: false,
  });
}

export function useDQRootCauseAnalysis(filters: DQRootCauseFilters) {
  return useQuery({
    queryKey: ['dq', 'quality', 'root_cause', filters],
    queryFn: () => dqService.getRootCauseAnalysis(filters),
    // Tightest backend throttle (5/min); always wait for explicit
    // dq_run_id / asset_id before firing.
    enabled: !!(filters.dq_run_id || filters.asset_id),
    refetchOnWindowFocus: false,
  });
}

// ─── Phase 240.4.A.7 — DQAlertingRule CRUD ───────────────────────────

export function useDQAlertingRules(
  filters: { asset_id?: string; enabled?: boolean } = {},
) {
  return useQuery({
    queryKey: ['dq', 'alerting-rules', 'list', filters],
    queryFn: () => dqService.listAlertingRules(filters),
  });
}

export function useCreateDQAlertingRule() {
  const queryClient = useQueryClient();
  return useMutationWithNotification({
    mutationFn: (data: DQAlertingRuleCreateRequest) =>
      dqService.createAlertingRule(data),
    successMessage: 'Alerting rule created',
    errorMessage: 'Failed to create alerting rule',
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dq', 'alerting-rules'] });
    },
  });
}

export function useUpdateDQAlertingRule() {
  const queryClient = useQueryClient();
  return useMutationWithNotification({
    mutationFn: ({ id, data }: { id: string; data: DQAlertingRuleUpdateRequest }) =>
      dqService.updateAlertingRule(id, data),
    successMessage: 'Alerting rule updated',
    errorMessage: 'Failed to update alerting rule',
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dq', 'alerting-rules'] });
    },
  });
}

export function useDeleteDQAlertingRule() {
  const queryClient = useQueryClient();
  return useMutationWithNotification({
    mutationFn: (id: string) => dqService.deleteAlertingRule(id),
    successMessage: 'Alerting rule deleted',
    errorMessage: 'Failed to delete alerting rule',
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dq', 'alerting-rules'] });
    },
  });
}
