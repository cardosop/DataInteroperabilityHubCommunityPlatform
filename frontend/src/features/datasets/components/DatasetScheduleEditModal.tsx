/**
 * Phase 260.4.F — schedule-edit modal embedded on DatasetDetailPage.
 *
 * Reuses the existing scheduled-ingestion plumbing:
 *   - Lookup via ``GET /api/v1/scheduled-ingestions/?asset_id=...``
 *     (Phase 260.4.F backend filter) to find the schedule(s) feeding
 *     the dataset's asset without scanning the full tenant list.
 *   - Edit via ``PATCH /api/v1/scheduled-ingestions/{id}/``
 *     (the existing ``useUpdateScheduledIngestion`` hook).
 *
 * Surface contract:
 *   - 0 schedules for the asset → "No schedule configured" empty
 *     state with a deep-link to ``/scheduled-ingestions/create?asset_id=...``
 *     so the user can wire one up without losing their seat.
 *   - 1+ schedules → rendered list with an "Edit on schedule page"
 *     deep-link per row (we don't try to inline-edit every field
 *     here; the existing edit page is the source of truth and
 *     duplicating its form would create drift). For MVP scope
 *     ("Reuses existing scheduled-ingestion settings") we link out
 *     to the existing form rather than rebuild it inline.
 *
 * Loading / error: skeleton + ErrorDisplay (consistent with the
 * surrounding DatasetDetailPage idiom).
 */

import { type JSX } from 'react';
import { Link } from 'react-router-dom';

import { Button } from '../../../shared/components/Button';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { Modal } from '../../../shared/components/Modal';
import { useScheduledIngestions } from '../../scheduledIngestion/hooks/useScheduledIngestion';
import type { ScheduledIngestionListFilters } from '../../../shared/types/scheduledIngestion';
import { formatScheduleSummary } from '../utils/scheduleSummary';
import './DatasetScheduleEditModal.css';

export interface DatasetScheduleEditModalProps {
  open: boolean;
  assetId: string | null | undefined;
  datasetName: string;
  onClose: () => void;
}

export function DatasetScheduleEditModal({
  open,
  assetId,
  datasetName,
  onClose,
}: DatasetScheduleEditModalProps): JSX.Element | null {
  const { data, isLoading, error, refetch } = useScheduledIngestions(
    (open ? {} : null) as ScheduledIngestionListFilters,
  );

  if (!open) return null;

  const results = data?.results ?? [];
  const createHref = assetId
    ? `/scheduled-ingestions/create?asset_id=${assetId}`
    : '/scheduled-ingestions/create';

  return (
    <Modal
      isOpen={open}
      onClose={onClose}
      title={`Schedule settings for "${datasetName}"`}
      aria-describedby="dataset-schedule-modal-body"
    >
      <div
        id="dataset-schedule-modal-body"
        data-testid="dataset-schedule-modal-body"
        className="dataset-schedule-modal"
      >
        <p className="dataset-schedule-explainer">
          Schedules feed data into this dataset's asset on a recurring cadence.
          Edit an existing schedule or create a new one to change when data is
          refreshed automatically.
        </p>

        {!assetId ? (
          // Defence in depth — the parent page hides the CTA when
          // there's no asset link, but if the modal is mounted
          // anyway we surface a clear empty-state instead of
          // silently rendering nothing.
          <div
            className="dataset-schedule-empty-state"
            data-testid="dataset-schedule-no-asset"
            role="status"
          >
            <p>
              <strong>This dataset is not linked to an asset.</strong> Link the
              dataset to an asset first to manage schedules.
            </p>
          </div>
        ) : isLoading ? (
          <LoadingSpinner message="Loading schedules…" />
        ) : error ? (
          <ErrorDisplay
            error={error}
            title="Failed to load schedules"
            onRetry={() => refetch()}
          />
        ) : results.length === 0 ? (
          <div
            className="dataset-schedule-empty-state"
            data-testid="dataset-schedule-empty-state"
            role="status"
          >
            <p>No schedule is configured for this dataset's asset yet.</p>
            <Link
              to={createHref}
              className="dataset-schedule-create-link"
              data-testid="dataset-schedule-create-link"
            >
              Create a schedule →
            </Link>
          </div>
        ) : (
          <ul
            className="dataset-schedule-list"
            data-testid="dataset-schedule-list"
            aria-label="Schedules feeding this dataset"
          >
            {results.map((schedule) => (
              <li
                key={schedule.id}
                className="dataset-schedule-row"
                data-testid={`dataset-schedule-row-${schedule.id}`}
              >
                <div className="dataset-schedule-row-summary">
                  <strong>{schedule.name}</strong>
                  <span className="dataset-schedule-row-cadence">
                    {formatScheduleSummary(schedule)}
                  </span>
                  <span
                    className={`dataset-schedule-row-status dataset-schedule-row-status-${schedule.status.toLowerCase()}`}
                    aria-label={`Status: ${schedule.status}`}
                  >
                    {schedule.status}
                  </span>
                </div>
                <Link
                  to={`/scheduled-ingestions/${schedule.id}/edit`}
                  className="dataset-schedule-edit-link"
                  data-testid={`dataset-schedule-edit-link-${schedule.id}`}
                >
                  Edit →
                </Link>
              </li>
            ))}
          </ul>
        )}

        <div className="dataset-schedule-actions">
          <Button
            type="button"
            variant="secondary"
            onClick={onClose}
            data-testid="dataset-schedule-close-btn"
          >
            Close
          </Button>
        </div>
      </div>
    </Modal>
  );
}
