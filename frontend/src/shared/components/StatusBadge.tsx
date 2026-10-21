/**
 * StatusBadge — consistent status pill with color, icon, and tooltip (278.K.2).
 *
 * Covers every status enum in the application.  Usage:
 *   <StatusBadge status="ACTIVE" category="asset" />
 *   <StatusBadge status="FAILED" category="dq_run" />
 */
import type { FC, ReactNode } from 'react';
import './StatusBadge.css';

// ── Status color + icon map ────────────────────────────────────────────────

const STATUS_MAP: Record<string, { color: string; icon: string; label: string }> = {
  // Universal
  ACTIVE:       { color: 'green',  icon: '●', label: 'Active' },
  INACTIVE:     { color: 'gray',   icon: '○', label: 'Inactive' },
  DRAFT:        { color: 'gray',   icon: '◌', label: 'Draft' },
  PENDING:      { color: 'amber',  icon: '◷', label: 'Pending' },
  RUNNING:      { color: 'blue',   icon: '◷', label: 'Running' },
  QUEUED:       { color: 'blue',   icon: '◷', label: 'Queued' },
  PROCESSING:   { color: 'blue',   icon: '◷', label: 'Processing' },
  COMPLETED:    { color: 'green',  icon: '✓', label: 'Completed' },
  SUCCEEDED:    { color: 'green',  icon: '✓', label: 'Succeeded' },
  SUCCESS:      { color: 'green',  icon: '✓', label: 'Success' },
  FAILED:       { color: 'red',    icon: '✗', label: 'Failed' },
  ERROR:        { color: 'red',    icon: '✗', label: 'Error' },
  CANCELLED:    { color: 'gray',   icon: '✕', label: 'Cancelled' },
  UNKNOWN:      { color: 'gray',   icon: '?', label: 'Unknown' },

  // Asset
  RETIRED:      { color: 'gray',   icon: '◌', label: 'Retired' },
  ARCHIVED:     { color: 'gray',   icon: '◌', label: 'Archived' },

  // Approval / access
  APPROVED:     { color: 'green',  icon: '✓', label: 'Approved' },
  REJECTED:     { color: 'red',    icon: '✗', label: 'Rejected' },
  EXPIRED:      { color: 'gray',   icon: '◌', label: 'Expired' },
  REVOKED:      { color: 'red',    icon: '✕', label: 'Revoked' },

  // Quality
  PASSED:       { color: 'green',  icon: '✓', label: 'Passed' },
  PASS:         { color: 'green',  icon: '✓', label: 'Pass' },
  WARNING:      { color: 'amber',  icon: '⚠', label: 'Warning' },
  WARN:         { color: 'amber',  icon: '⚠', label: 'Warn' },

  // Data quality specific
  IMPROVING:    { color: 'green',  icon: '↑', label: 'Improving' },
  DEGRADING:    { color: 'red',    icon: '↓', label: 'Degrading' },
  STABLE:       { color: 'gray',   icon: '→', label: 'Stable' },

  // Compliance
  COMPLIANT:    { color: 'green',  icon: '✓', label: 'Compliant' },
  NON_COMPLIANT:{ color: 'red',    icon: '✗', label: 'Non-Compliant' },

  // Marketplace
  PUBLISHED:    { color: 'green',  icon: '●', label: 'Published' },
  UNLISTED:     { color: 'gray',   icon: '◌', label: 'Unlisted' },
  DELETED:      { color: 'red',    icon: '✕', label: 'Deleted' },
  REQUESTED:    { color: 'blue',   icon: '◷', label: 'Requested' },
  FULFILLED:    { color: 'green',  icon: '✓', label: 'Fulfilled' },

  // Severity
  CRITICAL:     { color: 'red',    icon: '◆', label: 'Critical' },
  HIGH:         { color: 'orange', icon: '▲', label: 'High' },
  MEDIUM:       { color: 'amber',  icon: '■', label: 'Medium' },
  LOW:          { color: 'green',  icon: '▼', label: 'Low' },
  NONE:         { color: 'gray',   icon: '○', label: 'None' },

  // Infrastructure
  DEPLOYING:    { color: 'blue',   icon: '◷', label: 'Deploying' },
  DEPLOYED:     { color: 'green',  icon: '●', label: 'Deployed' },
  UNDEPLOYED:   { color: 'gray',   icon: '○', label: 'Undeployed' },
  TRAINING:     { color: 'blue',   icon: '◷', label: 'Training' },
  TRAINED:      { color: 'green',  icon: '✓', label: 'Trained' },

  // Webhook
  PAUSED:       { color: 'amber',  icon: '⏸', label: 'Paused' },
  DISABLED:     { color: 'gray',   icon: '✕', label: 'Disabled' },
  DEAD_LETTER:  { color: 'red',    icon: '☠', label: 'Dead Letter' },
  RATE_LIMITED: { color: 'amber',  icon: '⏳', label: 'Rate Limited' },

  // Verification
  VERIFIED:     { color: 'green',  icon: '✓', label: 'Verified' },
  UNVERIFIED:   { color: 'amber',  icon: '?', label: 'Unverified' },

  // User
  SUSPENDED:    { color: 'red',    icon: '✕', label: 'Suspended' },
  INVITED:      { color: 'blue',   icon: '◷', label: 'Invited' },

  // Sync
  SYNCED:       { color: 'green',  icon: '✓', label: 'Synced' },
  PARTIAL:      { color: 'amber',  icon: '⚠', label: 'Partial' },
};

export interface StatusBadgeProps {
  status: string;
  /** Optional tooltip text. Defaults to the status label. */
  tooltip?: string;
  /** Optional icon override. */
  icon?: string;
  /** Optional CSS class name. */
  className?: string;
  /** Extra content */
  children?: ReactNode;
}

export const StatusBadge: FC<StatusBadgeProps> = ({
  status,
  tooltip,
  icon,
  className,
  children,
}) => {
  const norm = status.toUpperCase();
  const entry = STATUS_MAP[norm] ?? { color: 'gray', icon: '●', label: status };
  const displayIcon = icon ?? entry.icon;
  const label = entry.label;
  const color = entry.color;

  return (
    <span
      className={`status-badge status-badge--${color} ${className ?? ''}`}
      title={tooltip ?? label}
      data-testid={`status-badge-${norm.toLowerCase()}`}
    >
      <span className="status-badge__icon" aria-hidden="true">{displayIcon}</span>
      <span className="status-badge__label">{children ?? label}</span>
    </span>
  );
};
