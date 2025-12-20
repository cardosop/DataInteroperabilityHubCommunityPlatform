# Frontend Application

Modern React application built with Vite, TypeScript, and Material-UI.

## Prerequisites

- **Node.js**: 18.x or higher
- **npm**: 9.x or higher

## Installation

```bash
# Install dependencies
npm install
```

## Configuration

Copy the example environment file and configure it:

```bash
cp .env.example .env
```

Edit `.env` with your configuration values.

## Development

```bash
# Start development server
npm run dev
```

The application will be available at `http://localhost:3000`

## Build

```bash
# Build for production
npm run build

# Preview production build
npm run preview
```

## Dependencies

### Core Framework
- **React 18+**: UI library
- **TypeScript 5+**: Type safety
- **Vite**: Build tool and dev server

### Routing
- **React Router v6+**: Client-side routing

### UI Library
- **Material-UI (MUI) v5+**: Component library
- **Emotion**: CSS-in-JS styling

### State Management
- **React Query (TanStack Query)**: Server state management
- **Apollo Client**: GraphQL client

### Forms & Validation
- **React Hook Form**: Form management
- **Zod**: Schema validation

### HTTP Client
- **Axios**: HTTP requests

### Internationalization
- **react-i18next**: i18n support

### Monitoring
- **@sentry/react**: Error tracking
- **react-ga4**: Analytics

## Project Structure

```
frontend/
├── public/              # Static assets
├── src/
│   ├── lib/
│   │   └── config/     # Configuration files for all dependencies
│   ├── locales/         # i18n translation files
│   └── ...
├── .env.example        # Example environment variables
└── package.json
```

## Configuration Files

All dependency configurations are in `src/lib/config/`:

- `react-query.ts`: React Query client configuration
- `apollo.ts`: Apollo Client configuration
- `axios.ts`: Axios HTTP client configuration
- `i18n.ts`: Internationalization configuration
- `sentry.ts`: Error tracking configuration
- `analytics.ts`: Analytics configuration
- `mui.ts`: Material-UI theme configuration

## Environment Variables

See `.env.example` for all required environment variables.

## Type Checking

```bash
npm run type-check
```

## Linting

```bash
npm run lint
```
