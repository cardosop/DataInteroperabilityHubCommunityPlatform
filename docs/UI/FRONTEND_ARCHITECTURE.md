# Frontend Architecture

**Last Updated**: 2025-01-15  
**Version**: 1.0.0

---

## Table of Contents

1. [Overview](#overview)
2. [Technology Stack](#technology-stack)
3. [Project Structure](#project-structure)
4. [Architecture Patterns](#architecture-patterns)
5. [State Management](#state-management)
6. [API Integration](#api-integration)
7. [Routing](#routing)
8. [Authentication](#authentication)
9. [Error Handling](#error-handling)
10. [Performance Optimization](#performance-optimization)
11. [Testing Strategy](#testing-strategy)
12. [Build and Deployment](#build-and-deployment)

---

## Overview

This document describes the frontend architecture for the Interoperable Data Hub platform. The frontend is built as a modern single-page application (SPA) with a focus on performance, maintainability, and user experience.

**Architecture Principles**:
- **Component-Based**: Reusable, composable components
- **Type-Safe**: TypeScript for type safety
- **Performance-First**: Optimized for fast load times and smooth interactions
- **Accessible**: WCAG 2.1 AA compliant
- **Maintainable**: Clear structure and documentation

---

## Technology Stack

### Core Framework

**React 18+**
- Modern React with hooks
- Concurrent features (Suspense, Transitions)
- Server Components (future)

**TypeScript 5+**
- Type safety
- Better IDE support
- Refactoring safety

### UI Library

**Material-UI (MUI) v5+** (or similar)
- Comprehensive component library
- Theming support
- Accessibility built-in
- Customizable design system

**Alternative Options**:
- Chakra UI
- Ant Design
- Custom component library

### State Management

**Redux Toolkit** (or Zustand)
- Centralized state management
- DevTools support
- Middleware for async actions
- RTK Query for API state

**Alternative**: Zustand for simpler state needs

### Routing

**React Router v6+**
- Declarative routing
- Code splitting
- Protected routes
- Nested routes

### API Client

**React Query (TanStack Query)**
- Server state management
- Caching and synchronization
- Optimistic updates
- Background refetching

**Axios**
- HTTP client
- Request/response interceptors
- Error handling

### Styling

**Emotion** (CSS-in-JS)
- Component-scoped styles
- Theme integration
- Dynamic styling

**Alternative**: Tailwind CSS

### Build Tools

**Vite**
- Fast development server
- Optimized production builds
- HMR (Hot Module Replacement)

**Alternative**: Create React App, Next.js

### Testing

**Jest**
- Unit testing
- Snapshot testing
- Mocking

**React Testing Library**
- Component testing
- User-centric testing
- Accessibility testing

**Cypress** (or Playwright)
- E2E testing
- Integration testing

### Development Tools

**ESLint**
- Code linting
- TypeScript support

**Prettier**
- Code formatting

**Storybook**
- Component documentation
- Component testing
- Design system showcase

---

## Project Structure

```
frontend/
├── public/                 # Static assets
│   ├── favicon.ico
│   └── assets/
├── src/
│   ├── components/         # Reusable components
│   │   ├── common/        # Common components (Button, Input, etc.)
│   │   ├── layout/        # Layout components (Header, Sidebar, etc.)
│   │   └── features/      # Feature-specific components
│   ├── pages/             # Page components
│   │   ├── assets/
│   │   ├── contracts/
│   │   ├── marketplace/
│   │   └── admin/
│   ├── features/           # Feature modules
│   │   ├── assets/
│   │   │   ├── components/
│   │   │   ├── hooks/
│   │   │   ├── services/
│   │   │   └── types.ts
│   │   ├── contracts/
│   │   └── marketplace/
│   ├── hooks/              # Custom React hooks
│   ├── services/           # API services
│   │   ├── api/
│   │   ├── auth/
│   │   └── storage/
│   ├── store/              # Redux store
│   │   ├── slices/
│   │   ├── middleware/
│   │   └── store.ts
│   ├── utils/              # Utility functions
│   ├── types/              # TypeScript types
│   ├── theme/              # Theme configuration
│   │   ├── colors.ts
│   │   ├── typography.ts
│   │   └── theme.ts
│   ├── App.tsx             # Root component
│   ├── index.tsx           # Entry point
│   └── routes.tsx          # Route configuration
├── .env                    # Environment variables
├── .eslintrc.js           # ESLint config
├── .prettierrc            # Prettier config
├── package.json
├── tsconfig.json          # TypeScript config
├── vite.config.ts         # Vite config
└── README.md
```

---

## Architecture Patterns

### Feature-Based Structure

Organize code by feature rather than by type:

```
features/
  assets/
    components/     # Asset-specific components
    hooks/          # Asset-specific hooks
    services/       # Asset API services
    types.ts        # Asset types
    index.ts        # Public exports
```

**Benefits**:
- Co-located related code
- Easier to find and maintain
- Clear feature boundaries
- Better code splitting

---

### Component Composition

Build complex components from simple ones:

```tsx
// Simple components
<Button />
<Icon />
<Text />

// Composed components
<IconButton icon={<Icon />} label="Save" />
<Card>
  <CardHeader title="Asset" />
  <CardContent>
    <Text>Content</Text>
  </CardContent>
</Card>
```

---

### Container/Presenter Pattern

Separate logic from presentation:

```tsx
// Container (logic)
const AssetListContainer = () => {
  const { data, isLoading } = useAssets();
  const handleDelete = useDeleteAsset();
  
  return <AssetList data={data} loading={isLoading} onDelete={handleDelete} />;
};

// Presenter (UI)
const AssetList = ({ data, loading, onDelete }) => {
  // Pure presentation logic
};
```

---

## State Management

### Server State (React Query)

Use React Query for server state:

```tsx
// Query
const { data, isLoading } = useQuery({
  queryKey: ['assets'],
  queryFn: () => api.getAssets()
});

// Mutation
const mutation = useMutation({
  mutationFn: (asset) => api.createAsset(asset),
  onSuccess: () => {
    queryClient.invalidateQueries(['assets']);
  }
});
```

### Client State (Redux/Zustand)

Use Redux for global client state:

```tsx
// Slice
const authSlice = createSlice({
  name: 'auth',
  initialState: { user: null, token: null },
  reducers: {
    setUser: (state, action) => {
      state.user = action.payload;
    }
  }
});

// Usage
const user = useSelector(state => state.auth.user);
dispatch(setUser(userData));
```

### Local State (useState)

Use useState for component-local state:

```tsx
const [isOpen, setIsOpen] = useState(false);
```

---

## API Integration

### API Client Setup

```tsx
// api/client.ts
import axios from 'axios';

const apiClient = axios.create({
  baseURL: process.env.REACT_APP_API_URL,
  headers: {
    'Content-Type': 'application/json'
  }
});

// Request interceptor (add auth token)
apiClient.interceptors.request.use((config) => {
  const token = getAuthToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor (handle errors)
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Handle unauthorized
      logout();
    }
    return Promise.reject(error);
  }
);
```

### API Services

```tsx
// services/assets.ts
export const assetService = {
  getAssets: () => apiClient.get('/api/v1/assets'),
  getAsset: (id: string) => apiClient.get(`/api/v1/assets/${id}`),
  createAsset: (data: Asset) => apiClient.post('/api/v1/assets', data),
  updateAsset: (id: string, data: Asset) => 
    apiClient.put(`/api/v1/assets/${id}`, data),
  deleteAsset: (id: string) => apiClient.delete(`/api/v1/assets/${id}`)
};
```

### React Query Integration

```tsx
// hooks/useAssets.ts
export const useAssets = () => {
  return useQuery({
    queryKey: ['assets'],
    queryFn: () => assetService.getAssets()
  });
};

export const useCreateAsset = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: assetService.createAsset,
    onSuccess: () => {
      queryClient.invalidateQueries(['assets']);
    }
  });
};
```

---

## Routing

### Route Configuration

```tsx
// routes.tsx
import { Routes, Route } from 'react-router-dom';

export const AppRoutes = () => {
  return (
    <Routes>
      <Route path="/" element={<Dashboard />} />
      <Route path="/assets" element={<AssetList />} />
      <Route path="/assets/:id" element={<AssetDetail />} />
      <Route path="/assets/new" element={<AssetCreate />} />
      <Route path="/marketplace" element={<Marketplace />} />
      <Route path="/admin/*" element={<AdminRoutes />} />
    </Routes>
  );
};
```

### Protected Routes

```tsx
// components/ProtectedRoute.tsx
const ProtectedRoute = ({ children, requiredRole }) => {
  const { user, isAuthenticated } = useAuth();
  
  if (!isAuthenticated) {
    return <Navigate to="/login" />;
  }
  
  if (requiredRole && !hasRole(user, requiredRole)) {
    return <Navigate to="/unauthorized" />;
  }
  
  return children;
};

// Usage
<Route
  path="/admin"
  element={
    <ProtectedRoute requiredRole="TENANT_ADMIN">
      <AdminPanel />
    </ProtectedRoute>
  }
/>
```

---

## Authentication

### Auth Context

```tsx
// contexts/AuthContext.tsx
const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(localStorage.getItem('token'));
  
  const login = async (email, password) => {
    const response = await authService.login(email, password);
    setToken(response.token);
    setUser(response.user);
    localStorage.setItem('token', response.token);
  };
  
  const logout = () => {
    setToken(null);
    setUser(null);
    localStorage.removeItem('token');
  };
  
  return (
    <AuthContext.Provider value={{ user, token, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
};
```

### Auth Hook

```tsx
// hooks/useAuth.ts
export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};
```

---

## Error Handling

### Error Boundary

```tsx
// components/ErrorBoundary.tsx
class ErrorBoundary extends React.Component {
  state = { hasError: false, error: null };
  
  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }
  
  componentDidCatch(error, errorInfo) {
    // Log to error reporting service
    console.error('Error caught:', error, errorInfo);
  }
  
  render() {
    if (this.state.hasError) {
      return <ErrorFallback error={this.state.error} />;
    }
    return this.props.children;
  }
}
```

### API Error Handling

```tsx
// utils/errorHandler.ts
export const handleApiError = (error: AxiosError) => {
  if (error.response) {
    // Server responded with error
    const { status, data } = error.response;
    
    switch (status) {
      case 400:
        return 'Invalid request. Please check your input.';
      case 401:
        return 'Unauthorized. Please log in.';
      case 403:
        return 'You do not have permission to perform this action.';
      case 404:
        return 'Resource not found.';
      case 500:
        return 'Server error. Please try again later.';
      default:
        return data?.message || 'An error occurred.';
    }
  }
  
  return 'Network error. Please check your connection.';
};
```

---

## Performance Optimization

### Code Splitting

```tsx
// Lazy load routes
const AssetDetail = lazy(() => import('./pages/AssetDetail'));
const AdminPanel = lazy(() => import('./pages/AdminPanel'));

// Usage with Suspense
<Suspense fallback={<LoadingSpinner />}>
  <AssetDetail />
</Suspense>
```

### Memoization

```tsx
// Memoize expensive components
const ExpensiveComponent = memo(({ data }) => {
  // Expensive rendering
});

// Memoize callbacks
const handleClick = useCallback(() => {
  // Handler logic
}, [dependencies]);

// Memoize computed values
const expensiveValue = useMemo(() => {
  return computeExpensiveValue(data);
}, [data]);
```

### Virtual Scrolling

For long lists:

```tsx
import { FixedSizeList } from 'react-window';

<FixedSizeList
  height={600}
  itemCount={items.length}
  itemSize={50}
>
  {({ index, style }) => (
    <div style={style}>
      {items[index]}
    </div>
  )}
</FixedSizeList>
```

---

## Testing Strategy

### Unit Tests

```tsx
// components/Button.test.tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { Button } from './Button';

test('renders button with text', () => {
  render(<Button>Click me</Button>);
  expect(screen.getByText('Click me')).toBeInTheDocument();
});

test('calls onClick when clicked', () => {
  const handleClick = jest.fn();
  render(<Button onClick={handleClick}>Click me</Button>);
  fireEvent.click(screen.getByText('Click me'));
  expect(handleClick).toHaveBeenCalledTimes(1);
});
```

### Integration Tests

```tsx
// features/assets/AssetList.test.tsx
test('loads and displays assets', async () => {
  render(<AssetList />);
  
  // Wait for data to load
  await waitFor(() => {
    expect(screen.getByText('Asset 1')).toBeInTheDocument();
  });
});
```

### E2E Tests

```tsx
// cypress/integration/assets.spec.ts
describe('Asset Management', () => {
  it('creates a new asset', () => {
    cy.visit('/assets');
    cy.get('[data-testid="new-asset-button"]').click();
    cy.get('[data-testid="asset-name-input"]').type('Test Asset');
    cy.get('[data-testid="submit-button"]').click();
    cy.contains('Asset created successfully').should('be.visible');
  });
});
```

---

## Build and Deployment

### Environment Variables

```bash
# .env.development
REACT_APP_API_URL=http://localhost:8000/api/v1
REACT_APP_ENV=development

# .env.production
REACT_APP_API_URL=https://api.hub.example.com/api/v1
REACT_APP_ENV=production
```

### Build Process

```bash
# Development
npm run dev

# Production build
npm run build

# Preview production build
npm run preview
```

### Deployment

- **Static Hosting**: Deploy to CDN (CloudFront, Cloudflare)
- **Container**: Docker container with Nginx
- **CI/CD**: Automated builds and deployments

---

**Last Updated**: 2025-01-15  
**Version**: 1.0.0

