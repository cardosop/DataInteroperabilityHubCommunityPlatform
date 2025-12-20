import { AppRoutes } from '@/routes'
import { SessionManager } from '@/components/auth'
import { useRealtimeNotifications } from '@/hooks/useRealtimeNotifications'

/**
 * App Component
 *
 * Main application component with routing and session management.
 */
function App() {
  // Enable real-time notifications for asset and contract changes
  useRealtimeNotifications({ enabled: true })

  return (
    <>
      <SessionManager />
      <AppRoutes />
    </>
  )
}

export default App
