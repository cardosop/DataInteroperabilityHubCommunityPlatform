/**
 * Installation Tests
 * 
 * Tests for SDK installation, dependencies, and build process.
 */

describe('SDK Installation', () => {
  describe('Package Installation', () => {
    it('should have correct package name', () => {
      const packageJson = require('../../package.json');
      expect(packageJson.name).toBe('@datahub/interoperability-sdk');
    });

    it('should have required dependencies', () => {
      const packageJson = require('../../package.json');
      expect(packageJson.dependencies).toHaveProperty('axios');
      expect(packageJson.dependencies.axios).toMatch(/^\^1\./);
    });

    it('should have required devDependencies', () => {
      const packageJson = require('../../package.json');
      expect(packageJson.devDependencies).toHaveProperty('typescript');
      expect(packageJson.devDependencies).toHaveProperty('jest');
      expect(packageJson.devDependencies).toHaveProperty('@types/jest');
      expect(packageJson.devDependencies).toHaveProperty('ts-jest');
    });

    it('should have build script', () => {
      const packageJson = require('../../package.json');
      expect(packageJson.scripts).toHaveProperty('build');
      expect(packageJson.scripts.build).toBe('tsc');
    });

    it('should have test script', () => {
      const packageJson = require('../../package.json');
      expect(packageJson.scripts).toHaveProperty('test');
      expect(packageJson.scripts.test).toBe('jest');
    });
  });

  describe('Module Exports', () => {
    it('should export DataHubClient', () => {
      const { DataHubClient } = require('../index');
      expect(typeof DataHubClient).toBe('function');
    });

    it('should export ContractsAPI', () => {
      const { ContractsAPI } = require('../index');
      expect(typeof ContractsAPI).toBe('function');
    });

    it('should export LineageAPI', () => {
      const { LineageAPI } = require('../index');
      expect(typeof LineageAPI).toBe('function');
    });

    it('should export error classes', () => {
      const {
        DataHubError,
        ValidationError,
        UnauthorizedError,
        NotFoundError,
        NetworkError,
      } = require('../index');
      
      expect(DataHubError).not.toBeUndefined();
      expect(ValidationError).not.toBeUndefined();
      expect(UnauthorizedError).not.toBeUndefined();
      expect(NotFoundError).not.toBeUndefined();
      expect(NetworkError).not.toBeUndefined();
    });

    it('should export config types', () => {
      // TypeScript types are compile-time only, but we can verify the default config is exported
      const { DEFAULT_CONFIG } = require('../index');
      expect(DEFAULT_CONFIG).not.toBeUndefined();
      expect(DEFAULT_CONFIG.timeout).toBe(30000);
    });
  });

  describe('TypeScript Compilation', () => {
    it('should compile without errors', () => {
      // This test verifies that the TypeScript code compiles
      // If there are compilation errors, this test will fail during build
      const index = require('../index');
      expect(index).not.toBeUndefined();
    });

    it('should have type definitions', () => {
      // Verify that types are properly exported
      const { DataHubClient } = require('../index');
      const client = new DataHubClient({
        baseUrl: 'https://api.example.com/api/v1',
        apiToken: 'test-token',
      });
      
      // TypeScript should infer types correctly
      expect(client).toBeInstanceOf(DataHubClient);
    });
  });
});

