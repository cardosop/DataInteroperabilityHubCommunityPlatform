# Build and Deployment Configuration

**Last Updated**: 2025-12-14
**Version**: 1.0.0

---

## Overview

This document describes the build and deployment configuration for the frontend application. The build system uses Vite with environment-specific configurations for development, staging, and production environments.

---

## Build Environments

### Development
- **Mode**: `development`
- **Source Maps**: Inline (for fast debugging)
- **Minification**: Disabled
- **Console Logs**: Enabled
- **Optimization**: Minimal (fast builds)

**Command**:
```bash
npm run build:development
```

### Staging
- **Mode**: `staging`
- **Source Maps**: Separate files (for debugging without exposing in production)
- **Minification**: Enabled (Terser)
- **Console Logs**: Enabled (for debugging)
- **Optimization**: Moderate (balanced performance)

**Command**:
```bash
npm run build:staging
```

### Production
- **Mode**: `production`
- **Source Maps**: Hidden (generated but not referenced)
- **Minification**: Enabled (Terser with aggressive compression)
- **Console Logs**: Removed
- **Optimization**: Maximum (best performance)

**Command**:
```bash
npm run build:production
```

---

## Build Configuration

### Source Maps

Source maps are configured differently for each environment:

- **Development**: Inline source maps for immediate debugging
- **Staging**: Separate `.map` files for debugging without exposing in production
- **Production**: Hidden source maps (generated but not referenced in HTML)

**Configuration Location**: `vite.config.ts` → `build.sourcemap`

### Code Splitting

The build uses intelligent code splitting with manual chunking:

1. **Vendor Chunks**:
   - `react-vendor`: React, React DOM, React Router
   - `mui-vendor`: Material-UI and Emotion
   - `query-vendor`: TanStack Query
   - `apollo-vendor`: Apollo Client and GraphQL
   - `form-vendor`: React Hook Form and Zod
   - `i18n-vendor`: i18next libraries
   - `analytics-vendor`: Sentry and Google Analytics
   - `http-vendor`: Axios
   - `vendor`: Other node_modules

2. **Application Chunks**:
   - `lib`: Shared library code
   - `components`: Reusable components
   - `pages`: Page components

**Benefits**:
- Better caching (vendor code changes less frequently)
- Parallel loading
- Smaller initial bundle size

### Minification

- **Tool**: Terser
- **Configuration**: Environment-specific
  - **Development**: No minification
  - **Staging**: Basic minification
  - **Production**: Aggressive minification with 3 passes

**Features**:
- Dead code elimination
- Console log removal (production only)
- Comment removal
- Variable name mangling

### Asset Optimization

- **CSS**: Minified in staging and production
- **Images**: Preserved with hashed filenames
- **Fonts**: Organized in `assets/fonts/`
- **JavaScript**: Code splitting and tree shaking

---

## Bundle Analysis

### Running Bundle Analysis

Analyze bundle size and composition:

```bash
# Production bundle analysis
npm run build:analyze

# Staging bundle analysis
npm run build:analyze:staging
```

### Analysis Output

After running analysis, open `dist/stats.html` in your browser to view:
- Bundle size breakdown
- Chunk composition
- Gzipped and Brotli sizes
- Dependency tree visualization

### Interpreting Results

- **Large chunks**: Consider code splitting
- **Duplicate dependencies**: Check for version conflicts
- **Unused code**: Verify tree shaking is working
- **Vendor size**: Monitor third-party library sizes

---

## Build Scripts

### Development
```bash
npm run dev              # Start dev server (development mode)
npm run dev:staging      # Start dev server (staging mode)
```

### Building
```bash
npm run build                    # Build for production
npm run build:development        # Build for development
npm run build:staging            # Build for staging
npm run build:production         # Build for production
npm run build:analyze            # Build with bundle analysis
npm run build:analyze:staging    # Build staging with analysis
```

### Preview
```bash
npm run preview              # Preview production build
npm run preview:staging      # Preview staging build
npm run preview:production   # Preview production build
```

---

## Environment Variables

Build-time environment variables must be prefixed with `VITE_`:

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000
VITE_ENV=development
```

See `.env.example` for all available variables.

---

## Build Output

### Directory Structure
```
dist/
├── assets/
│   ├── js/              # JavaScript bundles
│   ├── css/             # CSS files
│   ├── images/          # Images
│   └── fonts/           # Fonts
├── index.html           # Entry HTML
└── stats.html           # Bundle analysis (if ANALYZE=true)
```

### File Naming
- **JavaScript**: `[name]-[hash].js`
- **CSS**: `[name]-[hash].css`
- **Images**: `[name]-[hash].[ext]`
- **Fonts**: `[name]-[hash].[ext]`

Hash-based filenames enable long-term caching.

---

## Performance Targets

### Bundle Size Targets
- **Initial Load**: < 200KB (gzipped)
- **Total Bundle**: < 1MB (gzipped)
- **Chunk Size**: < 500KB per chunk

### Build Time Targets
- **Development Build**: < 5 seconds
- **Production Build**: < 30 seconds

---

## Deployment

### Static Hosting

The build output in `dist/` can be deployed to any static hosting service:

- **Vercel**: Automatic deployment
- **Netlify**: Automatic deployment
- **AWS S3 + CloudFront**: Manual upload
- **GitHub Pages**: Manual deployment

### Docker Deployment

See `docker-compose.yml` for containerized deployment configuration.

### CI/CD Integration

Build commands can be integrated into CI/CD pipelines:

```yaml
# Example GitHub Actions
- name: Build
  run: |
    cd frontend
    npm ci
    npm run build:production
```

---

## Troubleshooting

### Build Failures

1. **Type Errors**: Run `npm run type-check` to identify issues
2. **Lint Errors**: Run `npm run lint` to check code quality
3. **Dependency Issues**: Run `npm install` to update dependencies

### Performance Issues

1. **Large Bundle Size**: Run bundle analysis to identify large dependencies
2. **Slow Builds**: Check for unnecessary dependencies or large assets
3. **Slow Dev Server**: Clear cache and restart

### Source Map Issues

1. **Missing Source Maps**: Check `build.sourcemap` configuration
2. **Incorrect Line Numbers**: Verify source map generation
3. **Large Source Maps**: Consider using hidden source maps in production

---

## Best Practices

1. **Always run type-check before building**: `npm run type-check`
2. **Use environment-specific builds**: Don't use production builds in development
3. **Monitor bundle size**: Run bundle analysis regularly
4. **Optimize images**: Use appropriate formats and sizes
5. **Code splitting**: Keep initial bundle small
6. **Tree shaking**: Remove unused code
7. **Cache strategy**: Use hash-based filenames for long-term caching

---

## References

- [Vite Documentation](https://vitejs.dev/)
- [Rollup Plugin Visualizer](https://github.com/btd/rollup-plugin-visualizer)
- [Terser Documentation](https://terser.org/)

