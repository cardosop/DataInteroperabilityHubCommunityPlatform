/**
 * 280.C.1.1 — Translation coverage validation for es + fr locales.
 *
 * Validates:
 *  - Every English key has a corresponding key in es and fr
 *  - Coverage >= 90% (no more than 10% keys identical to English fallback)
 *  - No empty translation values
 *  - No duplicate keys within a locale
 */
import { describe, it, expect } from 'vitest';
import { ALL_I18N_EN } from './en';
import { ALL_I18N_ES } from './es';
import { ALL_I18N_FR } from './fr';

const EN_KEYS = Object.keys(ALL_I18N_EN);
const TOTAL_KEYS = EN_KEYS.length;

describe('i18n translation coverage (280.C.1.1)', () => {
  // ── Key parity ──────────────────────────────────────────────────────
  it('es locale has all English keys', () => {
    const esKeys = new Set(Object.keys(ALL_I18N_ES));
    const missing = EN_KEYS.filter((k) => !esKeys.has(k));
    expect(missing).toEqual([]);
  });

  it('fr locale has all English keys', () => {
    const frKeys = new Set(Object.keys(ALL_I18N_FR));
    const missing = EN_KEYS.filter((k) => !frKeys.has(k));
    expect(missing).toEqual([]);
  });

  it('es locale has no extra keys', () => {
    const esKeys = new Set(Object.keys(ALL_I18N_ES));
    const extra = [...esKeys].filter((k) => !ALL_I18N_EN[k]);
    expect(extra).toEqual([]);
  });

  it('fr locale has no extra keys', () => {
    const frKeys = new Set(Object.keys(ALL_I18N_FR));
    const extra = [...frKeys].filter((k) => !ALL_I18N_EN[k]);
    expect(extra).toEqual([]);
  });

  // ── No empty values ─────────────────────────────────────────────────
  it('es locale has no empty translation values', () => {
    const empty = EN_KEYS.filter((k) => !ALL_I18N_ES[k] || ALL_I18N_ES[k].trim() === '');
    expect(empty).toEqual([]);
  });

  it('fr locale has no empty translation values', () => {
    const empty = EN_KEYS.filter((k) => !ALL_I18N_FR[k] || ALL_I18N_FR[k].trim() === '');
    expect(empty).toEqual([]);
  });

  // ── Coverage threshold (>90%) ──────────────────────────────────────
  it('es locale has >= 90% unique translations (not identical to English)', () => {
    const identical = EN_KEYS.filter((k) => ALL_I18N_ES[k] === ALL_I18N_EN[k]);
    const coveragePct = ((TOTAL_KEYS - identical.length) / TOTAL_KEYS) * 100;
    expect(coveragePct).toBeGreaterThanOrEqual(90);
  });

  it('fr locale has >= 90% unique translations (not identical to English)', () => {
    const identical = EN_KEYS.filter((k) => ALL_I18N_FR[k] === ALL_I18N_EN[k]);
    const coveragePct = ((TOTAL_KEYS - identical.length) / TOTAL_KEYS) * 100;
    expect(coveragePct).toBeGreaterThanOrEqual(90);
  });

  // ── Minimum string length ───────────────────────────────────────────
  it('es translations have reasonable minimum length', () => {
    // No translation should be a single character (likely a mistake)
    const tooShort = EN_KEYS.filter(
      (k) => ALL_I18N_ES[k] !== ALL_I18N_EN[k] && ALL_I18N_ES[k].length === 1,
    );
    expect(tooShort).toEqual([]);
  });

  it('fr translations have reasonable minimum length', () => {
    const tooShort = EN_KEYS.filter(
      (k) => ALL_I18N_FR[k] !== ALL_I18N_EN[k] && ALL_I18N_FR[k].length === 1,
    );
    expect(tooShort).toEqual([]);
  });

  // ── Template interpolation preservation ─────────────────────────────
  it('es locale preserves {variable} interpolation patterns', () => {
    const broken: string[] = [];
    for (const k of EN_KEYS) {
      const enVars = ALL_I18N_EN[k].match(/\{[a-zA-Z_]+\}/g) || [];
      const esVars = (ALL_I18N_ES[k] || '').match(/\{[a-zA-Z_]+\}/g) || [];
      const enSet = new Set(enVars);
      const esSet = new Set(esVars);
      for (const v of enSet) {
        if (!esSet.has(v)) broken.push(`${k}: missing ${v}`);
      }
    }
    expect(broken).toEqual([]);
  });

  it('fr locale preserves {variable} interpolation patterns', () => {
    const broken: string[] = [];
    for (const k of EN_KEYS) {
      const enVars = ALL_I18N_EN[k].match(/\{[a-zA-Z_]+\}/g) || [];
      const frVars = (ALL_I18N_FR[k] || '').match(/\{[a-zA-Z_]+\}/g) || [];
      const enSet = new Set(enVars);
      const frSet = new Set(frVars);
      for (const v of enSet) {
        if (!frSet.has(v)) broken.push(`${k}: missing ${v}`);
      }
    }
    expect(broken).toEqual([]);
  });

  // ── Key count baseline ──────────────────────────────────────────────
  it('English locale has at least 170 keys (baseline for feature coverage)', () => {
    expect(TOTAL_KEYS).toBeGreaterThanOrEqual(170);
  });
});
