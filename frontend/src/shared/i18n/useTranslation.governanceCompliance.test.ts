/** Pins for the governance compliance-surface i18n keys
 * (close-test-coverage-gaps 4.4).
 *
 * The DSAR queue/detail pages render ``t(...)`` WITHOUT inline
 * fallbacks — before the GOVERNANCE_COMPLIANCE_EN table shipped, the
 * English UI showed RAW KEYS ("governance.dsar.queue_title"), the same
 * family as the 2.4 approval-inbox incident. These pins hold the
 * contract: every key the dsar/breach/processor components render must
 * resolve to real copy, so a future key-table refactor that drops them
 * fails here.
 */
import { describe, expect, it } from 'vitest';
import { useTranslation } from './useTranslation';

describe('useTranslation — governance compliance keys (4.4)', () => {
  const { t } = useTranslation();

  it('resolves every dsar key to real copy (no raw keys in the UI)', () => {
    const keys = [
      'governance.dsar.queue_title',
      'governance.dsar.col_type',
      'governance.dsar.col_subject',
      'governance.dsar.col_status',
      'governance.dsar.col_sla_scan',
      'governance.dsar.col_deadline',
      'governance.dsar.col_fulfil_detail',
      'governance.dsar.col_action',
      'governance.dsar.countdown_prefix',
      'governance.dsar.countdown_overdue',
      'governance.dsar.subject_tz_label',
      'governance.dsar.regulator_tz_label',
      'governance.dsar.open',
      'governance.dsar.empty',
      'governance.dsar.detail_title',
      'governance.dsar.loading',
      'governance.dsar.btn_materialize',
      'governance.dsar.btn_reject',
      'governance.dsar.btn_legal_hold',
      'governance.dsar.btn_download',
      'governance.dsar.download_ready',
      'governance.dsar.prompt_reject',
      'governance.dsar.prompt_hold_reason',
    ];
    for (const key of keys) {
      expect(t(key), key).not.toBe(key);
    }
  });

  it('resolves every breach key to real copy', () => {
    const keys = [
      'governance.breach.dashboard_title',
      'governance.breach.open_count',
      'governance.breach.pending_notifications',
      'governance.breach.col_title',
      'governance.breach.col_status',
      'governance.breach.col_deadline',
      'governance.breach.col_countdown',
      'governance.breach.col_action',
      'governance.breach.view',
      'governance.breach.btn_contained',
      'governance.breach.btn_notified',
      'governance.breach.btn_closed',
      'governance.breach.not_found',
      'governance.breach.notifications',
      'governance.breach.notif_due',
      'governance.breach.countdown_overdue',
      'governance.breach.btn_mark_sent',
      'governance.breach.prompt_outbound_ref',
      'governance.breach.templates_title',
      'governance.breach.templates_intro',
      'governance.breach.field_regime',
      'governance.breach.field_subject',
      'governance.breach.field_body',
      'governance.breach.save',
      'governance.breach.saving',
      'governance.breach.report_title',
      'governance.breach.field_title',
      'governance.breach.field_summary',
      'governance.breach.field_regimes',
      'governance.breach.submit',
      'governance.breach.submitting',
    ];
    for (const key of keys) {
      expect(t(key), key).not.toBe(key);
    }
  });

  it('resolves every processor-agreements key to real copy', () => {
    const keys = [
      'governance.processors.title',
      'governance.processors.add_processor',
      'governance.processors.legal_name',
      'governance.processors.list',
      'governance.processors.name',
      'governance.processors.save',
      'governance.processors.saving',
    ];
    for (const key of keys) {
      expect(t(key), key).not.toBe(key);
    }
  });

  it('resolves the dsar queue headline to the human copy', () => {
    expect(t('governance.dsar.queue_title')).toBe('Data subject requests (DSAR)');
  });

  it('resolves the dsar detail title to the human copy', () => {
    expect(t('governance.dsar.detail_title')).toBe('DSAR request detail');
  });
});
