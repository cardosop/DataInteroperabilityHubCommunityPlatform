/**
 * Phase 228 F5 (228.F5.18) — minimal i18n shim.
 *
 * This is the seam between the components and a future i18n library
 * (react-i18next, lingui, formatjs, etc.). The signature
 * `t(key, fallback?)` matches every mainstream library so the
 * eventual swap is a one-line change in this file — no component
 * code rewrites.
 *
 * Until the library is wired in, the shim simply returns the
 * fallback string (or the key as fallback-of-fallback). Translation
 * coverage is captured in [./locales/](./locales/) JSON files so
 * translators can start work without blocking on the runtime
 * integration.
 */
import { LINEAGE_TIMETRAVEL_EN } from './locales/en';

export interface Translator {
  t: (key: string, fallback?: string) => string;
}

const ALL_LOCALES_EN: Record<string, string> = {
  ...LINEAGE_TIMETRAVEL_EN,
};

export function useTranslation(): Translator {
  return {
    t: (key, fallback) => ALL_LOCALES_EN[key] ?? fallback ?? key,
  };
}
