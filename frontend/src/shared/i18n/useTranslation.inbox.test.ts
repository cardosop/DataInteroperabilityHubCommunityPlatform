/** Pins for the approval-inbox i18n keys (close-test-coverage-gaps 2.4).
 *
 * The populated-inbox E2E run exposed the raw keys rendering in the UI
 * ("governance.approvalInbox.title 41") — the keys were never added to
 * the locale table. These pins hold the contract: every key the inbox
 * component renders must resolve to real copy, so a future key-table
 * refactor that drops them fails here.
 */
import { describe, expect, it } from 'vitest';
import { useTranslation } from './useTranslation';

describe('useTranslation — governance.approvalInbox keys', () => {
  const { t } = useTranslation();

  it('resolves every inbox key to real copy (no raw keys in the UI)', () => {
    const keys = [
      'governance.approvalInbox.title',
      'governance.approvalInbox.empty',
      'governance.approvalInbox.view_all',
      'governance.approvalInbox.select_all',
      'governance.approvalInbox.reject_reason',
      'governance.approvalInbox.approve',
      'governance.approvalInbox.reject',
    ];
    for (const key of keys) {
      expect(t(key), key).not.toBe(key);
    }
  });

  it('resolves the title to the human copy', () => {
    expect(t('governance.approvalInbox.title')).toBe('My Approvals');
  });
});
