/**
 * Tenant Selection Page
 *
 * Page for selecting a tenant when user has access to multiple tenants.
 * This page is shown when a user needs to choose which tenant context to use.
 */

import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Container, Box, Typography, Button, Card, CardContent, CircularProgress } from '@mui/material'
import { useQuery } from '@tanstack/react-query'
import { Alert } from '@/components/feedback'
import { getCurrentUser } from '@/lib/api/auth'
import { setCurrentUser } from '@/lib/auth/auth'
import { spacing } from '@/styles/tokens'

/**
 * Tenant Selection Page Component
 *
 * Note: This is a placeholder implementation. In a real multi-tenant system,
 * you would fetch available tenants from an API endpoint. For now, this page
 * checks if the user has a tenant_id and allows them to proceed or switch tenants.
 */
export const TenantSelectionPage: React.FC = () => {
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)

  const { data: user, isLoading, error: userError } = useQuery({
    queryKey: ['auth', 'current-user'],
    queryFn: () => getCurrentUser(),
    retry: false,
  })

  useEffect(() => {
    // If user already has a tenant, redirect to home
    if (user?.tenant_id) {
      // Update user in storage
      setCurrentUser({
        id: user.id,
        email: user.email,
        name: user.name || undefined,
        roles: user.roles,
        permissions: user.permissions,
        tenantId: user.tenant_id,
      })
      navigate('/')
    }
  }, [user, navigate])

  const handleContinue = () => {
    if (user?.tenant_id) {
      navigate('/')
    } else {
      setError('Please select a tenant to continue')
    }
  }

  if (isLoading) {
    return (
      <Container maxWidth="sm">
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            minHeight: '100vh',
            padding: spacing[4],
          }}
        >
          <CircularProgress />
          <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
            Loading tenant information...
          </Typography>
        </Box>
      </Container>
    )
  }

  if (userError) {
    return (
      <Container maxWidth="sm">
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            minHeight: '100vh',
            padding: spacing[4],
          }}
        >
          <Alert
            severity="error"
            title="Error Loading Tenants"
            message="Failed to load tenant information. Please try again or contact support."
          />
          <Button
            variant="contained"
            onClick={() => navigate('/auth/login')}
            sx={{ mt: 2 }}
          >
            Back to Login
          </Button>
        </Box>
      </Container>
    )
  }

  // If user doesn't have a tenant_id, show tenant selection UI
  // In a real implementation, you would fetch available tenants from an API
  const availableTenants: Array<{ id: string; name: string }> = []

  if (availableTenants.length === 0 && !user?.tenant_id) {
    return (
      <Container maxWidth="sm">
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            minHeight: '100vh',
            padding: spacing[4],
          }}
        >
          <Box
            sx={{
              width: '100%',
              maxWidth: 500,
              padding: spacing[6],
              borderRadius: 2,
              boxShadow: 3,
            }}
          >
            <Typography variant="h4" component="h1" gutterBottom align="center">
              Select Tenant
            </Typography>
            <Typography variant="body2" color="text.secondary" align="center" sx={{ mb: 4 }}>
              You don't have access to any tenants. Please contact your administrator.
            </Typography>

            {error && (
              <Alert
                severity="error"
                message={error}
                dismissible
                onClose={() => setError(null)}
                className="mb-4"
              />
            )}

            <Box sx={{ mt: 3, textAlign: 'center' }}>
              <Button
                variant="outlined"
                onClick={() => navigate('/auth/login')}
              >
                Back to Login
              </Button>
            </Box>
          </Box>
        </Box>
      </Container>
    )
  }

  return (
    <Container maxWidth="md">
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: '100vh',
          padding: spacing[4],
        }}
      >
        <Box
          sx={{
            width: '100%',
            maxWidth: 600,
            padding: spacing[6],
            borderRadius: 2,
            boxShadow: 3,
          }}
        >
          <Typography variant="h4" component="h1" gutterBottom align="center">
            Select Tenant
          </Typography>
          <Typography variant="body2" color="text.secondary" align="center" sx={{ mb: 4 }}>
            Choose which tenant you want to access
          </Typography>

          {error && (
            <Alert
              severity="error"
              message={error}
              dismissible
              onClose={() => setError(null)}
              className="mb-4"
            />
          )}

          <Box sx={{ display: 'flex', flexDirection: 'column', gap: spacing[2], mb: 4 }}>
            {availableTenants.map((tenant) => (
              <Card
                key={tenant.id}
                sx={{
                  cursor: 'pointer',
                  '&:hover': {
                    boxShadow: 4,
                  },
                }}
                onClick={() => {
                  // In a real implementation, you would set the tenant context here
                  // and then navigate to the home page
                  navigate('/')
                }}
              >
                <CardContent>
                  <Typography variant="h6">{tenant.name}</Typography>
                  <Typography variant="body2" color="text.secondary">
                    Tenant ID: {tenant.id}
                  </Typography>
                </CardContent>
              </Card>
            ))}
          </Box>

          <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 3 }}>
            <Button
              variant="outlined"
              onClick={() => navigate('/auth/login')}
            >
              Back to Login
            </Button>
            <Button
              variant="contained"
              onClick={handleContinue}
              disabled={!user?.tenant_id && availableTenants.length === 0}
            >
              Continue
            </Button>
          </Box>
        </Box>
      </Box>
    </Container>
  )
}

