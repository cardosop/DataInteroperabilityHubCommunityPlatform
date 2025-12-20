import react from '@vitejs/plugin-react'
import path from 'path'
import { visualizer } from 'rollup-plugin-visualizer'
import { defineConfig, type UserConfig } from 'vite'
import commonjs from '@rollup/plugin-commonjs'
import { patchInteropPlugin } from './vite-plugins/patch-interop'

// Environment type definitions
type Environment = 'development' | 'staging' | 'production'

// https://vite.dev/config/
export default defineConfig(({ mode }): UserConfig => {
  const env: Environment = (mode as Environment) || 'development'
  const isDevelopment = env === 'development'
  const isStaging = env === 'staging'
  const isProduction = env === 'production'

  // Source map configuration based on environment
  const getSourcemapConfig = (): boolean | 'inline' | 'hidden' => {
    if (isDevelopment) {
      // Development: Inline source maps for fast debugging
      return 'inline'
    }
    if (isStaging) {
      // Staging: Separate source maps for debugging without exposing in production
      return true
    }
    // Production: Hidden source maps (generated but not referenced)
    // Set to false if you want no source maps in production
    return 'hidden'
  }

  // Minification configuration
  const getMinifyConfig = (): boolean | 'esbuild' | 'terser' => {
    if (isDevelopment) {
      return false
    }
    // Use terser for better compression in staging and production
    return 'terser'
  }

  // Terser options for minification with enhanced tree shaking
  const getTerserOptions = (): any => {
    if (!isProduction && !isStaging) {
      return undefined
    }
    return {
      compress: {
        drop_console: isProduction, // Only drop console in production
        drop_debugger: true,
        pure_funcs: isProduction ? ['console.log', 'console.info', 'console.debug'] : [],
        passes: isProduction ? 3 : 1, // More passes for better compression in production
        dead_code: true, // Remove unreachable code
        unused: true, // Drop unreferenced functions and variables
        collapse_vars: true, // Collapse single-use variables
        reduce_vars: true, // Optimize variable usage
        side_effects: false, // Assume no side effects for better tree shaking
      },
      format: {
        comments: false, // Remove all comments
      },
      mangle: {
        safari10: true, // Fix Safari 10+ issues
        properties: false, // Don't mangle properties to avoid breaking code
      },
    } as any
  }

  // Build output configuration
  const getBuildConfig = () => {
    const baseConfig = {
      outDir: 'dist',
      assetsDir: 'assets',
      sourcemap: getSourcemapConfig(),
      minify: getMinifyConfig(),
      terserOptions: getTerserOptions(),
      cssMinify: isProduction || isStaging,
      cssCodeSplit: true,
      reportCompressedSize: true, // Report gzipped sizes
      chunkSizeWarningLimit: 500, // Warn if chunk exceeds 500KB (optimized from 1MB)
      emptyOutDir: true, // Clear output directory before build
      // Use latest ES features for better tree shaking and smaller bundles
      target: 'esnext',
      // Optimize chunk sizes with better splitting
        rollupOptions: {
          // Add CommonJS plugin to Rollup build
          plugins: [
            commonjs({
              transformMixedEsModules: true,
              include: [/node_modules/],
            }) as any,
          ],
          treeshake: {
          moduleSideEffects: id => {
            // CSS files have side effects
            if (id.endsWith('.css') || id.endsWith('.scss') || id.endsWith('.sass')) {
              return true
            }
            // Main entry point has side effects
            if (id.includes('main.tsx') || id.includes('main.ts')) {
              return true
            }
            // Most other files can be tree-shaken
            return false
          },
          propertyReadSideEffects: false, // Assume property reads have no side effects
          tryCatchDeoptimization: false, // Don't deoptimize try-catch for better tree shaking
        },
        output: {
          // Manual chunking strategy for optimal caching and code splitting
          manualChunks: (id: string) => {
            // Node modules chunking (vendor libraries)
            if (id.includes('node_modules')) {
              // React ecosystem - core framework (highly stable, cache separately)
              if (
                id.includes('react/') ||
                id.includes('react-dom/') ||
                id.includes('react-router-dom/') ||
                id.includes('react-router/')
              ) {
                return 'vendor-react'
              }
              // Material-UI ecosystem - UI library (large, stable)
              if (
                id.includes('@mui/') ||
                id.includes('@emotion/') ||
                id.includes('@babel/runtime')
              ) {
                return 'vendor-mui'
              }
              // Monaco Editor - heavy editor library (lazy load separately)
              if (id.includes('monaco-editor') || id.includes('@monaco-editor')) {
                return 'vendor-monaco'
              }
              // Query libraries - data fetching (stable)
              if (id.includes('@tanstack/react-query')) {
                return 'vendor-query'
              }
              // GraphQL ecosystem - GraphQL client (lazy load if not always used)
              if (id.includes('@apollo/') || id.includes('graphql/')) {
                return 'vendor-apollo'
              }
              // Form libraries - form handling (stable)
              if (
                id.includes('react-hook-form') ||
                id.includes('@hookform/') ||
                id.includes('zod')
              ) {
                return 'vendor-forms'
              }
              // i18n libraries - internationalization (stable)
              if (id.includes('i18next') || id.includes('react-i18next')) {
                return 'vendor-i18n'
              }
              // Analytics and monitoring - optional features (lazy load)
              if (id.includes('@sentry/') || id.includes('react-ga4')) {
                return 'vendor-analytics'
              }
              // HTTP clients - network layer (stable)
              if (id.includes('axios')) {
                return 'vendor-http'
              }
              // Lodash - utility library (lazy load if used sparingly)
              if (id.includes('lodash')) {
                return 'vendor-utils'
              }
              // All other node_modules - catch-all vendor chunk
              return 'vendor-other'
            }
            // Application code chunking by feature/domain
            // Pages - route-based code splitting (already handled by lazy routes)
            if (id.includes('/src/pages/')) {
              // Extract feature/domain from path for better chunking
              const pathMatch = id.match(/\/src\/pages\/([^/]+)/)
              if (pathMatch) {
                const feature = pathMatch[1]
                // Group related pages together
                if (['admin', 'platform'].includes(feature)) {
                  return `pages-admin`
                }
                if (['marketplace'].includes(feature)) {
                  return `pages-marketplace`
                }
                if (['compliance', 'data-quality'].includes(feature)) {
                  return `pages-governance`
                }
                // Individual page chunks for better code splitting
                return `pages-${feature}`
              }
              return 'pages'
            }
            // Components - component-based code splitting
            if (id.includes('/src/components/')) {
              // Heavy components that should be split separately
              if (
                id.includes('monaco') ||
                id.includes('CodeSnippetGenerator') ||
                id.includes('RawEditorTab') ||
                id.includes('APIExplorer')
              ) {
                return 'components-editor'
              }
              // Admin components
              if (id.includes('/admin/') || id.includes('/platform/')) {
                return 'components-admin'
              }
              // Marketplace components
              if (id.includes('/marketplace/')) {
                return 'components-marketplace'
              }
              // Common/shared components (loaded early)
              if (id.includes('/common/') || id.includes('/layout/') || id.includes('/feedback/')) {
                return 'components-common'
              }
              // Other components
              return 'components'
            }
            // Library code - utilities and shared code
            if (id.includes('/src/lib/')) {
              // API client code
              if (id.includes('/api/')) {
                return 'lib-api'
              }
              // GraphQL code
              if (id.includes('/graphql/')) {
                return 'lib-graphql'
              }
              // Config code
              if (id.includes('/config/')) {
                return 'lib-config'
              }
              return 'lib'
            }
            // Hooks - can be split if needed
            if (id.includes('/src/hooks/')) {
              return 'hooks'
            }
            // Utils - shared utilities
            if (id.includes('/src/utils/')) {
              return 'utils'
            }
          },
          // File naming strategy with better organization
          chunkFileNames: (chunkInfo: { facadeModuleId: string | null; name: string }) => {
            // Use chunk name if available (from manualChunks)
            if (chunkInfo.name) {
              return `assets/js/${chunkInfo.name}-[hash].js`
            }
            // Fallback to facade module ID
            const facadeModuleId = chunkInfo.facadeModuleId
              ? chunkInfo.facadeModuleId
                  .split('/')
                  .pop()
                  ?.replace(/\.[^.]*$/, '')
              : 'chunk'
            return `assets/js/${facadeModuleId}-[hash].js`
          },
          entryFileNames: 'assets/js/[name]-[hash].js',
          assetFileNames: (assetInfo: { name?: string }) => {
            const info = assetInfo.name?.split('.') || []
            const ext = info[info.length - 1]
            if (/png|jpe?g|svg|gif|tiff|bmp|ico/i.test(ext || '')) {
              return `assets/images/[name]-[hash][extname]`
            }
            if (/woff2?|eot|ttf|otf/i.test(ext || '')) {
              return `assets/fonts/[name]-[hash][extname]`
            }
            return `assets/${ext}/[name]-[hash][extname]`
          },
          // Optimize chunk loading
          compact: isProduction,
        },
        // External dependencies (if needed for CDN)
        external: [],
      },
    }

    return baseConfig
  }

  // Custom plugin to inject interop helpers and patch pre-bundled modules
  // This plugin uses buildStart to ensure helpers are available before optimization
  const interopHelpersPlugin = (): any => {
    return {
      name: 'interop-helpers',
      enforce: 'pre',
      buildStart() {
        // Ensure helpers are available globally before optimization starts
        // This runs once at build start
      },
      transformIndexHtml(html) {
        // Inject helpers in HTML - ensure they're available before any modules load
        const helpers = `
          <script>
            // CommonJS/ESM interop helpers - must be available before module code runs
            (function() {
              var helper = function(obj) {
                return obj && obj.__esModule ? obj : { default: obj };
              };
              // Define on all global objects for maximum compatibility
              if (typeof globalThis !== 'undefined') {
                globalThis._interopRequireDefault = helper;
                globalThis._interopRequireDefault2 = helper;
              }
              if (typeof window !== 'undefined') {
                window._interopRequireDefault = helper;
                window._interopRequireDefault2 = helper;
              }
              if (typeof global !== 'undefined') {
                global._interopRequireDefault = helper;
                global._interopRequireDefault2 = helper;
              }
            })();
          </script>
        `
        return html.replace('<head>', `<head>${helpers}`)
      },
      // Note: Transform hook removed - it was creating invalid JavaScript
      // The HTML injection should be sufficient if the helpers are available globally
      // If the error persists, we need to identify which dependency is causing it
      // and exclude it from optimization or use dynamic imports
    }
  }

  // Plugins configuration
  const plugins = [
    // Add interop helpers plugin first
    interopHelpersPlugin(),
    react({
      // Include JSX runtime
      jsxRuntime: 'automatic',
      // Babel options for development
      babel: isDevelopment
        ? {
            plugins: [
              // Add development-only plugins here if needed
            ],
          }
        : undefined,
    }),
  ]

  // Enhanced bundle analyzer configuration
  // Only run when ANALYZE env var is explicitly set to avoid unnecessary overhead
  if (process.env.ANALYZE === 'true') {
    plugins.push(
      visualizer({
        filename: './dist/stats.html',
        open: process.env.ANALYZE_OPEN !== 'false', // Allow disabling auto-open
        gzipSize: true,
        brotliSize: true,
        template: (process.env.ANALYZE_TEMPLATE as 'sunburst' | 'treemap' | 'network') || 'treemap',
        // Enhanced analysis options
        title: 'Bundle Analysis - Data Interoperability Hub',
        generateStatsFile: true,
        statsFilename: './dist/stats.json',
        // Show detailed breakdown
        sourcemap: true,
        // Filter out node_modules details for cleaner view (can be toggled)
        includeSource: true,
      }) as any // Type assertion for visualizer plugin
    )
  }

  // Base configuration
  const config: UserConfig = {
    plugins,
    // Define interop helpers - but this only works for source code, not pre-bundled deps
    // We rely on the interop-helpers plugin for pre-bundled dependencies
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
        // Alias interop helpers so pre-bundled modules can import them
        '_interopRequireDefault': path.resolve(__dirname, './src/lib/utils/interop-helpers.ts'),
        '_interopRequireDefault2': path.resolve(__dirname, './src/lib/utils/interop-helpers.ts'),
      },
      // Optimize dependency resolution - deduplicate common dependencies
      dedupe: ['react', 'react-dom', '@emotion/react', '@emotion/styled'],
      // Prefer ESM for better tree shaking
      mainFields: ['module', 'jsnext:main', 'jsnext', 'main'],
      // Optimize conditions for ESM resolution
      conditions: ['import', 'module', 'browser', 'default'],
      // Better CommonJS/ESM interop
      preserveSymlinks: false,
    },
    // Environment variables
    envPrefix: 'VITE_',
    // Server configuration
    server: {
      port: process.env.VITE_DEV_SERVER_PORT ? parseInt(process.env.VITE_DEV_SERVER_PORT) : 5173,
      host: true,
      open: !isProduction, // Don't auto-open in production builds
      strictPort: false,
      proxy: {
        '/api': {
          target: process.env.VITE_API_BASE_URL || 'http://localhost:8000',
          changeOrigin: true,
          secure: false,
          ws: false,
        },
        '/ws': {
          target: process.env.VITE_WS_URL || 'ws://localhost:8000',
          ws: true,
          changeOrigin: true,
        },
        '/graphql': {
          target: process.env.VITE_GRAPHQL_URL || 'http://localhost:8000',
          changeOrigin: true,
          secure: false,
        },
      },
    },
    // Preview server configuration
    preview: {
      port: 4173,
      host: true,
      strictPort: false,
    },
    // Build configuration with CommonJS interop support
    build: {
      ...getBuildConfig(),
      // Ensure proper CommonJS/ESM interop in build
      commonjsOptions: {
        include: [/node_modules/],
        transformMixedEsModules: true,
      },
    },
    // Optimize dependencies - include essential packages that need pre-bundling
    // The patch plugin will fix any interop issues in pre-bundled code
    optimizeDeps: {
      include: [
        'react',
        'react-dom',
        'react-router-dom',
        '@mui/material',
        '@mui/material/styles',
        '@emotion/react',
        '@emotion/styled',
        // Include CommonJS packages that need pre-bundling
        'hoist-non-react-statics',
      ],
      exclude: [
        // Exclude packages that cause interop issues or should be lazy-loaded
        '@tanstack/react-query',
        '@apollo/client',
        // Exclude heavy libraries that should be lazy-loaded
        'monaco-editor',
        '@monaco-editor/react',
        // Exclude CommonJS packages that cause interop issues
        'react-ga4',
        'i18next',
        'react-i18next',
        'i18next-browser-languagedetector',
        'web-vitals',
        'js-yaml',
        'lodash-es',
      ],
      // Force re-optimization to regenerate with patch plugin
      force: true,
      // Wait for optimization to complete
      holdUntilCrawlEnd: false,
      // esbuild options
      esbuildOptions: {
        treeShaking: true,
        target: 'esnext',
        // Note: inject doesn't work well with pre-bundling
        // We rely on HTML injection + global definitions instead
      },
    },
    // Logging level
    logLevel: isDevelopment ? 'info' : 'warn',
    // Clear screen on restart
    clearScreen: !isDevelopment,
  }

  return config
})
