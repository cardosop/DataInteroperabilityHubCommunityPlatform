# Bundle Optimization Guide

**Last Updated**: 2025-01-27
**Version**: 1.0.0

---

## Overview

This document describes bundle optimization strategies, import best practices, and tools for maintaining optimal bundle sizes in the Data Interoperability Hub frontend application.

---

## Table of Contents

1. [Tree Shaking](#tree-shaking)
2. [Import Optimization](#import-optimization)
3. [Bundle Analysis](#bundle-analysis)
4. [Bundle Size Budgets](#bundle-size-budgets)
5. [Best Practices](#best-practices)
6. [Troubleshooting](#troubleshooting)

---

## Tree Shaking

### Configuration

Tree shaking is automatically enabled in Vite/Rollup. The following configurations optimize tree shaking:

1. **Package.json `sideEffects` field**: Explicitly declares which files have side effects
2. **ESM modules**: All code uses ES modules for optimal tree shaking
3. **Rollup tree shaking**: Configured in `vite.config.ts` with aggressive settings

### How It Works

- **Dead code elimination**: Unused exports are removed from the final bundle
- **Side effect detection**: Only files with side effects are included
- **Property access optimization**: Property reads are assumed to have no side effects

### Verifying Tree Shaking

```bash
# Build and analyze bundle
npm run build:analyze

# Check for unused code in bundle
# Open dist/stats.html and look for:
# - Unused exports
# - Duplicate code
# - Large vendor chunks
```

---

## Import Optimization

### Best Practices

#### ✅ DO: Use Direct Imports

Prefer importing specific modules instead of barrel exports when possible:

```typescript
// ✅ Good - Direct import (better tree shaking)
import { Button } from '@mui/material/Button'
import { TextField } from '@mui/material/TextField'

// ❌ Avoid - Barrel import (may include unused code)
import { Button, TextField } from '@mui/material'
```

#### ✅ DO: Use Named Exports

Prefer named exports over default exports for better tree shaking:

```typescript
// ✅ Good - Named export
export const MyComponent = () => { ... }

// ⚠️ Acceptable - Default export (still works, but less optimal)
export default MyComponent
```

#### ✅ DO: Import Only What You Need

```typescript
// ✅ Good - Import only used functions
import { debounce, throttle } from 'lodash-es'

// ❌ Avoid - Import entire library
import _ from 'lodash-es'
```

#### ✅ DO: Use Path Aliases

Use the `@/` alias for cleaner imports:

```typescript
// ✅ Good - Using alias
import { Button } from '@/components/forms'
import { useAuth } from '@/hooks'

// ❌ Avoid - Relative paths
import { Button } from '../../../components/forms'
```

#### ❌ AVOID: Barrel Exports for Large Libraries

When importing from large libraries, use direct paths:

```typescript
// ✅ Good - Direct import from MUI
import Button from '@mui/material/Button'
import TextField from '@mui/material/TextField'

// ❌ Avoid - Barrel import from MUI (includes entire library)
import { Button, TextField } from '@mui/material'
```

#### ❌ AVOID: Dynamic Imports in Hot Paths

Use dynamic imports for code splitting, but avoid in frequently executed code:

```typescript
// ✅ Good - Lazy load heavy components
const MonacoEditor = lazy(() => import('@/components/common/LazyMonacoEditor'))

// ❌ Avoid - Dynamic import in render loop
function Component() {
  const [Editor, setEditor] = useState(null)
  useEffect(() => {
    import('@/components/common/LazyMonacoEditor').then(setEditor) // ❌
  }, [])
}
```

### Barrel Export Guidelines

Barrel exports (`index.ts` files) are convenient but can prevent tree shaking. Follow these guidelines:

1. **Small modules**: Barrel exports are fine for small, cohesive modules
2. **Large modules**: Use direct imports for large libraries
3. **Application code**: Barrel exports are acceptable for internal code organization

### Checking Import Efficiency

```bash
# Analyze bundle to see which imports are included
npm run build:analyze

# Look for:
# - Unexpectedly large chunks
# - Duplicate dependencies
# - Unused code in vendor chunks
```

---

## Bundle Analysis

### Running Analysis

```bash
# Production bundle analysis
npm run build:analyze

# Staging bundle analysis
npm run build:analyze:staging

# Analysis with size checking
npm run build:check-size
```

### Analysis Output

After running analysis, open `dist/stats.html` to view:

- **Treemap visualization**: Visual representation of bundle composition
- **Gzipped sizes**: Actual sizes after compression
- **Brotli sizes**: Sizes with Brotli compression
- **Dependency tree**: Full dependency graph
- **Chunk breakdown**: Size of each chunk

### Interpreting Results

#### Large Chunks

If a chunk is unexpectedly large:

1. Check for duplicate dependencies
2. Verify tree shaking is working
3. Consider code splitting
4. Review import patterns

#### Duplicate Dependencies

If the same library appears multiple times:

1. Check `package.json` for version conflicts
2. Verify `dedupe` configuration in `vite.config.ts`
3. Use `npm ls <package>` to find duplicates

#### Unused Code

If unused code appears in the bundle:

1. Verify `sideEffects` in `package.json`
2. Check for side-effect imports
3. Review barrel export usage
4. Ensure ESM modules are used

---

## Bundle Size Budgets

### Current Budgets

| Type | Gzipped | Uncompressed |
|------|---------|--------------|
| Initial Load | 200 KB | 500 KB |
| Individual Chunk | 500 KB | 1.2 MB |
| Vendor Chunk | 600 KB | 1.5 MB |
| Total Bundle | 1 MB | 2.5 MB |

### Checking Budgets

```bash
# Build and check against budgets
npm run build:check-size

# Output shows:
# - Total bundle size
# - Per-chunk sizes
# - Budget violations
```

### Adjusting Budgets

Edit `scripts/check-bundle-size.js` to modify budgets:

```javascript
const BUNDLE_BUDGETS = {
  initial: {
    maxSize: 200, // KB gzipped
    maxUncompressed: 500, // KB uncompressed
  },
  // ... other budgets
}
```

---

## Best Practices

### 1. Code Splitting

- Use route-based code splitting (already implemented)
- Lazy load heavy components (Monaco Editor, etc.)
- Split vendor libraries by stability

### 2. Dependency Management

- Keep dependencies up to date
- Remove unused dependencies
- Use `npm audit` to check for vulnerabilities
- Prefer smaller, focused libraries

### 3. Asset Optimization

- Optimize images before adding to project
- Use modern image formats (WebP, AVIF)
- Lazy load images below the fold
- Use appropriate image sizes

### 4. CSS Optimization

- Use CSS code splitting (enabled)
- Remove unused CSS
- Prefer CSS modules or styled-components
- Avoid global CSS when possible

### 5. Build Configuration

- Use production builds for final deployment
- Enable minification in staging/production
- Use appropriate source map settings
- Monitor bundle sizes in CI/CD

---

## Troubleshooting

### Bundle Size Increased Unexpectedly

1. **Check for new dependencies**:
   ```bash
   npm ls --depth=0
   ```

2. **Analyze bundle**:
   ```bash
   npm run build:analyze
   ```

3. **Check for duplicate dependencies**:
   ```bash
   npm ls <package-name>
   ```

4. **Review recent changes**:
   - New imports
   - Barrel export usage
   - Dynamic import changes

### Tree Shaking Not Working

1. **Verify `sideEffects` in `package.json`**:
   ```json
   {
     "sideEffects": ["**/*.css", "src/main.tsx"]
   }
   ```

2. **Check for side-effect imports**:
   ```typescript
   // ❌ Side effect import
   import './styles.css' // Has side effects

   // ✅ No side effects
   import { Component } from './Component'
   ```

3. **Ensure ESM modules**:
   - Use `"type": "module"` in `package.json`
   - Prefer named exports
   - Avoid CommonJS (`require`)

### Large Vendor Chunks

1. **Review chunking strategy** in `vite.config.ts`
2. **Consider lazy loading** heavy libraries
3. **Check for unnecessary dependencies**
4. **Use CDN** for very large libraries (if appropriate)

### Build Performance Issues

1. **Optimize `optimizeDeps`** in `vite.config.ts`
2. **Exclude heavy libraries** from pre-bundling
3. **Use build cache** effectively
4. **Monitor build times** in CI/CD

---

## Tools and Resources

### Built-in Tools

- **Vite Bundle Analyzer**: `npm run build:analyze`
- **Bundle Size Checker**: `npm run build:check-size`
- **TypeScript**: Type checking and optimization

### External Tools

- [Bundlephobia](https://bundlephobia.com/): Check package sizes before installing
- [Webpack Bundle Analyzer](https://github.com/webpack-contrib/webpack-bundle-analyzer): Alternative analyzer
- [Source Map Explorer](https://github.com/danvk/source-map-explorer): Analyze source maps

### Documentation

- [Vite Build Optimization](https://vitejs.dev/guide/build.html)
- [Rollup Tree Shaking](https://rollupjs.org/guide/en/#tree-shaking)
- [ES Modules](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Modules)

---

## Maintenance

### Regular Tasks

1. **Weekly**: Review bundle sizes after major changes
2. **Monthly**: Audit dependencies and remove unused packages
3. **Quarterly**: Review and update bundle size budgets
4. **As needed**: Optimize imports when bundle size increases

### Monitoring

- Set up CI/CD checks for bundle size budgets
- Monitor bundle sizes in deployment pipeline
- Track bundle size trends over time
- Alert on significant size increases

---

## Summary

Bundle optimization is an ongoing process. Follow these guidelines:

1. ✅ Use direct imports for large libraries
2. ✅ Prefer named exports
3. ✅ Lazy load heavy components
4. ✅ Monitor bundle sizes regularly
5. ✅ Keep dependencies minimal
6. ✅ Use bundle analysis tools
7. ✅ Follow import best practices
8. ✅ Review and optimize regularly

For questions or issues, refer to the troubleshooting section or consult the development team.

