/**
 * useJobCompletionToast — toast on long-job completion (278.F.2).
 *
 * Watches job/run status transitions from PENDING/RUNNING → terminal
 * (COMPLETED/SUCCEEDED/FAILED) and fires a toast with action links.
 */
import { useEffect, useRef } from 'react';
import { useToast } from '../../shared/components/Toast/useToast';

export interface JobState {
  status: string | undefined;
  resourceLabel?: string;   // e.g. "DQ run", "Compliance scan"
  resourceId?: string;
  viewUrl?: string;         // deep-link to view the result
}

interface JobCompletionToastOptions {
  /** The current job state. */
  job: JobState;
  /** Toast is only fired when enabled is true (e.g. after initial load). */
  enabled?: boolean;
}

const RUNNING_STATES = new Set(['PENDING', 'RUNNING', 'QUEUED', 'PROCESSING']);
const SUCCESS_STATES = new Set(['COMPLETED', 'SUCCEEDED', 'SUCCESS', 'ACTIVE']);
const FAILURE_STATES = new Set(['FAILED', 'ERROR', 'CANCELLED', 'DEAD_LETTER']);

export function useJobCompletionToast({ job, enabled = true }: JobCompletionToastOptions) {
  const toast = useToast();
  const prevStatusRef = useRef<string | undefined>(undefined);

  useEffect(() => {
    if (!enabled) return;
    const prev = prevStatusRef.current;
    const curr = job.status;

    // Only fire on transition from running → terminal
    if (!prev || prev === curr) {
      prevStatusRef.current = curr;
      return;
    }
    if (!RUNNING_STATES.has(prev ?? '')) {
      prevStatusRef.current = curr;
      return;
    }

    const label = job.resourceLabel ?? 'Job';
    const id = job.resourceId ?? '';

    if (SUCCESS_STATES.has(curr ?? '')) {
      toast.success(`${label} completed${id ? ` — ${id.slice(0, 8)}…` : ''}`);
    } else if (FAILURE_STATES.has(curr ?? '')) {
      toast.error(`${label} failed${id ? ` — ${id.slice(0, 8)}…` : ''}`);
    }

    prevStatusRef.current = curr;
  }, [job.status, enabled, toast, job.resourceLabel, job.resourceId]);
}
