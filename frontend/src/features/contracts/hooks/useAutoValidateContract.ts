/**
 * useAutoValidateContract — dry-run validation triggered once per contract.
 *
 * Calls `POST /contracts/validate-draft/` exactly once per unique contract
 * id to surface immediate feedback after a contract is attached to an
 * asset. A `useRef<Set<string>>` records every id we have already
 * validated this session, so re-renders (and React 18 StrictMode's
 * double-invoked effects) do not re-call the endpoint. When the id
 * changes — e.g. the user attaches a different contract — the hook fires
 * once more for the new id.
 *
 * No side-effects on the backend: `validate-draft/` is a pure read-only
 * normalisation preview.
 */

import { useEffect, useRef, useState } from 'react';
import type {
  ContractFormat,
  DraftValidationResult,
} from '../../../shared/types/contracts';
import { contractService } from '../services/contractService';

export interface AutoValidateContractInput {
  id: string;
  original_raw: string;
  original_format: ContractFormat | string;
}

export type AutoValidateStatus =
  | 'idle'
  | 'validating'
  | 'valid'
  | 'warnings'
  | 'invalid'
  | 'error';

export interface AutoValidateContractResult {
  status: AutoValidateStatus;
  /** Raw backend payload once resolved (null while pending). */
  data: DraftValidationResult | null;
  /** Warning count; `0` when status !== "warnings". */
  warningCount: number;
  /** First error message joined with any additional, or empty string. */
  errorSummary: string;
}

export function useAutoValidateContract(
  input: AutoValidateContractInput | null,
): AutoValidateContractResult {
  const [status, setStatus] = useState<AutoValidateStatus>('idle');
  const [data, setData] = useState<DraftValidationResult | null>(null);
  // Each entry is a contract id we've already dispatched validation for.
  // StrictMode's double-invoke of effects + any parent re-render will find
  // the id already in the set and short-circuit.
  const validatedIds = useRef<Set<string>>(new Set());

  useEffect(() => {
    if (!input || !input.id || !input.original_raw) {
      setStatus('idle');
      setData(null);
      return;
    }
    if (validatedIds.current.has(input.id)) return;
    validatedIds.current.add(input.id);

    // StrictMode-safe guard: we cancel *state writes* from an aborted
    // effect run, and we *roll back* the id from the validated set if
    // the request had not yet completed when the effect was torn down.
    // Consequence: under React 18 StrictMode (dev double-invoke) we fire
    // two requests, but only the survivor's result is committed to
    // state. In production (no double-invoke) exactly one request fires.
    // The alternative — marking the id only on completion — would
    // re-fire after every re-render during the in-flight window, which
    // is worse.
    const currentId = input.id;
    let cancelled = false;
    let completed = false;
    setStatus('validating');
    setData(null);

    contractService
      .validateDraft({
        original_raw: input.original_raw,
        original_format: String(input.original_format),
      })
      .then((result) => {
        completed = true;
        if (cancelled) return;
        setData(result);
        if (!result.valid) {
          setStatus('invalid');
        } else if (result.normalization_warnings.length > 0) {
          setStatus('warnings');
        } else {
          setStatus('valid');
        }
      })
      .catch(() => {
        completed = true;
        if (cancelled) return;
        // Treat network/server failures separately from a semantic
        // "invalid contract" — the banner should not cry wolf on a
        // transient 500.
        setStatus('error');
      });

    return () => {
      cancelled = true;
      if (!completed) {
        // Release the guard so a remount can dispatch a fresh request.
        // The just-cancelled promise cannot write state, so consumers
        // observe at most one state transition per contract id.
        validatedIds.current.delete(currentId);
      }
    };
  }, [input?.id, input?.original_raw, input?.original_format]);

  const warningCount =
    status === 'warnings' ? data?.normalization_warnings.length ?? 0 : 0;
  const errorSummary =
    status === 'invalid' ? (data?.normalization_errors ?? []).join('; ') : '';

  return { status, data, warningCount, errorSummary };
}
