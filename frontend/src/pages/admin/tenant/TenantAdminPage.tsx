/**
 * Tenant Admin Page
 *
 * Comprehensive tenant administration page with:
 * - Tenant information display and editing
 * - Tenant users display and management
 * - Tenant settings display and editing
 * - User management (create, update, delete, invite)
 */

import React, { useState, useMemo, useCallback } from 'react'
import {
  Container,
  Box,
  Typography,
  Button,
  Paper,
  Grid,
  Chip,
  IconButton,
  Tooltip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Alert,
  Tabs,
  Tab,
  Divider,
  Switch,
  FormControlLabel,
  CircularProgress,
} from '@mui/material'
import {
  Edit as EditIcon,
  Refresh as RefreshIcon,
  Add as AddIcon,
  Delete as DeleteIcon,
  Email as EmailIcon,
  Save as SaveIcon,
  Cancel as CancelIcon,
  PersonAdd as PersonAddIcon,
} from '@mui/icons-material'
import { useTenant, useTenantConfig } from '@/hooks'
import { useUpdateTenant, useUpdateTenantConfig } from '@/hooks'
import { useUsers } from '@/hooks'
import { useCreateUser, useUpdateUser, useDeleteUser, useInviteUser } from '@/hooks'
import { listRoles } from '@/lib/api/users'
import { useQuery } from '@tanstack/react-query'
import type { Tenant, TenantConfig, User, UserStatus } from '@/lib/api/users'
import { LoadingState } from '@/components/loading/LoadingState'
import { ErrorState } from '@/components/utility/ErrorState'
import { Badge } from '@/components/data-display/Badge'
import { EnhancedPagination } from '@/components/navigation/Pagination'
import { NoDataEmptyState } from '@/components/utility/EmptyState'
import { useToastManager } from '@/components/feedback/Toast/useToastManager'
import { formatDistanceToNow } from 'date-fns'

/**
 * Get tenant status badge variant
 */
function getTenantStatusBadgeVariant(
  status?: string
): 'success' | 'warning' | 'error' | 'info' | 'neutral' {
  if (!status) return 'neutral'
  switch (status) {
    case 'ACTIVE':
      return 'success'
    case 'SUSPENDED':
      return 'warning'
    case 'DELETED':
      return 'error'
    default:
      return 'neutral'
  }
}

/**
 * Get user status badge variant
 */
function getUserStatusBadgeVariant(status: UserStatus): 'success' | 'warning' | 'error' | 'info' | 'neutral' {
  switch (status) {
    case 'ACTIVE':
      return 'success'
    case 'INVITED':
      return 'info'
    case 'DISABLED':
      return 'error'
    case 'SUSPENDED':
      return 'warning'
    default:
      return 'neutral'
  }
}

/**
 * Format date for display
 */
function formatDate(dateString: string | null | undefined): string {
  if (!dateString) return '—'
  try {
    return formatDistanceToNow(new Date(dateString), { addSuffix: true })
  } catch {
    return dateString
  }
}

/**
 * Tenant Admin Page Component
 */
