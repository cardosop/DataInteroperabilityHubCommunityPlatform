/**
 * Active Sessions Management Page
 *
 * Page for viewing and managing active user sessions (refresh tokens).
 * Users can see all their active sessions and revoke them individually.
 */

import React, { useState } from 'react'
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
  Chip,
  IconButton,
  Alert as MuiAlert,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
} from '@mui/material'
import { Delete as DeleteIcon } from '@mui/icons-material'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Alert } from '@/components/feedback'
import { listActiveSessions, revokeSession, type ActiveSession } from '@/lib/api/auth'
import { spacing } from '@/styles/tokens'

/**
 * Format date to readable string
 */
function formatDate(dateString: string): string {
  const date = new Date(dateString)
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/**
 * Calculate time until expiration
 */
function getTimeUntilExpiration(expiresAt: string): string {
  const now = new Date()
  const expires = new Date(expiresAt)
  const diffMs = expires.getTime() - now.getTime()

  if (diffMs <= 0) {
    return 'Expired'
  }

  const diffSeconds = Math.floor(diffMs / 1000)
  const diffMinutes = Math.floor(diffSeconds / 60)
  const diffHours = Math.floor(diffMinutes / 60)
  const diffDays = Math.floor(diffHours / 24)

  if (diffDays > 0) {
    return `${diffDays} day${diffDays !== 1 ? 's' : ''}`
  } else if (diffHours > 0) {
    return `${diffHours} hour${diffHours !== 1 ? 's' : ''}`
  } else if (diffMinutes > 0) {
    return `${diffMinutes} minute${diffMinutes !== 1 ? 's' : ''}`
  } else {
    return `${diffSeconds} second${diffSeconds !== 1 ? 's' : ''}`
  }
}

/**
 * Check if session is expired
 */
function isSessionExpired(expiresAt: string): boolean {
  return new Date(expiresAt) <= new Date()
}

/**
 * Active Sessions Management Page Component
 */
export const ActiveSessionsPage: React.FC = () => {
  const queryClient = useQueryClient()
  const [revokeDialogOpen, setRevokeDialogOpen] = useState(false)
  const [sessionToRevoke, setSessionToRevoke] = useState<ActiveSession | null>(null)
  const [error, setError] = useState<string | null>(null)

  const {
    data: sessions,
    isLoading,
    error: listError,
  } = useQuery({
    queryKey: ['auth', 'active-sessions'],
    queryFn: () => listActiveSessions(),
  })

  const revokeMutation = useMutation({
    mutationFn: (sessionId: string) => revokeSession(sessionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['auth', 'active-sessions'] })
      setRevokeDialogOpen(false)
      setSessionToRevoke(null)
      setError(null)
    },
    onError: (error: any) => {
      const errorMessage =
        error?.response?.data?.error?.message ||
        error?.message ||
        'Failed to revoke session. Please try again.'
      setError(errorMessage)
    },
  })

  const handleRevokeClick = (session: ActiveSession) => {
    setSessionToRevoke(session)
    setRevokeDialogOpen(true)
    setError(null)
  }

  const handleRevokeConfirm = () => {
    if (sessionToRevoke) {
      revokeMutation.mutate(sessionToRevoke.id)
    }
  }

  const handleRevokeCancel = () => {
    setRevokeDialogOpen(false)
    setSessionToRevoke(null)
    setError(null)
  }

  const activeSessions = sessions?.filter(
    (session) => !session.revoked_at && !isSessionExpired(session.expires_at)
  ) || []

  const revokedSessions = sessions?.filter((session) => session.revoked_at) || []

  const expiredSessions = sessions?.filter(
    (session) => !session.revoked_at && isSessionExpired(session.expires_at)
  ) || []

  return (
    <Container maxWidth="lg">
      <Box sx={{ padding: spacing[4] }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 4 }}>
          <Typography variant="h4" component="h1">
            Active Sessions
          </Typography>
          <Button
            variant="outlined"
            onClick={() => queryClient.invalidateQueries({ queryKey: ['auth', 'active-sessions'] })}
            disabled={isLoading}
          >
            Refresh
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
            message="Failed to load active sessions. Please try again."
            className="mb-4"
          />
        )}

        {isLoading ? (
          <Box sx={{ textAlign: 'center', py: 4 }}>
            <Typography>Loading sessions...</Typography>
          </Box>
        ) : (
          <>
            {/* Active Sessions */}
            <Box sx={{ mb: 4 }}>
              <Typography variant="h6" gutterBottom>
                Active Sessions ({activeSessions.length})
              </Typography>
              {activeSessions.length > 0 ? (
                <TableContainer component={Paper} sx={{ mt: 2 }}>
                  <Table>
                    <TableHead>
                      <TableRow>
                        <TableCell>Status</TableCell>
                        <TableCell>Created</TableCell>
                        <TableCell>Expires</TableCell>
                        <TableCell>Time Remaining</TableCell>
                        <TableCell align="right">Actions</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {activeSessions.map((session) => (
                        <TableRow key={session.id}>
                          <TableCell>
                            {session.is_current ? (
                              <Chip label="Current Session" color="primary" size="small" />
                            ) : (
                              <Chip label="Active" color="success" size="small" />
                            )}
                          </TableCell>
                          <TableCell>{formatDate(session.created_at)}</TableCell>
                          <TableCell>{formatDate(session.expires_at)}</TableCell>
                          <TableCell>{getTimeUntilExpiration(session.expires_at)}</TableCell>
                          <TableCell align="right">
                            {!session.is_current && (
                              <IconButton
                                size="small"
                                onClick={() => handleRevokeClick(session)}
                                disabled={revokeMutation.isPending}
                                color="error"
                                aria-label="Revoke session"
                              >
                                <DeleteIcon />
                              </IconButton>
                            )}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              ) : (
                <MuiAlert severity="info" sx={{ mt: 2 }}>
                  No active sessions found.
                </MuiAlert>
              )}
            </Box>

            {/* Expired Sessions */}
            {expiredSessions.length > 0 && (
              <Box sx={{ mb: 4 }}>
                <Typography variant="h6" gutterBottom>
                  Expired Sessions ({expiredSessions.length})
                </Typography>
                <TableContainer component={Paper} sx={{ mt: 2 }}>
                  <Table>
                    <TableHead>
                      <TableRow>
                        <TableCell>Status</TableCell>
                        <TableCell>Created</TableCell>
                        <TableCell>Expired</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {expiredSessions.map((session) => (
                        <TableRow key={session.id}>
                          <TableCell>
                            <Chip label="Expired" color="default" size="small" />
                          </TableCell>
                          <TableCell>{formatDate(session.created_at)}</TableCell>
                          <TableCell>{formatDate(session.expires_at)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              </Box>
            )}

            {/* Revoked Sessions */}
            {revokedSessions.length > 0 && (
              <Box>
                <Typography variant="h6" gutterBottom>
                  Revoked Sessions ({revokedSessions.length})
                </Typography>
                <TableContainer component={Paper} sx={{ mt: 2 }}>
                  <Table>
                    <TableHead>
                      <TableRow>
                        <TableCell>Status</TableCell>
                        <TableCell>Created</TableCell>
                        <TableCell>Revoked</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {revokedSessions.map((session) => (
                        <TableRow key={session.id}>
                          <TableCell>
                            <Chip label="Revoked" color="error" size="small" />
                          </TableCell>
                          <TableCell>{formatDate(session.created_at)}</TableCell>
                          <TableCell>
                            {session.revoked_at ? formatDate(session.revoked_at) : 'N/A'}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              </Box>
            )}
          </>
        )}

        {/* Revoke Session Confirmation Dialog */}
        <Dialog
          open={revokeDialogOpen}
          onClose={handleRevokeCancel}
          aria-labelledby="revoke-session-dialog-title"
          aria-describedby="revoke-session-dialog-description"
        >
          <DialogTitle id="revoke-session-dialog-title">Revoke Session?</DialogTitle>
          <DialogContent>
            <DialogContentText id="revoke-session-dialog-description">
              Are you sure you want to revoke this session? This will immediately log out the device
              using this session. This action cannot be undone.
            </DialogContentText>
            {sessionToRevoke && (
              <Box sx={{ mt: 2, p: 2, bgcolor: 'grey.100', borderRadius: 1 }}>
                <Typography variant="body2">
                  <strong>Created:</strong> {formatDate(sessionToRevoke.created_at)}
                </Typography>
                <Typography variant="body2">
                  <strong>Expires:</strong> {formatDate(sessionToRevoke.expires_at)}
                </Typography>
              </Box>
            )}
          </DialogContent>
          <DialogActions>
            <Button onClick={handleRevokeCancel} disabled={revokeMutation.isPending}>
              Cancel
            </Button>
            <Button
              onClick={handleRevokeConfirm}
              color="error"
              variant="contained"
              disabled={revokeMutation.isPending}
            >
              {revokeMutation.isPending ? 'Revoking...' : 'Revoke Session'}
            </Button>
          </DialogActions>
        </Dialog>
      </Box>
    </Container>
  )
}

