/**
 * Phase 231.3 — discovery payload for latest succeeded compliance on resources.
 * Mirrors hub/apps/compliance/serializers.py:ComplianceRunSummarySerializer.
 */

export interface ComplianceRunSummary {
  id: string;
  status: string;
  overall_status?: string | null;
  risk_level?: string | null;
  allowed_to_store?: boolean | null;
  completed_at?: string | null;
  created_at: string;
  /** When present and not an array, discovery UI may fail closed via error boundary. */
  regulation_summaries?: unknown;
}
