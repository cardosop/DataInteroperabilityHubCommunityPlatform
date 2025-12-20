/**
 * Password Reset Confirm Page
 *
 * Page for confirming password reset with token and new password.
 */

import React, { useState, useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useNavigate, useSearchParams, Link } from 'react-router-dom'
import { Container, Box, Typography, Button } from '@mui/material'
import { useMutation } from '@tanstack/react-query'
import { TextInput } from '@/components/forms'
import { Alert } from '@/components/feedback'
import { confirmPasswordReset } from '@/lib/api/auth'
import { spacing } from '@/styles/tokens'

/**
 * Password reset confirm schema
 */
const passwordResetConfirmSchema = z
  .object({
    new_password: z
      .string()
      .min(8, 'Password must be at least 8 characters')
      .regex(/[A-Z]/, 'Password must contain at least one uppercase letter')
      .regex(/[a-z]/, 'Password must contain at least one lowercase letter')
      .regex(/[0-9]/, 'Password must contain at least one number'),
    confirm_password: z.string().min(1, 'Please confirm your password'),
  })
  .refine((data) => data.new_password === data.confirm_password, {
    message: "Passwords don't match",
    path: ['confirm_password'],
  })

type PasswordResetConfirmFormData = z.infer<typeof passwordResetConfirmSchema>

/**
 * Password Reset Confirm Page Component
 */
export const PasswordResetConfirmPage: React.FC = () => {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)
  const [token, setToken] = useState<string | null>(null)

  useEffect(() => {
    // Get token from URL query parameter
    const tokenParam = searchParams.get('token')
    if (tokenParam) {
      setToken(tokenParam)
    } else {
      setError('Invalid or missing reset token. Please request a new password reset.')
    }
  }, [searchParams])

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<PasswordResetConfirmFormData>({
    resolver: zodResolver(passwordResetConfirmSchema),
    defaultValues: {
      new_password: '',
      confirm_password: '',
    },
  })

  const confirmMutation = useMutation({
    mutationFn: (data: { token: string; new_password: string }) =>
      confirmPasswordReset(data),
    onSuccess: () => {
      setSuccess(true)
      setError(null)
      // Redirect to login after 3 seconds
      setTimeout(() => {
        navigate('/auth/login?password_reset=true')
      }, 3000)
    },
    onError: (error: any) => {
      const errorMessage =
        error?.response?.data?.error?.message ||
        error?.response?.data?.token?.[0] ||
        error?.response?.data?.new_password?.[0] ||
        error?.message ||
        'Failed to reset password. The token may be invalid or expired. Please request a new password reset.'
      setError(errorMessage)
      setSuccess(false)
    },
  })

  const onSubmit = async (data: PasswordResetConfirmFormData) => {
    if (!token) {
      setError('Invalid or missing reset token. Please request a new password reset.')
      return
    }

    setError(null)
    confirmMutation.mutate({
      token,
      new_password: data.new_password,
    })
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
              title="Password Reset Successful"
              message="Your password has been reset successfully. Redirecting to login..."
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
                Go to Sign In
              </Link>
            </Box>
          </Box>
        </Box>
      </Container>
    )
  }

  if (!token) {
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
              severity="error"
              title="Invalid Token"
              message="The password reset token is missing or invalid. Please request a new password reset."
            />
            <Box sx={{ mt: 3, textAlign: 'center' }}>
              <Link
                to="/auth/password-reset"
                style={{
                  color: 'inherit',
                  textDecoration: 'none',
                  fontWeight: 500,
                }}
              >
                Request New Reset Link
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
            Enter your new password
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
                {...register('new_password')}
                type="password"
                label="New Password"
                required
                error={errors.new_password?.message || null}
                disabled={isSubmitting || confirmMutation.isPending}
                autoComplete="new-password"
                autoFocus
                helperText="Must be at least 8 characters with uppercase, lowercase, and number"
              />

              <TextInput
                {...register('confirm_password')}
                type="password"
                label="Confirm New Password"
                required
                error={errors.confirm_password?.message || null}
                disabled={isSubmitting || confirmMutation.isPending}
                autoComplete="new-password"
              />

              <Button
                type="submit"
                variant="contained"
                fullWidth
                size="large"
                disabled={isSubmitting || confirmMutation.isPending}
                sx={{ mt: 2 }}
              >
                {isSubmitting || confirmMutation.isPending ? 'Resetting...' : 'Reset Password'}
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

