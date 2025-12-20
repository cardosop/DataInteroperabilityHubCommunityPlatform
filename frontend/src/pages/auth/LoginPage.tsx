/**
 * Login Page
 *
 * User authentication page with email and password login.
 */

import React, { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useNavigate, Link } from 'react-router-dom'
import { Container, Box, Typography, Button } from '@mui/material'
import { useMutation } from '@tanstack/react-query'
import { TextInput } from '@/components/forms'
import { Alert } from '@/components/feedback'
import { login } from '@/lib/api/auth'
import type { LoginRequest } from '@/lib/api/auth'
import { spacing } from '@/styles/tokens'

/**
 * Login form schema
 */
const loginSchema = z.object({
  email: z.string().min(1, 'Email is required').email('Invalid email address'),
  password: z.string().min(1, 'Password is required'),
  remember_me: z.boolean().optional(),
})

type LoginFormData = z.infer<typeof loginSchema>

/**
 * Login Page Component
 */
export const LoginPage: React.FC = () => {
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting, isSubmitted },
  } = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
    mode: 'onTouched', // Validate on blur and submit - shows errors after user interacts
    reValidateMode: 'onChange', // Re-validate on change after first validation
    shouldFocusError: true, // Focus first error field
    criteriaMode: 'all', // Show all validation errors, not just first
    shouldUnregister: false, // Keep field values in form state
    defaultValues: {
      email: '',
      password: '',
      remember_me: false,
    },
  })

  const loginMutation = useMutation({
    mutationFn: (data: LoginRequest) => login(data),
    onSuccess: () => {
      // Login function already handles token storage and user fetching
      // Redirect to home or intended destination
      const redirectTo = new URLSearchParams(window.location.search).get('redirect') || '/'
      navigate(redirectTo)
    },
    onError: (error: any) => {
      const errorMessage =
        error?.response?.data?.error?.message ||
        error?.response?.data?.email?.[0] ||
        error?.response?.data?.password?.[0] ||
        error?.message ||
        'Login failed. Please check your credentials and try again.'
      setError(errorMessage)
    },
  })

  const onSubmit = async (data: LoginFormData) => {
    setError(null)
    loginMutation.mutate({
      email: data.email,
      password: data.password,
      remember_me: data.remember_me,
    })
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
            Sign In
          </Typography>
          <Typography variant="body2" color="text.secondary" align="center" sx={{ mb: 4 }}>
            Enter your credentials to access your account
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
                disabled={isSubmitting || loginMutation.isPending}
                autoComplete="email"
                autoFocus
              />

              <TextInput
                {...register('password')}
                type="password"
                label="Password"
                required
                error={errors.password?.message || null}
                disabled={isSubmitting || loginMutation.isPending}
                autoComplete="current-password"
              />

              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Box sx={{ display: 'flex', alignItems: 'center' }}>
                  <input
                    type="checkbox"
                    id="remember_me"
                    {...register('remember_me')}
                    disabled={isSubmitting || loginMutation.isPending}
                  />
                  <label htmlFor="remember_me" style={{ marginLeft: spacing[1], fontSize: '14px' }}>
                    Remember me
                  </label>
                </Box>
                <Link
                  to="/auth/password-reset"
                  style={{
                    fontSize: '14px',
                    color: 'inherit',
                    textDecoration: 'none',
                  }}
                >
                  Forgot password?
                </Link>
              </Box>

              <Button
                type="submit"
                variant="contained"
                fullWidth
                size="large"
                disabled={isSubmitting || loginMutation.isPending}
                sx={{ mt: 2 }}
              >
                {isSubmitting || loginMutation.isPending ? 'Signing in...' : 'Sign In'}
              </Button>
            </Box>
          </form>

          <Box sx={{ mt: 3, textAlign: 'center' }}>
            <Typography variant="body2" color="text.secondary">
              Don't have an account?{' '}
              <Link
                to="/auth/register"
                style={{
                  color: 'inherit',
                  textDecoration: 'none',
                  fontWeight: 500,
                }}
              >
                Sign up
              </Link>
            </Typography>
          </Box>
        </Box>
      </Box>
    </Container>
  )
}

