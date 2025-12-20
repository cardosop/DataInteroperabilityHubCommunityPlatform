/**
 * i18next Configuration
 *
 * Internationalization configuration using react-i18next.
 * Using dynamic imports to avoid CommonJS/ESM interop issues.
 */
let i18nInstance: any = null
let initReactI18next: any = null
let LanguageDetector: any = null

// Lazy load i18next modules to avoid build-time issues
const loadI18n = async () => {
  if (!i18nInstance) {
    const i18next = await import('i18next')
    const reactI18next = await import('react-i18next')
    const detector = await import('i18next-browser-languagedetector')

    i18nInstance = i18next.default || i18next
    initReactI18next = reactI18next.initReactI18next
    LanguageDetector = detector.default || detector
  }
  return { i18nInstance, initReactI18next, LanguageDetector }
}

// Import translation files
import enTranslations from '@/locales/en/translation.json'
import esTranslations from '@/locales/es/translation.json'
import frTranslations from '@/locales/fr/translation.json'

// Initialize i18n asynchronously
let i18nInitialized = false

const initializeI18n = async () => {
  if (i18nInitialized && i18nInstance) {
    return i18nInstance
  }

  const { i18nInstance: i18n, initReactI18next: initReact, LanguageDetector: Detector } = await loadI18n()

  i18n
    .use(Detector)
    .use(initReact)
    .init({
      resources: {
        en: {
          translation: enTranslations,
        },
        es: {
          translation: esTranslations,
        },
        fr: {
          translation: frTranslations,
        },
      },
      fallbackLng: 'en',
      debug: import.meta.env.DEV,
      interpolation: {
        escapeValue: false, // React already escapes values
      },
      detection: {
        order: ['localStorage', 'navigator'],
        caches: ['localStorage'],
      },
    })

  i18nInitialized = true
  i18nInstance = i18n
  return i18n
}

// Initialize immediately (but asynchronously)
initializeI18n().catch((error) => {
  console.error('[i18n] Failed to initialize:', error)
})

// Export a getter that returns the i18n instance
// This allows synchronous access after initialization
const getI18n = () => {
  if (!i18nInstance) {
    throw new Error('i18n not initialized yet. Call initializeI18n() first.')
  }
  return i18nInstance
}

// For backward compatibility, export default as a proxy
// This will work after initialization
export default new Proxy({} as any, {
  get(_target, prop) {
    const instance = getI18n()
    return instance[prop]
  },
})
