# State Management

This directory contains state management setup (Redux, Zustand, or other).

## Purpose

Centralized state management for:
- Global application state
- Shared state between features
- State persistence
- State synchronization

## Structure

The structure depends on the state management library chosen:

### Redux Structure
```
store/
├── index.ts           # Store configuration
├── slices/            # Redux slices
│   ├── auth.ts
│   └── user.ts
├── middleware/        # Redux middleware
└── hooks.ts           # Typed hooks
```

### Zustand Structure
```
store/
├── index.ts           # Store exports
├── stores/            # Zustand stores
│   ├── authStore.ts
│   └── userStore.ts
└── middleware/        # Zustand middleware
```

## Guidelines

- **Minimal state**: Only store truly global state
- **Type safety**: Fully typed state and actions
- **Immutability**: Don't mutate state directly
- **Testing**: Test state management logic
- **Documentation**: Document state structure and actions

## Usage

```tsx
// Redux example
import { useAppDispatch, useAppSelector } from '@/store'
const user = useAppSelector(state => state.user)
const dispatch = useAppDispatch()

// Zustand example
import { useAuthStore } from '@/store'
const user = useAuthStore(state => state.user)
```

## Best Practices

1. **Local state first**: Use component state when possible
2. **Feature state**: Keep feature-specific state in features
3. **Normalization**: Normalize complex state structures
4. **Selectors**: Use selectors for derived state
5. **Persistence**: Persist only necessary state

## Note

If not using a state management library, this directory can be omitted or used for context providers.

