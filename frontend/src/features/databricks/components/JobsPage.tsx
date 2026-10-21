/**
 * Databricks jobs page (openspec add-databricks-jobs task 4.5) — the U5
 * job-fleet surface.
 *
 * Lists the workspace's mirrored jobs (the 4.2 mirror — zero network
 * reads) with their reported task configuration and schedule, and
 * expands a job to render its mirrored runs — every lifecycle/result
 * state is the jobs API's REPORTED value, never invented (the mirror
 * contract). A failed load renders the machine-readable CODE in the
 * alert; the flag-off 403 surfaces the distinct banner.
 */
import { useCallback, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';

import { useTranslation } from '../../../shared/i18n/useTranslation';

import type { DatabricksJob, DatabricksJobRun } from '@/shared/types/databricks';

import { DatabricksApiError, listJobRuns, listJobs } from '../services/jobsService';

const FLAG_DISABLED_CODE = 'DATABRICKS_CONTROL_PLANE_DISABLED';

export function JobsPage(): React.ReactElement {
  const { workspaceId } = useParams<{ workspaceId: string }>();
  const { t } = useTranslation();
  const [jobs, setJobs] = useState<DatabricksJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [flagDisabled, setFlagDisabled] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedJobId, setExpandedJobId] = useState<string | null>(null);
  const [runs, setRuns] = useState<DatabricksJobRun[]>([]);
  const [runsLoading, setRunsLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    setFlagDisabled(false);
    setExpandedJobId(null);
    setRuns([]);
    try {
      setJobs(await listJobs(workspaceId ?? ''));
    } catch (e) {
      if (e instanceof DatabricksApiError && e.code === FLAG_DISABLED_CODE) {
        setFlagDisabled(true);
        setJobs([]);
      } else {
        const code = e instanceof DatabricksApiError ? e.code : undefined;
        const message = e instanceof Error ? e.message : String(e);
        setError(code ? `[${code}] ${message}` : message);
      }
    } finally {
      setLoading(false);
    }
  }, [workspaceId]);

  useEffect(() => {
    void load();
  }, [load]);

  const toggleRuns = async (jobId: string) => {
    if (expandedJobId === jobId) {
      setExpandedJobId(null);
      setRuns([]);
      return;
    }
    setExpandedJobId(jobId);
    setRuns([]);
    setRunsLoading(true);
    try {
      setRuns(await listJobRuns(workspaceId ?? '', jobId));
    } catch (e) {
      const code = e instanceof DatabricksApiError ? e.code : undefined;
      const message = e instanceof Error ? e.message : String(e);
      setError(code ? `[${code}] ${message}` : message);
      setExpandedJobId(null);
    } finally {
      setRunsLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="job-list">{t('databricks.jobs.loading', 'Loading Databricks jobs…')}</div>
    );
  }

  if (flagDisabled) {
    return (
      <div role="alert" data-testid="flag-disabled-banner">
        <h2>{t('databricks.jobs.title', 'Databricks jobs')}</h2>
        <p>
          {t('databricks.page.flag_disabled_body', 'The Databricks control plane is disabled for this tenant.')}{' '}
          <code>{FLAG_DISABLED_CODE}</code>
        </p>
      </div>
    );
  }

  return (
    <div className="job-list">
      <div className="job-list-header">
        <h2>{t('databricks.jobs.title', 'Databricks jobs')}</h2>
        <button type="button" onClick={() => void load()} disabled={loading}>
          {t('databricks.jobs.refresh', 'Refresh')}
        </button>
      </div>

      {error && (
        <div role="alert" className="job-error" data-testid="action-error">
          {error}
        </div>
      )}

      {jobs.length === 0 ? (
        <p>{t('databricks.jobs.empty', 'No jobs reported for this workspace yet.')}</p>
      ) : (
        <table aria-label={t('databricks.jobs.title', 'Databricks jobs')}>
          <thead>
            <tr>
              <th>{t('databricks.jobs.name', 'Name')}</th>
              <th>{t('databricks.jobs.schedule', 'Schedule')}</th>
              <th>{t('databricks.jobs.tasks', 'Tasks')}</th>
              <th>{t('databricks.jobs.actions', 'Actions')}</th>
            </tr>
          </thead>
          <tbody>
            {jobs.map((job) => (
              <JobRow
                key={job.job_id}
                job={job}
                expanded={expandedJobId === job.job_id}
                runsLoading={runsLoading}
                runs={runs}
                onToggleRuns={() => void toggleRuns(job.job_id)}
                t={t}
              />
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function JobRow({
  job,
  expanded,
  runsLoading,
  runs,
  onToggleRuns,
  t,
}: {
  job: DatabricksJob;
  expanded: boolean;
  runsLoading: boolean;
  runs: DatabricksJobRun[];
  onToggleRuns: () => void;
  t: (key: string, fallback?: string) => string;
}): React.ReactElement {
  const taskCount = Array.isArray(job.task_config) ? job.task_config.length : 0;
  return (
    <>
      <tr data-job={job.job_id} aria-busy={runsLoading && expanded}>
        <td>{job.name}</td>
        <td>
          {job.schedule
            ? t('databricks.jobs.scheduled', 'scheduled')
            : t('databricks.jobs.unscheduled', 'unscheduled')}
        </td>
        <td>{taskCount}</td>
        <td>
          <button type="button" data-job-id={job.job_id} onClick={onToggleRuns}>
            {expanded
              ? t('databricks.jobs.hide_runs', 'Hide runs')
              : t('databricks.jobs.view_runs', 'View runs')}
          </button>
        </td>
      </tr>
      {expanded && (
        <tr className="job-runs-row" data-job-runs={job.job_id}>
          <td colSpan={4}>
            {runsLoading ? (
              <p>{t('databricks.jobs.runs_loading', 'Loading runs…')}</p>
            ) : runs.length === 0 ? (
              <p>{t('databricks.jobs.runs_empty', 'No runs reported for this job yet.')}</p>
            ) : (
              <table aria-label={t('databricks.jobs.runs_title', 'Job runs')}>
                <thead>
                  <tr>
                    <th>{t('databricks.jobs.run_id', 'Run id')}</th>
                    <th>{t('databricks.jobs.lifecycle_state', 'Lifecycle state')}</th>
                    <th>{t('databricks.jobs.result_state', 'Result')}</th>
                    <th>{t('databricks.jobs.duration', 'Duration (ms)')}</th>
                  </tr>
                </thead>
                <tbody>
                  {runs.map((run) => (
                    <tr key={run.run_id} data-run={run.run_id} data-lifecycle={run.lifecycle_state}>
                      <td>{run.run_id}</td>
                      <td>{run.lifecycle_state}</td>
                      <td>{run.result_state ?? '-'}</td>
                      <td>{run.duration_ms ?? '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </td>
        </tr>
      )}
    </>
  );
}
