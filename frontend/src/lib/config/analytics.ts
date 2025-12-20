/**
 * Google Analytics Configuration
 *
 * Analytics tracking configuration using react-ga4.
 */
// Use dynamic import to avoid CommonJS/ESM interop issues during build
// react-ga4 uses CommonJS, so we import it dynamically at runtime
let ReactGA: any = null

// Lazy load react-ga4 to avoid build-time issues
const loadReactGA = async () => {
  if (!ReactGA) {
    const ga4Module = await import('react-ga4')
    // react-ga4 exports both default and named exports
    ReactGA = ga4Module.default || ga4Module
  }
  return ReactGA
}

export const initAnalytics = async () => {
  const measurementId = import.meta.env.VITE_GA_MEASUREMENT_ID

  if (!measurementId) {
    console.warn('Google Analytics Measurement ID not configured. Analytics disabled.')
    return
  }

  const GA = await loadReactGA()
  GA.initialize(measurementId, {
    testMode: import.meta.env.DEV,
  })
}

export const trackPageView = async (path: string) => {
  try {
    const GA = await loadReactGA()
    GA.send({ hitType: 'pageview', page: path })
  } catch (error) {
    console.error('[Analytics] Failed to track page view:', error)
  }
}

export const trackEvent = async (
  category: string,
  action: string,
  label?: string,
  value?: number,
  properties?: Record<string, any>
) => {
  try {
    const GA = await loadReactGA()
    GA.event({
      category,
      action,
      label,
      value,
      ...(properties && { custom_parameters: properties }),
    })
  } catch (error) {
    console.error('[Analytics] Failed to track event:', error)
  }
}
