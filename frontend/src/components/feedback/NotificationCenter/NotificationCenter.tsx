/**
 * NotificationCenter Component
 *
 * Notification center for displaying and managing a list of notifications.
 * Supports marking as read, filtering, and grouping.
 */

import React, { useState, useMemo } from 'react'
import {
  Drawer,
  Box,
  Typography,
  IconButton,
  List,
  ListItem,
  ListItemText,
  ListItemButton,
  Chip,
  Button,
  Divider,
  Badge,
  Tooltip,
} from '@mui/material'
import {
  Notifications as NotificationsIcon,
  Close as CloseIcon,
  CheckCircle as CheckCircleIcon,
  MarkEmailRead as MarkReadIcon,
  Delete as DeleteIcon,
} from '@mui/icons-material'
import { spacing, colors } from '@/styles/tokens'

export interface Notification {
  id: string
  title: string
  message: string
  severity?: 'success' | 'warning' | 'error' | 'info'
  timestamp: Date
  read: boolean
  action?: {
    label: string
    onClick: () => void
  }
  actions?: Array<{
    label: string
    onClick: () => void
    variant?: 'primary' | 'secondary' | 'default'
  }>
  onDismiss?: () => void
}

export interface NotificationCenterProps {
  /**
   * List of notifications
   */
  notifications: Notification[]
  /**
   * Callback when notification is marked as read
   */
  onMarkAsRead?: (id: string) => void
  /**
   * Callback when notification is dismissed
   */
  onDismiss?: (id: string) => void
  /**
   * Callback when all notifications are marked as read
   */
  onMarkAllAsRead?: () => void
  /**
   * Callback when all notifications are cleared
   */
  onClearAll?: () => void
  /**
   * Whether the drawer is open
   */
  open: boolean
  /**
   * Callback when drawer is closed
   */
  onClose: () => void
  /**
   * Anchor position
   * @default 'right'
   */
  anchor?: 'left' | 'right' | 'top' | 'bottom'
  /**
   * Width of the drawer
   * @default 400
   */
  width?: number
}

/**
 * NotificationCenter component
 */
