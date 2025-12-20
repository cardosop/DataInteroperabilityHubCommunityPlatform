/**
 * Password Reset Request Page
 *
 * Page for requesting a password reset via email.
 */

import React, { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Link } from 'react-router-dom'
import { Container, Box, Typography, Button } from '@mui/material'
import { useMutation } from '@tanstack/react-query'
import { TextInput } from '@/components/forms'
import { Alert } from '@/components/feedback'
import { requestPasswordReset } from '@/lib/api/auth'
import { spacing } from '@/styles/tokens'

/**
 * Password reset request schema
 */
const passwordResetRequestSchema = z.object({
  email: z.string().email('Invalid email address').min(1, 'Email is required'),
})

type PasswordResetRequestFormData = z.infer<typeof passwordResetRequestSchema>

/**
 * Password Reset Request Page Component
 */
export const PasswordResetRequestPage: React.FC = () => {
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<PasswordResetRequestFormData>({
    resolver: zodResolver(passwordResetRequestSchema),
    defaultValues: {
      email: '',
    },
  })

  const resetMutation = useMutation({
    mutationFn: (data: { email: string }) => requestPasswordReset(data),
    onSuccess: () => {
      setSuccess(true)
      setError(null)
    },
    onError: (error: any) => {
      const errorMessage =
        error?.response?.data?.error?.message ||
        error?.response?.data?.email?.[0] ||
        error?.message ||
        'Failed to send password reset email. Please try again.'
      setError(errorMessage)
      setSuccess(false)
    },
  })

  const onSubmit = async (data: PasswordResetRequestFormData) => {
    setError(null)
    setSuccess(false)
    resetMutation.mutate({ email: data.email })
  }

  if (success) {
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
              maxWidth: 400,
              padding: spacing[6],
              borderRadius: 2,
              boxShadow: 3,
            }}
          >
            <Alert
              severity="success"
              title="Check your email"
              message="If an account with that email exists, we've sent you a password reset link. Please check your inbox and follow the instructions."
            />
            <Box sx={{ mt: 3, textAlign: 'center' }}>
              <Link
                to="/auth/login"
                style={{
                  color: 'inherit',
                  textDecoration: 'none',
                  fontWeight: 500,
                }}
              >
                Back to Sign In
              </Link>
            </Box>
          </Box>
        </Box>
      </Container>
    )
  }

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
            maxWidth: 400,
            padding: spacing[6],
            borderRadius: 2,
            boxShadow: 3,
          }}
        >
          <Typography variant="h4" component="h1" gutterBottom align="center">
            Reset Password
          </Typography>
          <Typography variant="body2" color="text.secondary" align="center" sx={{ mb: 4 }}>
            Enter your email address and we'll send you a link to reset your password
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

          <form onSubmit={handleSubmit(onSubmit)}>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: spacing[3] }}>
              <TextInput
                {...register('email')}
                type="email"
                label="Email Address"
                required
                error={errors.email?.message || null}
                disabled={isSubmitting || resetMutation.isPending}
                autoComplete="email"
                autoFocus
              />

              <Button
                type="submit"
                variant="contained"
                fullWidth
                size="large"
                disabled={isSubmitting || resetMutation.isPending}
                sx={{ mt: 2 }}
              >
                {isSubmitting || resetMutation.isPending ? 'Sending...' : 'Send Reset Link'}
              </Button>
            </Box>
          </form>

          <Box sx={{ mt: 3, textAlign: 'center' }}>
            <Link
              to="/auth/login"
              style={{
                color: 'inherit',
                textDecoration: 'none',
                fontSize: '14px',
              }}
            >
              Back to Sign In
            </Link>
          </Box>
        </Box>
      </Box>
    </Container>
  )
}

