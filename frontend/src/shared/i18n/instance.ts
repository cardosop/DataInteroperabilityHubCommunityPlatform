/**
 * Phase 232.0 — central i18next instance (bootstrap before React root).
 */

import i18next from 'i18next';
import { initReactI18next } from 'react-i18next';
import { ALL_I18N_EN } from './locales/en';
import { ALL_I18N_ES } from './locales/es';
import { ALL_I18N_FR } from './locales/fr';
import { ALL_I18N_DE } from './locales/de';
import { ALL_I18N_PT } from './locales/pt';
import { ALL_I18N_JA } from './locales/ja';

const instance = i18next.createInstance();

void instance.use(initReactI18next).init({
  lng: 'en',
  fallbackLng: 'en',
  supportedLngs: ['en', 'es', 'fr', 'de', 'pt', 'ja'],
  resources: {
    en: { translation: ALL_I18N_EN },
    es: { translation: ALL_I18N_ES },
    fr: { translation: ALL_I18N_FR },
    de: { translation: ALL_I18N_DE },
    pt: { translation: ALL_I18N_PT },
    ja: { translation: ALL_I18N_JA },
  },
  interpolation: { escapeValue: true },
});

export default instance;
