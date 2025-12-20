import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { ThemeProvider, CssBaseline } from '@mui/material'
import './index.css'
import App from './App.tsx'
import { lightTheme } from '@/lib/config/mui'
import { ReactQueryProvider } from '@/lib/api/react-query-provider'
import { initAppConfig } from '@/lib/config'

// Validate environment variables at startup
// This will throw an error if required variables are missing or invalid
import '@/lib/config'

// Initialize application configuration (Sentry, Analytics, etc.)
initAppConfig()

// Start MSW in development mode (if enabled)
if (import.meta.env.DEV && import.meta.env.VITE_MSW_ENABLED === 'true') {
  import('@/test-utils/msw/browser').then(({ startMSW }) => {
    startMSW().catch((error) => {
      console.error('[MSW] Failed to start:', error)
    })
  })
}

const rootElement = document.getElementById('root')
if (!rootElement) {
  throw new Error('Root element not found')
}

createRoot(rootElement).render(
  <StrictMode>
    <ReactQueryProvider>
      <ThemeProvider theme={lightTheme}>
        <CssBaseline />
        <App />
      </ThemeProvider>
    </ReactQueryProvider>
  </StrictMode>
)
