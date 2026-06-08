/**
 * 285.9.4.1 — useTransformationWizard hook.
 *
 * Manages the multi-step wizard state: direction, config, submit.
 */
import { useCallback, useState } from 'react';
import { useTransformationApi } from './useTransformationApi';

interface WizardState {
  direction: 'code-first' | 'contract-first' | null;
  config: Record<string, unknown>;
}

export function useTransformationWizard(pipelineId: string) {
  const api = useTransformationApi();
  const [state, setState] = useState<WizardState>({
    direction: null,
    config: {},
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const update = useCallback(
    (key: keyof WizardState, value: unknown) => {
      setState((prev) => ({ ...prev, [key]: value }));
    },
    [],
  );

  const submit = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      await api.updatePipeline(pipelineId, {
        warehouse_credential_ref: (state.config as Record<string, string>).warehouseCredentialRef,
        git_credential_ref: (state.config as Record<string, string>).gitCredentialRef,
        source_config: {
          git_repo_url: (state.config as Record<string, string>).gitUrl,
          target_name: (state.config as Record<string, string>).targetName ?? 'prod',
          dbt_timeout_seconds: parseInt(
            String((state.config as Record<string, string>).timeout ?? '3600'), 10,
          ),
        },
      });
      await api.executeDbt(pipelineId, '');
    } catch (err: unknown) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }, [pipelineId, state.config, api]);

  return { state, update, submit, loading, error };
}
