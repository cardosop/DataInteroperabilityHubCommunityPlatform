# Real-Time Features UI Patterns

**Last Updated**: 2025-12-13  
**Version**: 1.0.0

---

## Table of Contents

1. [Overview](#overview)
2. [WebSocket Connection Status](#websocket-connection-status)
3. [Real-Time Notifications](#real-time-notifications)
4. [Live Job Status Updates](#live-job-status-updates)
5. [Real-Time Collaboration](#real-time-collaboration)
6. [Connection Management](#connection-management)
7. [Reconnection Handling](#reconnection-handling)
8. [Event Subscription Patterns](#event-subscription-patterns)

---

## Overview

This document describes UI patterns and components for real-time features in the Interoperable Data Hub platform. Real-time features are powered by WebSocket connections and provide live updates for jobs, workflows, assets, contracts, and system events.

**Real-Time Features**:
- Job status updates
- Workflow progress tracking
- Asset/contract change notifications
- System event notifications
- Live collaboration indicators
- Real-time data quality results

**Key Principles**:
- Always show connection status
- Graceful degradation when offline
- Automatic reconnection
- Clear visual feedback
- Non-intrusive notifications

---

## WebSocket Connection Status

### Connection Status Indicator Component

**Component**: `ConnectionStatusIndicator`

**Purpose**: Show WebSocket connection status to users

**Layout**:
```
┌─────────────────────────────────────────┐
│ Header                                  │
│  [Logo] [Nav] ... [User] [🟢 Connected]│
└─────────────────────────────────────────┘
```

**States**:
- **Connected**: Green dot, "Connected"
- **Connecting**: Yellow dot, "Connecting..."
- **Disconnected**: Red dot, "Disconnected"
- **Reconnecting**: Yellow dot, "Reconnecting... (attempt 2/5)"

**Component Specification**:
```typescript
interface ConnectionStatusIndicatorProps {
  status: 'connected' | 'connecting' | 'disconnected' | 'reconnecting';
  reconnectAttempt?: number;
  maxReconnectAttempts?: number;
}

export function ConnectionStatusIndicator({
  status,
  reconnectAttempt,
  maxReconnectAttempts = 5,
}: ConnectionStatusIndicatorProps) {
  const statusConfig = {
    connected: { color: 'success', icon: '🟢', text: 'Connected' },
    connecting: { color: 'warning', icon: '🟡', text: 'Connecting...' },
    disconnected: { color: 'error', icon: '🔴', text: 'Disconnected' },
    reconnecting: {
      color: 'warning',
      icon: '🟡',
      text: `Reconnecting... (${reconnectAttempt}/${maxReconnectAttempts})`,
    },
  };

  const config = statusConfig[status];

  return (
    <Tooltip title={config.text}>
      <Chip
        icon={<span>{config.icon}</span>}
        label={config.text}
        color={config.color}
        size="small"
        variant="outlined"
      />
    </Tooltip>
  );
}
```

**Placement**:
- Header: Always visible in top-right corner
- Footer: Alternative placement for mobile
- Toast: Show connection status changes as toast notifications

---

## Real-Time Notifications

### Notification Center Component

**Component**: `NotificationCenter`

**Purpose**: Display real-time notifications from WebSocket events

**Layout**:
```
┌─────────────────────────────────────────┐
│ Notifications                    [🔔 3] │
├─────────────────────────────────────────┤
│                                         │
│  ┌───────────────────────────────────┐ │
│  │ ✓ Contract validated              │ │
│  │   Customer Orders contract        │ │
│  │   2 minutes ago                   │ │
│  └───────────────────────────────────┘ │
│                                         │
│  ┌───────────────────────────────────┐ │
│  │ ⚠ DQ Run completed with warnings  │ │
│  │   Sales Data asset                 │ │
│  │   5 minutes ago                    │ │
│  └───────────────────────────────────┘ │
│                                         │
│  ┌───────────────────────────────────┐ │
│  │ ✗ Job failed                      │ │
│  │   Data ingestion job              │ │
│  │   10 minutes ago                   │ │
│  └───────────────────────────────────┘ │
│                                         │
│  [Mark all as read]  [View all]        │
│                                         │
└─────────────────────────────────────────┘
```

**Component Specification**:
```typescript
interface Notification {
  id: string;
  type: 'success' | 'warning' | 'error' | 'info';
  title: string;
  message: string;
  timestamp: Date;
  read: boolean;
  actionUrl?: string;
  metadata?: Record<string, any>;
}

interface NotificationCenterProps {
  notifications: Notification[];
  onMarkAsRead: (id: string) => void;
  onMarkAllAsRead: () => void;
  onNotificationClick: (notification: Notification) => void;
}

export function NotificationCenter({
  notifications,
  onMarkAsRead,
  onMarkAllAsRead,
  onNotificationClick,
}: NotificationCenterProps) {
  const unreadCount = notifications.filter(n => !n.read).length;

  return (
    <Popover>
      <IconButton>
        <Badge badgeContent={unreadCount} color="error">
          <NotificationsIcon />
        </Badge>
      </IconButton>
      <PopoverContent>
        <NotificationList
          notifications={notifications}
          onMarkAsRead={onMarkAsRead}
          onNotificationClick={onNotificationClick}
        />
        <Button onClick={onMarkAllAsRead}>Mark all as read</Button>
      </PopoverContent>
    </Popover>
  );
}
```

**Notification Types**:
- **Success**: Green, checkmark icon (e.g., "Contract validated")
- **Warning**: Yellow, warning icon (e.g., "DQ run completed with warnings")
- **Error**: Red, error icon (e.g., "Job failed")
- **Info**: Blue, info icon (e.g., "Asset updated")

**Interactions**:
- Click notification: Navigate to related resource
- Mark as read: Remove from unread count
- Mark all as read: Mark all notifications as read
- Auto-dismiss: Success notifications auto-dismiss after 5 seconds

**Real-Time Updates**:
- New notifications appear at top
- Unread count updates automatically
- Sound notification (optional, user preference)

---

## Live Job Status Updates

### Job Status Component

**Component**: `JobStatusIndicator`

**Purpose**: Show real-time job progress and status

**Layout**:
```
┌─────────────────────────────────────────┐
│ Job: Data Quality Run                   │
├─────────────────────────────────────────┤
│                                         │
│  Status: ⏳ Running                     │
│                                         │
│  Progress: ████████░░ 80%              │
│                                         │
│  Current Step: Validating schemas       │
│                                         │
│  Started: 2 minutes ago                  │
│  Estimated completion: 1 minute        │
│                                         │
│  [View Details] [Cancel]                │
│                                         │
└─────────────────────────────────────────┘
```

**Component Specification**:
```typescript
interface JobStatus {
  id: string;
  name: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  progress?: number; // 0-100
  currentStep?: string;
  startedAt: Date;
  completedAt?: Date;
  estimatedCompletion?: Date;
  error?: string;
}

interface JobStatusIndicatorProps {
  job: JobStatus;
  onViewDetails: () => void;
  onCancel?: () => void;
}

export function JobStatusIndicator({
  job,
  onViewDetails,
  onCancel,
}: JobStatusIndicatorProps) {
  const statusConfig = {
    pending: { color: 'default', icon: '⏸', label: 'Pending' },
    running: { color: 'primary', icon: '⏳', label: 'Running' },
    completed: { color: 'success', icon: '✓', label: 'Completed' },
    failed: { color: 'error', icon: '✗', label: 'Failed' },
    cancelled: { color: 'default', icon: '⊘', label: 'Cancelled' },
  };

  const config = statusConfig[job.status];

  return (
    <Card>
      <CardContent>
        <Box display="flex" alignItems="center" gap={2}>
          <Chip
            icon={<span>{config.icon}</span>}
            label={config.label}
            color={config.color}
          />
          <Typography variant="h6">{job.name}</Typography>
        </Box>

        {job.status === 'running' && job.progress !== undefined && (
          <>
            <LinearProgress
              variant="determinate"
              value={job.progress}
              sx={{ mt: 2, mb: 1 }}
            />
            <Typography variant="body2" color="text.secondary">
              {job.progress}% complete
            </Typography>
            {job.currentStep && (
              <Typography variant="body2" color="text.secondary">
                Current step: {job.currentStep}
              </Typography>
            )}
          </>
        )}

        {job.status === 'failed' && job.error && (
          <Alert severity="error" sx={{ mt: 2 }}>
            {job.error}
          </Alert>
        )}

        <Box display="flex" gap={1} mt={2}>
          <Button onClick={onViewDetails}>View Details</Button>
          {job.status === 'running' && onCancel && (
            <Button onClick={onCancel} color="error">
              Cancel
            </Button>
          )}
        </Box>
      </CardContent>
    </Card>
  );
}
```

**Real-Time Updates**:
- Progress bar updates automatically
- Current step updates in real-time
- Status changes trigger visual updates
- Completion triggers success notification

---

## Real-Time Collaboration

### Active Users Indicator

**Component**: `ActiveUsersIndicator`

**Purpose**: Show who is currently viewing/editing a resource

**Layout**:
```
┌─────────────────────────────────────────┐
│ Contract Editor                         │
│                                         │
│  👤 Active Users (2)                   │
│  • John Doe (editing)                  │
│  • Jane Smith (viewing)                │
│                                         │
│  [Content]                              │
│                                         │
└─────────────────────────────────────────┘
```

**Component Specification**:
```typescript
interface ActiveUser {
  id: string;
  name: string;
  email: string;
  status: 'viewing' | 'editing';
  cursor?: { line: number; column: number };
  color: string; // Color for user's cursor/selection
}

interface ActiveUsersIndicatorProps {
  users: ActiveUser[];
  currentUserId: string;
}

export function ActiveUsersIndicator({
  users,
  currentUserId,
}: ActiveUsersIndicatorProps) {
  const otherUsers = users.filter(u => u.id !== currentUserId);

  return (
    <Box>
      <Typography variant="caption">
        👤 Active Users ({users.length})
      </Typography>
      <List dense>
        {otherUsers.map(user => (
          <ListItem key={user.id}>
            <ListItemAvatar>
              <Avatar sx={{ bgcolor: user.color }}>
                {user.name[0]}
              </Avatar>
            </ListItemAvatar>
            <ListItemText
              primary={user.name}
              secondary={user.status}
            />
          </ListItem>
        ))}
      </List>
    </Box>
  );
}
```

### Collaborative Cursors

**Component**: `CollaborativeCursor`

**Purpose**: Show other users' cursors in real-time editors

**Visual**:
- Colored cursor line with user's name
- User's selection highlighted in their color
- Smooth cursor movement animations

---

## Connection Management

### Connection Manager Hook

**Hook**: `useWebSocketConnection`

**Purpose**: Manage WebSocket connection lifecycle

```typescript
export function useWebSocketConnection() {
  const [status, setStatus] = useState<'connected' | 'disconnected' | 'reconnecting'>('disconnected');
  const [reconnectAttempt, setReconnectAttempt] = useState(0);
  const wsRef = useRef<WebSocketClient | null>(null);

  useEffect(() => {
    const connect = async () => {
      try {
        setStatus('connecting');
        await wsClient.connect();
        setStatus('connected');
        setReconnectAttempt(0);
      } catch (error) {
        setStatus('disconnected');
      }
    };

    connect();

    // Listen to connection events
    const handleConnect = () => setStatus('connected');
    const handleDisconnect = () => setStatus('disconnected');
    const handleReconnect = (attempt: number) => {
      setStatus('reconnecting');
      setReconnectAttempt(attempt);
    };

    wsClient.on('connect', handleConnect);
    wsClient.on('disconnect', handleDisconnect);
    wsClient.on('reconnect', handleReconnect);

    return () => {
      wsClient.off('connect', handleConnect);
      wsClient.off('disconnect', handleDisconnect);
      wsClient.off('reconnect', handleReconnect);
      wsClient.disconnect();
    };
  }, []);

  return { status, reconnectAttempt };
}
```

---

## Reconnection Handling

### Reconnection UI Patterns

**Pattern 1: Automatic Reconnection (Silent)**
- Show connection status indicator
- Automatically reconnect in background
- No user intervention required
- Show toast on successful reconnection

**Pattern 2: Manual Reconnection**
- Show reconnection dialog
- Allow user to manually retry
- Show connection status

**Reconnection Dialog**:
```
┌─────────────────────────────────────────┐
│ Connection Lost                         │
├─────────────────────────────────────────┤
│                                         │
│  Unable to connect to server.           │
│                                         │
│  Attempting to reconnect...             │
│  (Attempt 2 of 5)                       │
│                                         │
│  [Retry Now]  [Work Offline]           │
│                                         │
└─────────────────────────────────────────┘
```

**Reconnection Strategy**:
- Exponential backoff: 1s, 2s, 4s, 8s, 16s
- Max attempts: 5
- Show attempt count to user
- Allow manual retry
- Option to work offline

---

## Event Subscription Patterns

### Event Subscription Hook

**Hook**: `useEventSubscription`

**Purpose**: Subscribe to specific event types

```typescript
export function useEventSubscription(
  eventTypes: WebSocketEventType[],
  onEvent: (event: WebSocketEvent) => void
) {
  const queryClient = useQueryClient();

  useEffect(() => {
    // Subscribe to events
    wsClient.subscribe(eventTypes);

    // Set up listeners
    const unsubscribes = eventTypes.map(eventType =>
      wsClient.on(eventType, (event) => {
        // Invalidate relevant queries
        if (eventType.startsWith('asset.')) {
          queryClient.invalidateQueries({ queryKey: ['assets'] });
        } else if (eventType.startsWith('contract.')) {
          queryClient.invalidateQueries({ queryKey: ['contracts'] });
        } else if (eventType.startsWith('job.')) {
          queryClient.invalidateQueries({ queryKey: ['jobs'] });
        }

        // Call custom handler
        onEvent(event);
      })
    );

    return () => {
      unsubscribes.forEach(unsubscribe => unsubscribe());
      wsClient.unsubscribe(eventTypes);
    };
  }, [eventTypes, onEvent, queryClient]);
}
```

### Usage Examples

**Example 1: Job Status Updates**
```typescript
function JobDetailPage({ jobId }: { jobId: string }) {
  const { data: job } = useJob(jobId);

  useEventSubscription(
    ['job.started', 'job.completed', 'job.failed', 'job.progress'],
    (event) => {
      if (event.data.job_id === jobId) {
        // Update job status
        queryClient.setQueryData(['jobs', jobId], (old: Job) => ({
          ...old,
          status: event.data.status,
          progress: event.data.progress,
        }));
      }
    }
  );

  return <JobStatusIndicator job={job} />;
}
```

**Example 2: Contract Validation Updates**
```typescript
function ContractEditor({ contractId }: { contractId: string }) {
  useEventSubscription(
    ['contract.validated'],
    (event) => {
      if (event.data.contract_id === contractId) {
        // Show validation result
        showNotification({
          type: 'success',
          title: 'Contract validated',
          message: 'Validation completed successfully',
        });
      }
    }
  );

  return <ContractEditorContent />;
}
```

---

## Offline Mode Handling

### Offline Indicator

**Component**: `OfflineIndicator`

**Purpose**: Show when application is offline

**Layout**:
```
┌─────────────────────────────────────────┐
│ ⚠️ You're offline. Some features may    │
│    not be available.                    │
└─────────────────────────────────────────┘
```

**Behavior**:
- Detect offline status (navigator.onLine)
- Show banner at top of page
- Disable real-time features
- Queue actions for when online
- Show sync status when reconnected

---

## Performance Considerations

1. **Event Throttling**: Throttle high-frequency events (e.g., cursor movements)
2. **Selective Subscriptions**: Only subscribe to needed events
3. **Connection Pooling**: Reuse WebSocket connections
4. **Message Batching**: Batch multiple events when possible
5. **Memory Management**: Clean up event listeners on unmount

---

## Accessibility

1. **Status Announcements**: Announce connection status changes to screen readers
2. **Notification Alerts**: Notifications announced to screen readers
3. **Keyboard Navigation**: All real-time UI elements keyboard accessible
4. **Focus Management**: Manage focus during real-time updates

---

**Last Updated**: 2025-12-13  
**Version**: 1.0.0

