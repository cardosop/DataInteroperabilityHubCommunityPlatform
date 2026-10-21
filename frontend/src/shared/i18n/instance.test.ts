import { describe, expect, it } from 'vitest';
import i18n from './instance';

describe('i18next bootstrap (Phase 232.0)', () => {
  it('loads public legal copy from bundled English catalog', () => {
    expect(i18n.t('public.legal.home.title')).toBe('Legal & transparency');
  });

  it('honours explicit defaultValues from callers via t(options)', () => {
    expect(i18n.t('nonexistent.xyz', { defaultValue: 'fallback-value' })).toBe('fallback-value');
  });
});
