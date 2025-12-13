# Developer Experience Guide

**Last Updated**: 2025-12-13  
**Version**: 1.0.0

---

## Table of Contents

1. [Overview](#overview)
2. [Development Setup](#development-setup)
3. [Project Structure](#project-structure)
4. [Development Workflow](#development-workflow)
5. [Component Development](#component-development)
6. [Storybook Usage](#storybook-usage)
7. [Code Style Guide](#code-style-guide)
8. [Git Workflow](#git-workflow)
9. [Debugging](#debugging)
10. [Common Tasks](#common-tasks)

---

## Overview

This guide provides comprehensive instructions for developers working on the frontend application. It covers setup, workflows, best practices, and common development tasks.

**Developer Experience Goals**:
- Fast setup and onboarding
- Clear project structure
- Efficient development workflow
- Comprehensive tooling
- Good documentation

---

## Development Setup

### Prerequisites

- **Node.js**: 18.x or higher
- **npm**: 9.x or higher
- **Git**: Latest version
- **IDE**: VS Code (recommended) or any modern IDE

### Initial Setup

```bash
# Clone repository
git clone https://github.com/org/datahub-frontend.git
cd datahub-frontend

# Install dependencies
npm install

# Copy environment file
cp .env.example .env

# Start development server
npm run dev
```

### VS Code Setup

**Recommended Extensions**:
- ESLint
- Prettier
- TypeScript
- React snippets
- Tailwind CSS IntelliSense (if using Tailwind)

**Settings**: `.vscode/settings.json`

```json
{
  "editor.formatOnSave": true,
  "editor.defaultFormatter": "esbenp.prettier-vscode",
  "editor.codeActionsOnSave": {
    "source.fixAll.eslint": true
  },
  "typescript.tsdk": "node_modules/typescript/lib",
  "typescript.enablePromptUseWorkspaceTsdk": true
}
```

---

## Project Structure

### Directory Layout

```
src/
├── components/          # Reusable UI components
│   ├── common/         # Common components (Button, Input, etc.)
│   ├── layout/         # Layout components (Header, Sidebar, etc.)
│   └── features/       # Feature-specific components
├── features/           # Feature modules
│   ├── assets/        # Assets feature
│   ├── contracts/     # Contracts feature
│   └── marketplace/   # Marketplace feature
├── hooks/              # Custom React hooks
├── lib/                # Utility libraries
│   ├── api/           # API client, WebSocket
│   ├── analytics/     # Analytics integration
│   ├── i18n/          # Internationalization
│   └── utils/         # Utility functions
├── pages/              # Page components
├── routes/             # Route configuration
├── store/              # State management (Redux/Zustand)
├── styles/             # Global styles, themes
├── types/              # TypeScript type definitions
└── test-utils/        # Testing utilities
```

### File Naming Conventions

- **Components**: PascalCase (e.g., `AssetCard.tsx`)
- **Hooks**: camelCase with `use` prefix (e.g., `useAssets.ts`)
- **Utils**: camelCase (e.g., `formatDate.ts`)
- **Types**: PascalCase (e.g., `Asset.ts`)
- **Constants**: UPPER_SNAKE_CASE (e.g., `API_ENDPOINTS.ts`)

---

## Development Workflow

### Starting Development

```bash
# Start development server
npm run dev

# Start with backend
docker-compose up

# Run tests in watch mode
npm run test:watch
```

### Development Server

- **URL**: http://localhost:3000
- **Hot Reload**: Automatic on file changes
- **API Proxy**: `/api` proxied to backend
- **WebSocket Proxy**: `/ws` proxied to backend

### Common Commands

```bash
# Development
npm run dev              # Start dev server
npm run build           # Build for production
npm run preview         # Preview production build

# Testing
npm run test            # Run tests
npm run test:watch      # Run tests in watch mode
npm run test:coverage   # Run tests with coverage

# Linting
npm run lint            # Run ESLint
npm run lint:fix        # Fix ESLint errors
npm run format          # Format code with Prettier

# Storybook
npm run storybook       # Start Storybook
npm run build-storybook # Build Storybook
```

---

## Component Development

### Component Template

**Template**: `src/components/templates/ComponentTemplate.tsx`

```typescript
import React from 'react';
import { Box, Typography } from '@mui/material';

export interface ComponentTemplateProps {
  title: string;
  children?: React.ReactNode;
}

/**
 * ComponentTemplate - Brief description of component
 *
 * @param props - Component props
 * @returns Component JSX
 */
export function ComponentTemplate({
  title,
  children,
}: ComponentTemplateProps) {
  return (
    <Box>
      <Typography variant="h6">{title}</Typography>
      {children}
    </Box>
  );
}
```

### Component Checklist

- [ ] Component follows naming conventions
- [ ] Props are typed with TypeScript
- [ ] Component is documented
- [ ] Component is accessible (ARIA labels, keyboard navigation)
- [ ] Component is responsive
- [ ] Component has loading and error states
- [ ] Component is tested
- [ ] Component has Storybook story

---

## Storybook Usage

### Story Template

**Template**: `src/components/Component.stories.tsx`

```typescript
import type { Meta, StoryObj } from '@storybook/react';
import { ComponentTemplate } from './ComponentTemplate';

const meta: Meta<typeof ComponentTemplate> = {
  title: 'Components/ComponentTemplate',
  component: ComponentTemplate,
  tags: ['autodocs'],
  parameters: {
    layout: 'centered',
  },
};

export default meta;
type Story = StoryObj<typeof ComponentTemplate>;

export const Default: Story = {
  args: {
    title: 'Default Title',
    children: 'Default content',
  },
};

export const WithContent: Story = {
  args: {
    title: 'With Content',
    children: <div>Custom content here</div>,
  },
};
```

### Viewing Stories

```bash
# Start Storybook
npm run storybook

# Open in browser
# http://localhost:6006
```

### Storybook Best Practices

1. **Document Components**: Use JSDoc comments
2. **Multiple Variants**: Create stories for different states
3. **Controls**: Use controls for interactive props
4. **Accessibility**: Test accessibility in Storybook
5. **Visual Testing**: Use Chromatic for visual regression

---

## Code Style Guide

### TypeScript

**Guidelines**:
- Use TypeScript for all new code
- Avoid `any` type
- Use interfaces for object types
- Use type aliases for unions/intersections
- Prefer `const` over `let`

**Example**:
```typescript
// Good
interface User {
  id: string;
  name: string;
  email: string;
}

function getUser(id: string): Promise<User> {
  // ...
}

// Bad
function getUser(id: any): Promise<any> {
  // ...
}
```

### React

**Guidelines**:
- Use functional components
- Use hooks for state and side effects
- Extract custom hooks for reusable logic
- Use `React.memo` for expensive components
- Avoid inline functions in JSX when possible

**Example**:
```typescript
// Good
const handleClick = useCallback(() => {
  onClick(id);
}, [id, onClick]);

return <Button onClick={handleClick}>Click me</Button>;

// Bad
return <Button onClick={() => onClick(id)}>Click me</Button>;
```

### Naming Conventions

- **Components**: PascalCase (`AssetCard`)
- **Functions**: camelCase (`getAsset`)
- **Constants**: UPPER_SNAKE_CASE (`API_BASE_URL`)
- **Files**: Match export name
- **Props**: camelCase (`assetId`)

---

## Git Workflow

### Branch Strategy

- **main**: Production-ready code
- **develop**: Integration branch
- **feature/**: Feature branches
- **fix/**: Bug fix branches
- **hotfix/**: Critical production fixes

### Commit Messages

**Format**: `type(scope): subject`

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Code style changes
- `refactor`: Code refactoring
- `test`: Test changes
- `chore`: Build/tooling changes

**Examples**:
```
feat(assets): add asset creation form
fix(contracts): fix contract validation error
docs(readme): update setup instructions
```

### Pull Request Process

1. **Create Branch**: `git checkout -b feature/new-feature`
2. **Make Changes**: Implement feature
3. **Write Tests**: Add tests for new code
4. **Update Docs**: Update documentation if needed
5. **Create PR**: Create pull request with description
6. **Review**: Address review comments
7. **Merge**: Merge after approval

---

## Debugging

### React DevTools

- Install React DevTools browser extension
- Inspect component tree
- View component props and state
- Profile component performance

### Redux DevTools

- Install Redux DevTools browser extension
- View action history
- Time-travel debugging
- State inspection

### VS Code Debugging

**Configuration**: `.vscode/launch.json`

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "type": "chrome",
      "request": "launch",
      "name": "Launch Chrome",
      "url": "http://localhost:3000",
      "webRoot": "${workspaceFolder}/src"
    }
  ]
}
```

### Console Debugging

```typescript
// Use console.log for debugging (remove before commit)
console.log('Debug info:', data);

// Use debugger statement
debugger; // Pauses execution
```

---

## Common Tasks

### Adding a New Component

1. Create component file: `src/components/NewComponent.tsx`
2. Create component styles (if needed)
3. Create Storybook story: `NewComponent.stories.tsx`
4. Create tests: `NewComponent.test.tsx`
5. Export from index: `src/components/index.ts`

### Adding a New Page

1. Create page component: `src/pages/NewPage.tsx`
2. Add route: `src/routes/index.tsx`
3. Add navigation link (if needed)
4. Create tests: `NewPage.test.tsx`

### Adding a New API Endpoint

1. Add API function: `src/lib/api/endpoints.ts`
2. Create React Query hook: `src/hooks/api/useNewEndpoint.ts`
3. Add TypeScript types: `src/types/api.ts`
4. Use in component

### Adding a New Feature

1. Create feature directory: `src/features/new-feature/`
2. Add components, hooks, types
3. Add routes
4. Add navigation
5. Write tests
6. Update documentation

---

## Best Practices

1. **Follow Conventions**: Follow project conventions
2. **Write Tests**: Write tests for new code
3. **Document Code**: Document complex logic
4. **Review Code**: Review code before committing
5. **Keep Dependencies Updated**: Update dependencies regularly
6. **Optimize Performance**: Consider performance implications
7. **Accessibility**: Ensure accessibility
8. **Error Handling**: Handle errors gracefully
9. **Type Safety**: Use TypeScript effectively
10. **Clean Code**: Write clean, maintainable code

---

**Last Updated**: 2025-12-13  
**Version**: 1.0.0