export const NotificationCenter: React.FC<NotificationCenterProps> = ({
  notifications,
  onMarkAsRead,
  onDismiss,
  onMarkAllAsRead,
  onClearAll,
  open,
  onClose,
  anchor = 'right',
  width = 400,
}) => {
  const [filter, setFilter] = useState<'all' | 'unread'>('all')

  const unreadCount = useMemo(
    () => notifications.filter((n) => !n.read).length,
    [notifications]
  )

  const filteredNotifications = useMemo(() => {
    if (filter === 'unread') {
      return notifications.filter((n) => !n.read)
    }
    return notifications
  }, [notifications, filter])

  const handleMarkAsRead = (id: string) => {
    onMarkAsRead?.(id)
  }

  const handleDismiss = (id: string) => {
    onDismiss?.(id)
  }

  const formatTimestamp = (date: Date) => {
    const now = new Date()
    const diff = now.getTime() - date.getTime()
    const minutes = Math.floor(diff / 60000)
    const hours = Math.floor(diff / 3600000)
    const days = Math.floor(diff / 86400000)

    if (minutes < 1) return 'Just now'
    if (minutes < 60) return `${minutes}m ago`
    if (hours < 24) return `${hours}h ago`
    if (days < 7) return `${days}d ago`
    return date.toLocaleDateString()
  }

  const getSeverityColor = (severity?: Notification['severity']) => {
    switch (severity) {
      case 'success':
        return colors.success[500]
      case 'warning':
        return colors.warning[500]
      case 'error':
        return colors.error[500]
      case 'info':
      default:
        return colors.info[500]
    }
  }

  return (
    <Drawer
      anchor={anchor}
      open={open}
      onClose={onClose}
      PaperProps={{
        sx: {
          width: width,
          maxWidth: '90vw',
        },
      }}
    >
      <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
        {/* Header */}
        <Box
          sx={{
            padding: spacing[3],
            borderBottom: 1,
            borderColor: 'divider',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: spacing[2] }}>
            <Badge badgeContent={unreadCount} color="error">
              <NotificationsIcon />
            </Badge>
            <Typography variant="h6">Notifications</Typography>
          </Box>
          <IconButton onClick={onClose} size="small">
            <CloseIcon />
          </IconButton>
        </Box>

        {/* Filters and Actions */}
        <Box
          sx={{
            padding: spacing[2],
            borderBottom: 1,
            borderColor: 'divider',
            display: 'flex',
            gap: spacing[2],
            alignItems: 'center',
          }}
        >
          <Chip
            label="All"
            size="small"
            onClick={() => setFilter('all')}
            color={filter === 'all' ? 'primary' : 'default'}
            variant={filter === 'all' ? 'filled' : 'outlined'}
          />
          <Chip
            label={`Unread (${unreadCount})`}
            size="small"
            onClick={() => setFilter('unread')}
            color={filter === 'unread' ? 'primary' : 'default'}
            variant={filter === 'unread' ? 'filled' : 'outlined'}
          />
          <Box sx={{ flex: 1 }} />
          {onMarkAllAsRead && unreadCount > 0 && (
            <Tooltip title="Mark all as read">
              <IconButton size="small" onClick={onMarkAllAsRead}>
                <MarkReadIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          )}
          {onClearAll && notifications.length > 0 && (
            <Tooltip title="Clear all">
              <IconButton size="small" onClick={onClearAll}>
                <DeleteIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          )}
        </Box>

        {/* Notifications List */}
        <Box sx={{ flex: 1, overflow: 'auto' }}>
          {filteredNotifications.length === 0 ? (
            <Box
              sx={{
                padding: spacing[4],
                textAlign: 'center',
                color: 'text.secondary',
              }}
            >
              <Typography variant="body2">
                {filter === 'unread' ? 'No unread notifications' : 'No notifications'}
              </Typography>
            </Box>
          ) : (
            <List>
              {filteredNotifications.map((notification, index) => (
                <React.Fragment key={notification.id}>
                  <ListItem
                    disablePadding
                    sx={{
                      backgroundColor: notification.read
                        ? 'transparent'
                        : 'action.hover',
                      borderLeft: `3px solid ${getSeverityColor(notification.severity)}`,
                    }}
                  >
                    <ListItemButton
                      onClick={() => {
                        if (!notification.read) {
                          handleMarkAsRead(notification.id)
                        }
                      }}
                    >
                      <ListItemText
                        primary={
                          <Box
                            sx={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: spacing[1],
                            }}
                          >
                            <Typography
                              variant="subtitle2"
                              sx={{
                                fontWeight: notification.read ? 400 : 600,
                              }}
                            >
                              {notification.title}
                            </Typography>
                            {!notification.read && (
                              <Box
                                sx={{
                                  width: 8,
                                  height: 8,
                                  borderRadius: '50%',
                                  backgroundColor: 'primary.main',
                                }}
                              />
                            )}
                          </Box>
                        }
                        secondary={
                          <Box>
                            <Typography variant="body2" color="text.secondary">
                              {notification.message}
                            </Typography>
                            <Box
                              sx={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: spacing[2],
                                marginTop: spacing[1],
                              }}
                            >
                              <Typography variant="caption" color="text.secondary">
                                {formatTimestamp(notification.timestamp)}
                              </Typography>
                              {notification.action && (
                                <Button
                                  size="small"
                                  variant="text"
                                  onClick={(e) => {
                                    e.stopPropagation()
                                    notification.action?.onClick()
                                  }}
                                >
                                  {notification.action.label}
                                </Button>
                              )}
                              {/* Support for multiple actions - show first action in secondary area */}
                              {notification.actions && notification.actions.length > 1 && (
                                <Box sx={{ display: 'flex', gap: 1, mt: 1 }}>
                                  {notification.actions.slice(1).map((action, idx) => (
                                    <Button
                                      key={idx}
                                      size="small"
                                      variant={action.variant === 'primary' ? 'contained' : 'outlined'}
                                      onClick={(e) => {
                                        e.stopPropagation()
                                        action.onClick()
                                      }}
                                    >
                                      {action.label}
                                    </Button>
                                  ))}
                                </Box>
                              )}
                            </Box>
                          </Box>
                        }
                      />
                      <Box sx={{ display: 'flex', gap: spacing[1] }}>
                        {!notification.read && (
                          <Tooltip title="Mark as read">
                            <IconButton
                              size="small"
                              onClick={(e) => {
                                e.stopPropagation()
                                handleMarkAsRead(notification.id)
                              }}
                            >
                              <CheckCircleIcon fontSize="small" />
                            </IconButton>
                          </Tooltip>
                        )}
                        {onDismiss && (
                          <Tooltip title="Dismiss">
                            <IconButton
                              size="small"
                              onClick={(e) => {
                                e.stopPropagation()
                                handleDismiss(notification.id)
                              }}
                            >
                              <CloseIcon fontSize="small" />
                            </IconButton>
                          </Tooltip>
                        )}
                      </Box>
                    </ListItemButton>
                  </ListItem>
                  {index < filteredNotifications.length - 1 && <Divider />}
                </React.Fragment>
              ))}
            </List>
          )}
        </Box>
      </Box>
    </Drawer>
  )
}

