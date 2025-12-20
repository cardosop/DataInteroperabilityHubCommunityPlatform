/**
 * API Key Management Page
 *
 * Page for managing API keys: creating, viewing, and deleting API keys.
 */

import React, { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import {
  Container,
  Box,
  Typography,
  Button,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  IconButton,
  Chip,
  Alert as MuiAlert,
} from '@mui/material'
import { Delete as DeleteIcon, Visibility as VisibilityIcon, VisibilityOff as VisibilityOffIcon } from '@mui/icons-material'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { TextInput } from '@/components/forms'
import { Alert } from '@/components/feedback'
import { listAPIKeys, createAPIKey, deleteAPIKey, type CreateAPIKeyRequest } from '@/lib/api/auth'
import { spacing } from '@/styles/tokens'

/**
 * Create API key form schema
 */
const createApiKeySchema = z.object({
  name: z.string().min(1, 'Name is required').max(255, 'Name is too long'),
  scopes: z.string().optional(),
  expires_in_days: z
    .string()
    .optional()
    .transform((val) => (val === '' ? undefined : val ? parseInt(val, 10) : null))
    .refine((val) => val === null || val === undefined || (val > 0 && val <= 365), {
      message: 'Expiration days must be between 1 and 365',
    }),
})

type CreateApiKeyFormData = z.infer<typeof createApiKeySchema>

/**
 * API Key Management Page Component
 */
export const ApiKeyManagementPage: React.FC = () => {
  const queryClient = useQueryClient()
  const [createDialogOpen, setCreateDialogOpen] = useState(false)
  const [newApiKey, setNewApiKey] = useState<string | null>(null)
  const [visibleKeys, setVisibleKeys] = useState<Set<string>>(new Set())
  const [error, setError] = useState<string | null>(null)

  const {
    data: apiKeysData,
    isLoading,
    error: listError,
  } = useQuery({
    queryKey: ['auth', 'api-keys'],
    queryFn: () => listAPIKeys(),
  })

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<CreateApiKeyFormData>({
    resolver: zodResolver(createApiKeySchema),
    defaultValues: {
      name: '',
      scopes: '',
      expires_in_days: '',
    },
  })

  const createMutation = useMutation({
    mutationFn: (data: CreateAPIKeyRequest) => createAPIKey(data),
    onSuccess: (response) => {
      setNewApiKey(response.api_key)
      queryClient.invalidateQueries({ queryKey: ['auth', 'api-keys'] })
      reset()
      setError(null)
    },
    onError: (error: any) => {
      const errorMessage =
        error?.response?.data?.error?.message ||
        error?.response?.data?.name?.[0] ||
        error?.response?.data?.scopes?.[0] ||
        error?.response?.data?.expires_in_days?.[0] ||
        error?.message ||
        'Failed to create API key. Please try again.'
      setError(errorMessage)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteAPIKey(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['auth', 'api-keys'] })
      setError(null)
    },
    onError: (error: any) => {
      const errorMessage =
        error?.response?.data?.error?.message ||
        error?.message ||
        'Failed to delete API key. Please try again.'
      setError(errorMessage)
    },
  })

  const onSubmit = async (data: CreateApiKeyFormData) => {
    setError(null)
    createMutation.mutate({
      name: data.name,
      scopes: data.scopes ? data.scopes.split(',').map((s) => s.trim()) : [],
      expires_in_days: data.expires_in_days || null,
    })
  }

  const handleCloseCreateDialog = () => {
    setCreateDialogOpen(false)
    setNewApiKey(null)
    reset()
    setError(null)
  }

  const handleDelete = (id: string) => {
    if (window.confirm('Are you sure you want to delete this API key? This action cannot be undone.')) {
      deleteMutation.mutate(id)
    }
  }

  const toggleKeyVisibility = (id: string) => {
    setVisibleKeys((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  const formatDate = (dateString: string | null) => {
    if (!dateString) return 'Never'
    return new Date(dateString).toLocaleDateString()
  }

  const isExpired = (expiresAt: string | null) => {
    if (!expiresAt) return false
    return new Date(expiresAt) < new Date()
  }

  return (
    <Container maxWidth="lg">
      <Box sx={{ padding: spacing[4] }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 4 }}>
          <Typography variant="h4" component="h1">
            API Key Management
          </Typography>
          <Button
            variant="contained"
            onClick={() => setCreateDialogOpen(true)}
          >
            Create API Key
          </Button>
        </Box>

        {error && (
          <Alert
            severity="error"
            message={error}
            dismissible
            onClose={() => setError(null)}
            className="mb-4"
          />
        )}

        {listError && (
          <Alert
            severity="error"
            message="Failed to load API keys. Please try again."
            className="mb-4"
          />
        )}

        {isLoading ? (
          <Box sx={{ textAlign: 'center', py: 4 }}>
            <Typography>Loading API keys...</Typography>
          </Box>
        ) : (
          <TableContainer component={Paper}>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Name</TableCell>
                  <TableCell>Scopes</TableCell>
                  <TableCell>Created</TableCell>
                  <TableCell>Last Used</TableCell>
                  <TableCell>Expires</TableCell>
                  <TableCell align="right">Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {apiKeysData?.results && apiKeysData.results.length > 0 ? (
                  apiKeysData.results.map((key) => (
                    <TableRow key={key.id}>
                      <TableCell>{key.name}</TableCell>
                      <TableCell>
                        {key.scopes.length > 0 ? (
                          <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                            {key.scopes.map((scope) => (
                              <Chip key={scope} label={scope} size="small" />
                            ))}
                          </Box>
                        ) : (
                          <Typography variant="body2" color="text.secondary">
                            No scopes
                          </Typography>
                        )}
                      </TableCell>
                      <TableCell>{formatDate(key.created_at)}</TableCell>
                      <TableCell>{formatDate(key.last_used_at)}</TableCell>
                      <TableCell>
                        {isExpired(key.expires_at) ? (
                          <Chip label="Expired" color="error" size="small" />
                        ) : (
                          formatDate(key.expires_at)
                        )}
                      </TableCell>
                      <TableCell align="right">
                        <IconButton
                          size="small"
                          onClick={() => handleDelete(key.id)}
                          disabled={deleteMutation.isPending}
                        >
                          <DeleteIcon />
                        </IconButton>
                      </TableCell>
                    </TableRow>
                  ))
                ) : (
                  <TableRow>
                    <TableCell colSpan={6} align="center">
                      <Typography variant="body2" color="text.secondary" sx={{ py: 4 }}>
                        No API keys found. Create your first API key to get started.
                      </Typography>
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </TableContainer>
        )}

        {/* Create API Key Dialog */}
        <Dialog open={createDialogOpen} onClose={handleCloseCreateDialog} maxWidth="sm" fullWidth>
          <DialogTitle>Create API Key</DialogTitle>
          <form onSubmit={handleSubmit(onSubmit)}>
            <DialogContent>
              {newApiKey && (
                <MuiAlert severity="success" sx={{ mb: 2 }}>
                  <Typography variant="subtitle2" gutterBottom>
                    API Key Created Successfully
                  </Typography>
                  <Typography variant="body2" component="div" sx={{ mt: 1 }}>
                    <strong>Important:</strong> Copy this API key now. You won't be able to see it again.
                  </Typography>
                  <Box
                    sx={{
                      mt: 2,
                      p: 2,
                      bgcolor: 'grey.100',
                      borderRadius: 1,
                      fontFamily: 'monospace',
                      wordBreak: 'break-all',
                    }}
                  >
                    {visibleKeys.has('new') ? newApiKey : '•'.repeat(40)}
                  </Box>
                  <Button
                    size="small"
                    startIcon={visibleKeys.has('new') ? <VisibilityOffIcon /> : <VisibilityIcon />}
                    onClick={() => toggleKeyVisibility('new')}
                    sx={{ mt: 1 }}
                  >
                    {visibleKeys.has('new') ? 'Hide' : 'Show'} Key
                  </Button>
                </MuiAlert>
              )}

              {error && (
                <Alert
                  severity="error"
                  message={error}
                  dismissible
                  onClose={() => setError(null)}
                  className="mb-4"
                />
              )}

              <Box sx={{ display: 'flex', flexDirection: 'column', gap: spacing[3] }}>
                <TextInput
                  {...register('name')}
                  type="text"
                  label="API Key Name"
                  required
                  error={errors.name?.message || null}
                  disabled={isSubmitting || createMutation.isPending || !!newApiKey}
                  autoFocus
                  helperText="A descriptive name for this API key"
                />

                <TextInput
                  {...register('scopes')}
                  type="text"
                  label="Scopes (Optional)"
                  error={errors.scopes?.message || null}
                  disabled={isSubmitting || createMutation.isPending || !!newApiKey}
                  helperText="Comma-separated list of scopes (e.g., assets:read, assets:write)"
                />

                <TextInput
                  {...register('expires_in_days')}
                  type="number"
                  label="Expires In Days (Optional)"
                  error={errors.expires_in_days?.message || null}
                  disabled={isSubmitting || createMutation.isPending || !!newApiKey}
                  helperText="Number of days until expiration (1-365). Leave empty for no expiration."
                />
              </Box>
            </DialogContent>
            <DialogActions>
              <Button onClick={handleCloseCreateDialog} disabled={isSubmitting || createMutation.isPending}>
                {newApiKey ? 'Close' : 'Cancel'}
              </Button>
              {!newApiKey && (
                <Button
                  type="submit"
                  variant="contained"
                  disabled={isSubmitting || createMutation.isPending}
                >
                  {isSubmitting || createMutation.isPending ? 'Creating...' : 'Create'}
                </Button>
              )}
            </DialogActions>
          </form>
        </Dialog>
      </Box>
    </Container>
  )
}

