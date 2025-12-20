/**
 * Register Page
 *
 * User registration page with email, password, and name fields.
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
import { register as registerUser } from '@/lib/api/auth'
import type { RegisterRequest } from '@/lib/api/auth'
import { spacing } from '@/styles/tokens'

/**
 * Register form schema
 */
const registerSchema = z
  .object({
    email: z.string().email('Invalid email address').min(1, 'Email is required'),
    password: z
      .string()
      .min(8, 'Password must be at least 8 characters')
      .regex(/[A-Z]/, 'Password must contain at least one uppercase letter')
      .regex(/[a-z]/, 'Password must contain at least one lowercase letter')
      .regex(/[0-9]/, 'Password must contain at least one number'),
    confirmPassword: z.string().min(1, 'Please confirm your password'),
    name: z.string().min(1, 'Name is required').max(255, 'Name is too long'),
    tenant_id: z.string().uuid('Invalid tenant ID').optional().or(z.literal('')),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: "Passwords don't match",
    path: ['confirmPassword'],
  })

type RegisterFormData = z.infer<typeof registerSchema>

/**
 * Register Page Component
 */
export const RegisterPage: React.FC = () => {
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<RegisterFormData>({
    resolver: zodResolver(registerSchema),
    mode: 'onSubmit', // Validate on submit
    reValidateMode: 'onChange', // Re-validate on change after submit
    shouldFocusError: true, // Focus first error field
    criteriaMode: 'all', // Show all validation errors, not just first
    defaultValues: {
      email: '',
      password: '',
      confirmPassword: '',
      name: '',
      tenant_id: '',
    },
  })

  const registerMutation = useMutation({
    mutationFn: (data: RegisterRequest) => registerUser(data),
    onSuccess: () => {
      // Redirect to login with success message
      navigate('/auth/login?registered=true')
    },
    onError: (error: any) => {
      const errorMessage =
        error?.response?.data?.error?.message ||
        error?.response?.data?.email?.[0] ||
        error?.response?.data?.password?.[0] ||
        error?.response?.data?.name?.[0] ||
        error?.response?.data?.tenant_id?.[0] ||
        error?.message ||
        'Registration failed. Please try again.'
      setError(errorMessage)
    },
  })

  const onSubmit = async (data: RegisterFormData) => {
    setError(null)
    registerMutation.mutate({
      email: data.email,
      password: data.password,
      name: data.name,
      tenant_id: data.tenant_id || undefined,
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
            Create Account
          </Typography>
          <Typography variant="body2" color="text.secondary" align="center" sx={{ mb: 4 }}>
            Sign up to get started
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
                {...register('name')}
                type="text"
                label="Full Name"
                required
                error={errors.name?.message || null}
                disabled={isSubmitting || registerMutation.isPending}
                autoComplete="name"
                autoFocus
              />

              <TextInput
                {...register('email')}
                type="email"
                label="Email Address"
                required
                error={errors.email?.message || null}
                disabled={isSubmitting || registerMutation.isPending}
                autoComplete="email"
              />

              <TextInput
                {...register('password')}
                type="password"
                label="Password"
                required
                error={errors.password?.message || null}
                disabled={isSubmitting || registerMutation.isPending}
                autoComplete="new-password"
                helperText="Must be at least 8 characters with uppercase, lowercase, and number"
              />

              <TextInput
                {...register('confirmPassword')}
                type="password"
                label="Confirm Password"
                required
                error={errors.confirmPassword?.message || null}
                disabled={isSubmitting || registerMutation.isPending}
                autoComplete="new-password"
              />

              <TextInput
                {...register('tenant_id')}
                type="text"
                label="Tenant ID (Optional)"
                error={errors.tenant_id?.message || null}
                disabled={isSubmitting || registerMutation.isPending}
                helperText="If you have a tenant ID, enter it here"
              />

              <Button
                type="submit"
                variant="contained"
                fullWidth
                size="large"
                disabled={isSubmitting || registerMutation.isPending}
                sx={{ mt: 2 }}
              >
                {isSubmitting || registerMutation.isPending ? 'Creating account...' : 'Create Account'}
              </Button>
            </Box>
          </form>

          <Box sx={{ mt: 3, textAlign: 'center' }}>
            <Typography variant="body2" color="text.secondary">
              Already have an account?{' '}
              <Link
                to="/auth/login"
                style={{
                  color: 'inherit',
                  textDecoration: 'none',
                  fontWeight: 500,
                }}
              >
                Sign in
              </Link>
            </Typography>
          </Box>
        </Box>
      </Box>
    </Container>
  )
}

