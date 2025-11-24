# Publishing SDK to npm

## Prerequisites

1. npm account with access to `@datahub` organization
2. Authentication configured: `npm login`
3. Build completed: `npm run build`
4. Tests passing: `npm test`

## Publishing Steps

### 1. Update Version

Update version in `package.json`:
- Patch: `npm version patch` (1.0.0 → 1.0.1)
- Minor: `npm version minor` (1.0.0 → 1.1.0)
- Major: `npm version major` (1.0.0 → 2.0.0)

### 2. Build and Test

```bash
npm run build
npm test
```

### 3. Publish

```bash
npm publish --access public
```

For scoped packages (`@datahub/interoperability-sdk`), use `--access public` to make it publicly accessible.

## CI/CD Integration

Add to CI/CD pipeline:

```yaml
- name: Publish to npm
  if: github.ref == 'refs/heads/main' && github.event_name == 'push'
  run: |
    npm run build
    npm test
    npm publish --access public
  env:
    NODE_AUTH_TOKEN: ${{ secrets.NPM_TOKEN }}
```

## Notes

- SDK will be published as `@datahub/interoperability-sdk`
- Version follows semantic versioning
- Pre-publish hook runs build and tests automatically