export const TenantAdminPage: React.FC = () => {
  const { showToast } = useToastManager()

  // Tab state
  const [activeTab, setActiveTab] = useState(0)

  // Pagination state for users
  const [usersPage, setUsersPage] = useState(1)
  const [usersPageSize, setUsersPageSize] = useState(20)

  // Filter state for users
  const [userStatusFilter, setUserStatusFilter] = useState<UserStatus | ''>('')

  // Edit state
  const [isEditingTenant, setIsEditingTenant] = useState(false)
  const [isEditingConfig, setIsEditingConfig] = useState(false)
  const [editedTenant, setEditedTenant] = useState<Partial<Tenant>>({})
  const [editedConfig, setEditedConfig] = useState<Partial<TenantConfig>>({})

  // Dialog state
  const [isCreateUserDialogOpen, setIsCreateUserDialogOpen] = useState(false)
  const [isInviteUserDialogOpen, setIsInviteUserDialogOpen] = useState(false)
  const [isDeleteUserDialogOpen, setIsDeleteUserDialogOpen] = useState(false)
  const [selectedUser, setSelectedUser] = useState<User | null>(null)

  // Form state
  const [newUser, setNewUser] = useState({
    email: '',
    display_name: '',
    password: '',
    role_ids: [] as string[],
    send_invitation: true,
  })
  const [inviteUser, setInviteUser] = useState({
    email: '',
    display_name: '',
    role_ids: [] as string[],
  })

  // Fetch current tenant
  const {
    data: tenant,
    isLoading: isLoadingTenant,
    error: tenantError,
    refetch: refetchTenant,
  } = useTenant()

  // Fetch tenant config
  const {
    data: config,
    isLoading: isLoadingConfig,
    error: configError,
    refetch: refetchConfig,
  } = useTenantConfig(tenant?.id)

  // Fetch users
  const {
    data: usersData,
    isLoading: isLoadingUsers,
    error: usersError,
    refetch: refetchUsers,
  } = useUsers({
    page: usersPage,
    page_size: usersPageSize,
    status: userStatusFilter || undefined,
    ordering: '-created_at',
  })

  // Fetch roles
  const { data: rolesData } = useQuery({
    queryKey: ['roles'],
    queryFn: () => listRoles({ page_size: 100 }),
  })

  // Mutations
  const updateTenantMutation = useUpdateTenant({
    onSuccess: () => {
      showToast({ message: 'Tenant updated successfully', severity: 'success' })
      setIsEditingTenant(false)
      refetchTenant()
    },
    onError: (error) => {
      showToast({ message: error.message || 'Failed to update tenant', severity: 'error' })
    },
  })

  const updateConfigMutation = useUpdateTenantConfig({
    onSuccess: () => {
      showToast({ message: 'Tenant settings updated successfully', severity: 'success' })
      setIsEditingConfig(false)
      refetchConfig()
    },
    onError: (error) => {
      showToast({ message: error.message || 'Failed to update settings', severity: 'error' })
    },
  })

  const createUserMutation = useCreateUser({
    onSuccess: () => {
      showToast({ message: 'User created successfully', severity: 'success' })
      setIsCreateUserDialogOpen(false)
      setNewUser({ email: '', display_name: '', password: '', role_ids: [], send_invitation: true })
      refetchUsers()
    },
    onError: (error) => {
      showToast({ message: error.message || 'Failed to create user', severity: 'error' })
    },
  })

  const updateUserMutation = useUpdateUser({
    onSuccess: () => {
      showToast({ message: 'User updated successfully', severity: 'success' })
      refetchUsers()
    },
    onError: (error) => {
      showToast({ message: error.message || 'Failed to update user', severity: 'error' })
    },
  })

  const deleteUserMutation = useDeleteUser({
    onSuccess: () => {
      showToast({ message: 'User deleted successfully', severity: 'success' })
      setIsDeleteUserDialogOpen(false)
      setSelectedUser(null)
      refetchUsers()
    },
    onError: (error) => {
      showToast({ message: error.message || 'Failed to delete user', severity: 'error' })
    },
  })

  const inviteUserMutation = useInviteUser({
    onSuccess: () => {
      showToast({ message: 'Invitation sent successfully', severity: 'success' })
      setIsInviteUserDialogOpen(false)
      setInviteUser({ email: '', display_name: '', role_ids: [] })
      refetchUsers()
    },
    onError: (error) => {
      showToast({ message: error.message || 'Failed to send invitation', severity: 'error' })
    },
  })

  // Handle edit tenant
  const handleEditTenant = useCallback(() => {
    if (tenant) {
      setEditedTenant({
        name: tenant.name,
        slug: tenant.slug,
        kyc_status: tenant.kyc_status,
        region: tenant.region,
      })
      setIsEditingTenant(true)
    }
  }, [tenant])

  const handleCancelEditTenant = useCallback(() => {
    setIsEditingTenant(false)
    setEditedTenant({})
  }, [])

  const handleSaveTenant = useCallback(() => {
    if (tenant) {
      updateTenantMutation.mutate({
        id: tenant.id,
        data: editedTenant,
      })
    }
  }, [tenant, editedTenant, updateTenantMutation])

  // Handle edit config
  const handleEditConfig = useCallback(() => {
    if (config) {
      setEditedConfig({
        default_dq_profile: config.default_dq_profile,
        allowed_compliance_regimes: config.allowed_compliance_regimes,
        default_compliance_regimes: config.default_compliance_regimes,
        data_retention_days: config.data_retention_days,
        max_file_size_bytes: config.max_file_size_bytes,
        max_job_concurrency: config.max_job_concurrency,
        max_queued_jobs: config.max_queued_jobs,
      })
      setIsEditingConfig(true)
    }
  }, [config])

  const handleCancelEditConfig = useCallback(() => {
    setIsEditingConfig(false)
    setEditedConfig({})
  }, [])

  const handleSaveConfig = useCallback(() => {
    if (tenant && config) {
      updateConfigMutation.mutate({
        tenantId: tenant.id,
        data: editedConfig,
      })
    }
  }, [tenant, config, editedConfig, updateConfigMutation])

  // Handle create user
  const handleCreateUser = useCallback(() => {
    createUserMutation.mutate({
      email: newUser.email,
      display_name: newUser.display_name || undefined,
      password: newUser.password || undefined,
      role_ids: newUser.role_ids.length > 0 ? newUser.role_ids : undefined,
      send_invitation: newUser.send_invitation,
    })
  }, [newUser, createUserMutation])

  // Handle invite user
  const handleInviteUser = useCallback(() => {
    inviteUserMutation.mutate({
      email: inviteUser.email,
      display_name: inviteUser.display_name || undefined,
      role_ids: inviteUser.role_ids.length > 0 ? inviteUser.role_ids : undefined,
    })
  }, [inviteUser, inviteUserMutation])

  // Handle delete user
  const handleDeleteUser = useCallback(() => {
    if (selectedUser) {
      deleteUserMutation.mutate(selectedUser.id)
    }
  }, [selectedUser, deleteUserMutation])

  // Loading state
  if (isLoadingTenant) {
    return (
      <Container maxWidth="xl">
        <Box sx={{ py: 4 }}>
          <LoadingState message="Loading tenant information..." />
        </Box>
      </Container>
    )
  }

  // Error state
  if (tenantError || !tenant) {
    return (
      <Container maxWidth="xl">
        <Box sx={{ py: 4 }}>
          <ErrorState
            title="Failed to load tenant"
            message={tenantError?.message || 'Tenant not found'}
            onRetry={() => refetchTenant()}
          />
        </Box>
      </Container>
    )
  }

  return (
    <Container maxWidth="xl">
      <Box sx={{ py: 4 }}>
        {/* Header */}
        <Box sx={{ mb: 4, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <Box>
            <Typography variant="h4" gutterBottom>
              Tenant Administration
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Manage tenant information, users, and settings
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', gap: 2 }}>
            <Tooltip title="Refresh">
              <IconButton onClick={() => { refetchTenant(); refetchConfig(); refetchUsers() }}>
                <RefreshIcon />
              </IconButton>
            </Tooltip>
          </Box>
        </Box>

        {/* Tabs */}
        <Paper sx={{ mb: 3 }}>
          <Tabs value={activeTab} onChange={(_, newValue) => setActiveTab(newValue)}>
            <Tab label="Information" />
            <Tab label="Users" />
            <Tab label="Settings" />
          </Tabs>
        </Paper>

        {/* Tab Content */}
        {activeTab === 0 && (
          <Paper sx={{ p: 3 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
              <Typography variant="h6" sx={{ fontWeight: 600 }}>
                Tenant Information
              </Typography>
              {!isEditingTenant ? (
                <Button startIcon={<EditIcon />} onClick={handleEditTenant}>
                  Edit
                </Button>
              ) : (
                <Box sx={{ display: 'flex', gap: 1 }}>
                  <Button
                    startIcon={<SaveIcon />}
                    variant="contained"
                    onClick={handleSaveTenant}
                    disabled={updateTenantMutation.isPending}
                  >
                    Save
                  </Button>
                  <Button startIcon={<CancelIcon />} onClick={handleCancelEditTenant}>
                    Cancel
                  </Button>
                </Box>
              )}
            </Box>

            <Divider sx={{ mb: 3 }} />

            {isEditingTenant ? (
              <Grid container spacing={3}>
                <Grid item xs={12} md={6}>
                  <TextField
                    fullWidth
                    label="Name"
                    value={editedTenant.name || ''}
                    onChange={(e) => setEditedTenant({ ...editedTenant, name: e.target.value })}
                  />
                </Grid>
                <Grid item xs={12} md={6}>
                  <TextField
                    fullWidth
                    label="Slug"
                    value={editedTenant.slug || ''}
                    onChange={(e) => setEditedTenant({ ...editedTenant, slug: e.target.value })}
                    helperText="URL-safe identifier"
                  />
                </Grid>
                <Grid item xs={12} md={6}>
                  <FormControl fullWidth>
                    <InputLabel>KYC Status</InputLabel>
                    <Select
                      value={editedTenant.kyc_status || 'UNVERIFIED'}
                      label="KYC Status"
                      onChange={(e) => setEditedTenant({ ...editedTenant, kyc_status: e.target.value as any })}
                    >
                      <MenuItem value="UNVERIFIED">Unverified</MenuItem>
                      <MenuItem value="VERIFIED">Verified</MenuItem>
                    </Select>
                  </FormControl>
                </Grid>
                <Grid item xs={12} md={6}>
                  <TextField
                    fullWidth
                    label="Region"
                    value={editedTenant.region || ''}
                    onChange={(e) => setEditedTenant({ ...editedTenant, region: e.target.value || null })}
                    placeholder="e.g., us-east-1"
                  />
                </Grid>
              </Grid>
            ) : (
              <Grid container spacing={3}>
                <Grid item xs={12} md={6}>
                  <Typography variant="body2" color="text.secondary">
                    Name
                  </Typography>
                  <Typography variant="body1" sx={{ fontWeight: 600, mt: 0.5 }}>
                    {tenant.name}
                  </Typography>
                </Grid>
                <Grid item xs={12} md={6}>
                  <Typography variant="body2" color="text.secondary">
                    Slug
                  </Typography>
                  <Typography variant="body1" sx={{ fontFamily: 'monospace', mt: 0.5 }}>
                    {tenant.slug}
                  </Typography>
                </Grid>
                <Grid item xs={12} md={6}>
                  <Typography variant="body2" color="text.secondary">
                    Status
                  </Typography>
                  <Box sx={{ mt: 0.5 }}>
                    <Badge variant={getTenantStatusBadgeVariant(tenant.status)} size="sm">
                      {tenant.status}
                    </Badge>
                  </Box>
                </Grid>
                <Grid item xs={12} md={6}>
                  <Typography variant="body2" color="text.secondary">
                    KYC Status
                  </Typography>
                  <Box sx={{ mt: 0.5 }}>
                    <Chip
                      label={tenant.kyc_status}
                      size="small"
                      color={tenant.kyc_status === 'VERIFIED' ? 'success' : 'default'}
                      variant="outlined"
                    />
                  </Box>
                </Grid>
                <Grid item xs={12} md={6}>
                  <Typography variant="body2" color="text.secondary">
                    Region
                  </Typography>
                  <Typography variant="body1" sx={{ mt: 0.5 }}>
                    {tenant.region || '—'}
                  </Typography>
                </Grid>
                <Grid item xs={12} md={6}>
                  <Typography variant="body2" color="text.secondary">
                    Created
                  </Typography>
                  <Typography variant="body1" sx={{ mt: 0.5 }}>
                    {formatDate(tenant.created_at)}
                  </Typography>
                </Grid>
              </Grid>
            )}
          </Paper>
        )}

        {activeTab === 1 && (
          <Paper sx={{ p: 3 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
              <Typography variant="h6" sx={{ fontWeight: 600 }}>
                Tenant Users
              </Typography>
              <Box sx={{ display: 'flex', gap: 2 }}>
                <Button
                  variant="outlined"
                  startIcon={<EmailIcon />}
                  onClick={() => setIsInviteUserDialogOpen(true)}
                >
                  Invite User
                </Button>
                <Button
                  variant="contained"
                  startIcon={<PersonAddIcon />}
                  onClick={() => setIsCreateUserDialogOpen(true)}
                >
                  Create User
                </Button>
              </Box>
            </Box>

            <Divider sx={{ mb: 3 }} />

            {/* Filters */}
            <Box sx={{ mb: 3, display: 'flex', gap: 2 }}>
              <FormControl size="small" sx={{ minWidth: 200 }}>
                <InputLabel>Status</InputLabel>
                <Select
                  value={userStatusFilter}
                  label="Status"
                  onChange={(e) => {
                    setUserStatusFilter(e.target.value as UserStatus | '')
                    setUsersPage(1)
                  }}
                >
                  <MenuItem value="">
                    <em>All Statuses</em>
                  </MenuItem>
                  <MenuItem value="ACTIVE">Active</MenuItem>
                  <MenuItem value="INVITED">Invited</MenuItem>
                  <MenuItem value="DISABLED">Disabled</MenuItem>
                  <MenuItem value="SUSPENDED">Suspended</MenuItem>
                </Select>
              </FormControl>
            </Box>

            {/* Users Table */}
            {isLoadingUsers ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
                <CircularProgress />
              </Box>
            ) : usersError ? (
              <Alert severity="error">{usersError.message}</Alert>
            ) : !usersData?.results || usersData.results.length === 0 ? (
              <NoDataEmptyState
                title="No users found"
                description="Create or invite users to get started."
              />
            ) : (
              <>
                <TableContainer>
                  <Table>
                    <TableHead>
                      <TableRow>
                        <TableCell>Email</TableCell>
                        <TableCell>Display Name</TableCell>
                        <TableCell>Status</TableCell>
                        <TableCell>Roles</TableCell>
                        <TableCell>Created</TableCell>
                        <TableCell align="right">Actions</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {usersData.results.map((user) => (
                        <TableRow key={user.id}>
                          <TableCell>{user.email}</TableCell>
                          <TableCell>{user.display_name || '—'}</TableCell>
                          <TableCell>
                            <Badge variant={getUserStatusBadgeVariant(user.status)} size="sm">
                              {user.status}
                            </Badge>
                          </TableCell>
                          <TableCell>
                            {user.roles && user.roles.length > 0 ? (
                              <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                                {user.roles.map((role) => (
                                  <Chip key={role.id} label={role.name} size="small" variant="outlined" />
                                ))}
                              </Box>
                            ) : (
                              '—'
                            )}
                          </TableCell>
                          <TableCell>{formatDate(user.created_at)}</TableCell>
                          <TableCell align="right">
                            <Tooltip title="Delete">
                              <IconButton
                                size="small"
                                onClick={() => {
                                  setSelectedUser(user)
                                  setIsDeleteUserDialogOpen(true)
                                }}
                                color="error"
                              >
                                <DeleteIcon fontSize="small" />
                              </IconButton>
                            </Tooltip>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>

                {/* Pagination */}
                {usersData && usersData.count > usersPageSize && (
                  <Box sx={{ mt: 3, display: 'flex', justifyContent: 'center' }}>
                    <EnhancedPagination
                      count={Math.ceil(usersData.count / usersPageSize)}
                      page={usersPage}
                      onChange={(_, newPage) => setUsersPage(newPage)}
                      pageSize={usersPageSize}
                      onPageSizeChange={setUsersPageSize}
                      showPageSizeSelector
                    />
                  </Box>
                )}
              </>
            )}
          </Paper>
        )}

        {activeTab === 2 && (
          <Paper sx={{ p: 3 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
              <Typography variant="h6" sx={{ fontWeight: 600 }}>
                Tenant Settings
              </Typography>
              {!isEditingConfig ? (
                <Button startIcon={<EditIcon />} onClick={handleEditConfig}>
                  Edit
                </Button>
              ) : (
                <Box sx={{ display: 'flex', gap: 1 }}>
                  <Button
                    startIcon={<SaveIcon />}
                    variant="contained"
                    onClick={handleSaveConfig}
                    disabled={updateConfigMutation.isPending}
                  >
                    Save
                  </Button>
                  <Button startIcon={<CancelIcon />} onClick={handleCancelEditConfig}>
                    Cancel
                  </Button>
                </Box>
              )}
            </Box>

            <Divider sx={{ mb: 3 }} />

            {isLoadingConfig ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
                <CircularProgress />
              </Box>
            ) : configError ? (
              <Alert severity="error">{configError.message}</Alert>
            ) : config ? (
              isEditingConfig ? (
                <Grid container spacing={3}>
                  <Grid item xs={12} md={6}>
                    <TextField
                      fullWidth
                      label="Default DQ Profile"
                      value={editedConfig.default_dq_profile || ''}
                      onChange={(e) => setEditedConfig({ ...editedConfig, default_dq_profile: e.target.value || null })}
                      placeholder="e.g., intake_basic_gx"
                    />
                  </Grid>
                  <Grid item xs={12} md={6}>
                    <TextField
                      fullWidth
                      type="number"
                      label="Data Retention (days)"
                      value={editedConfig.data_retention_days || ''}
                      onChange={(e) => setEditedConfig({ ...editedConfig, data_retention_days: e.target.value ? parseInt(e.target.value) : null })}
                      inputProps={{ min: 90, max: 3650 }}
                    />
                  </Grid>
                  <Grid item xs={12} md={6}>
                    <TextField
                      fullWidth
                      type="number"
                      label="Max File Size (bytes)"
                      value={editedConfig.max_file_size_bytes || ''}
                      onChange={(e) => setEditedConfig({ ...editedConfig, max_file_size_bytes: e.target.value ? parseInt(e.target.value) : null })}
                    />
                  </Grid>
                  <Grid item xs={12} md={6}>
                    <TextField
                      fullWidth
                      type="number"
                      label="Max Job Concurrency"
                      value={editedConfig.max_job_concurrency || ''}
                      onChange={(e) => setEditedConfig({ ...editedConfig, max_job_concurrency: e.target.value ? parseInt(e.target.value) : null })}
                    />
                  </Grid>
                  <Grid item xs={12} md={6}>
                    <TextField
                      fullWidth
                      type="number"
                      label="Max Queued Jobs"
                      value={editedConfig.max_queued_jobs || ''}
                      onChange={(e) => setEditedConfig({ ...editedConfig, max_queued_jobs: e.target.value ? parseInt(e.target.value) : null })}
                    />
                  </Grid>
                </Grid>
              ) : (
                <Grid container spacing={3}>
                  <Grid item xs={12} md={6}>
                    <Typography variant="body2" color="text.secondary">
                      Default DQ Profile
                    </Typography>
                    <Typography variant="body1" sx={{ mt: 0.5 }}>
                      {config.default_dq_profile || '—'}
                    </Typography>
                  </Grid>
                  <Grid item xs={12} md={6}>
                    <Typography variant="body2" color="text.secondary">
                      Data Retention (days)
                    </Typography>
                    <Typography variant="body1" sx={{ mt: 0.5 }}>
                      {config.data_retention_days || '—'}
                    </Typography>
                  </Grid>
                  <Grid item xs={12} md={6}>
                    <Typography variant="body2" color="text.secondary">
                      Max File Size (bytes)
                    </Typography>
                    <Typography variant="body1" sx={{ mt: 0.5 }}>
                      {config.max_file_size_bytes ? config.max_file_size_bytes.toLocaleString() : '—'}
                    </Typography>
                  </Grid>
                  <Grid item xs={12} md={6}>
                    <Typography variant="body2" color="text.secondary">
                      Max Job Concurrency
                    </Typography>
                    <Typography variant="body1" sx={{ mt: 0.5 }}>
                      {config.max_job_concurrency || '—'}
                    </Typography>
                  </Grid>
                  <Grid item xs={12} md={6}>
                    <Typography variant="body2" color="text.secondary">
                      Max Queued Jobs
                    </Typography>
                    <Typography variant="body1" sx={{ mt: 0.5 }}>
                      {config.max_queued_jobs || '—'}
                    </Typography>
                  </Grid>
                </Grid>
              )
            ) : null}
          </Paper>
        )}

        {/* Create User Dialog */}
        <Dialog open={isCreateUserDialogOpen} onClose={() => setIsCreateUserDialogOpen(false)} maxWidth="sm" fullWidth>
          <DialogTitle>Create User</DialogTitle>
          <DialogContent>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 2 }}>
              <TextField
                fullWidth
                label="Email"
                type="email"
                value={newUser.email}
                onChange={(e) => setNewUser({ ...newUser, email: e.target.value })}
                required
              />
              <TextField
                fullWidth
                label="Display Name"
                value={newUser.display_name}
                onChange={(e) => setNewUser({ ...newUser, display_name: e.target.value })}
              />
              <TextField
                fullWidth
                label="Password"
                type="password"
                value={newUser.password}
                onChange={(e) => setNewUser({ ...newUser, password: e.target.value })}
                helperText="Leave empty to send invitation email"
              />
              <FormControl fullWidth>
                <InputLabel>Roles</InputLabel>
                <Select
                  multiple
                  value={newUser.role_ids}
                  label="Roles"
                  onChange={(e) => setNewUser({ ...newUser, role_ids: e.target.value as string[] })}
                >
                  {rolesData?.results.map((role) => (
                    <MenuItem key={role.id} value={role.id}>
                      {role.name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
              <FormControlLabel
                control={
                  <Switch
                    checked={newUser.send_invitation}
                    onChange={(e) => setNewUser({ ...newUser, send_invitation: e.target.checked })}
                  />
                }
                label="Send invitation email"
              />
            </Box>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setIsCreateUserDialogOpen(false)}>Cancel</Button>
            <Button
              variant="contained"
              onClick={handleCreateUser}
              disabled={!newUser.email || createUserMutation.isPending}
            >
              {createUserMutation.isPending ? 'Creating...' : 'Create'}
            </Button>
          </DialogActions>
        </Dialog>

        {/* Invite User Dialog */}
        <Dialog open={isInviteUserDialogOpen} onClose={() => setIsInviteUserDialogOpen(false)} maxWidth="sm" fullWidth>
          <DialogTitle>Invite User</DialogTitle>
          <DialogContent>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 2 }}>
              <TextField
                fullWidth
                label="Email"
                type="email"
                value={inviteUser.email}
                onChange={(e) => setInviteUser({ ...inviteUser, email: e.target.value })}
                required
              />
              <TextField
                fullWidth
                label="Display Name"
                value={inviteUser.display_name}
                onChange={(e) => setInviteUser({ ...inviteUser, display_name: e.target.value })}
              />
              <FormControl fullWidth>
                <InputLabel>Roles</InputLabel>
                <Select
                  multiple
                  value={inviteUser.role_ids}
                  label="Roles"
                  onChange={(e) => setInviteUser({ ...inviteUser, role_ids: e.target.value as string[] })}
                >
                  {rolesData?.results.map((role) => (
                    <MenuItem key={role.id} value={role.id}>
                      {role.name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Box>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setIsInviteUserDialogOpen(false)}>Cancel</Button>
            <Button
              variant="contained"
              onClick={handleInviteUser}
              disabled={!inviteUser.email || inviteUserMutation.isPending}
            >
              {inviteUserMutation.isPending ? 'Sending...' : 'Send Invitation'}
            </Button>
          </DialogActions>
        </Dialog>

        {/* Delete User Dialog */}
        <Dialog open={isDeleteUserDialogOpen} onClose={() => setIsDeleteUserDialogOpen(false)}>
          <DialogTitle>Delete User</DialogTitle>
          <DialogContent>
            <Typography>
              Are you sure you want to delete user <strong>{selectedUser?.email}</strong>? This action cannot be undone.
            </Typography>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setIsDeleteUserDialogOpen(false)}>Cancel</Button>
            <Button
              variant="contained"
              color="error"
              onClick={handleDeleteUser}
              disabled={deleteUserMutation.isPending}
            >
              {deleteUserMutation.isPending ? 'Deleting...' : 'Delete'}
            </Button>
          </DialogActions>
        </Dialog>
      </Box>
    </Container>
  )
}

TenantAdminPage.displayName = 'TenantAdminPage'

