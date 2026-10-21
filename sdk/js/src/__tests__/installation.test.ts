/**
 * Installation Tests
 *
 * Tests for SDK installation, dependencies, and build process.
 */

import * as packageJson from '../../package.json';
import * as sdk from '../index';
import { DataHubClient } from '../client';

describe('SDK Installation', () => {
  describe('Package Installation', () => {
    it('should have correct package name', () => {
      expect(packageJson.name).toBe('@meshant/interoperability-sdk');
    });

    it('should have zero runtime dependencies (fetch client, W6.2 axios eviction)', () => {
      // The SDK is implemented on the platform fetch API — no runtime
      // dependencies at all (axios was repo-evicted as a supply-chain
      // risk; CLAUDE.md policy).
      expect(packageJson.dependencies).toEqual({});
    });

    it('should declare Node >= 18 (global fetch / AbortSignal.timeout)', () => {
      expect(packageJson.engines.node).toBe('>=18');
    });

    it('should have required devDependencies', () => {
      expect(packageJson.devDependencies).toHaveProperty('typescript');
      expect(packageJson.devDependencies).toHaveProperty('jest');
      expect(packageJson.devDependencies).toHaveProperty('@types/jest');
      expect(packageJson.devDependencies).toHaveProperty('ts-jest');
    });

    it('should have build script', () => {
      expect(packageJson.scripts).toHaveProperty('build');
      expect(packageJson.scripts.build).toBe('tsc');
    });

    it('should have test script', () => {
      expect(packageJson.scripts).toHaveProperty('test');
      expect(packageJson.scripts.test).toBe('jest');
    });
  });

  describe('Module Exports', () => {
    it('should export DataHubClient', () => {
      const { DataHubClient: Exported } = sdk;
      expect(typeof Exported).toBe('function');
    });

    it('should export ContractsAPI', () => {
      const { ContractsAPI } = sdk;
      expect(typeof ContractsAPI).toBe('function');
    });

    it('should export LineageAPI', () => {
      const { LineageAPI } = sdk;
      expect(typeof LineageAPI).toBe('function');
    });

    it('should export error classes', () => {
      const {
        DataHubError,
        ValidationError,
        UnauthorizedError,
        NotFoundError,
        NetworkError,
      } = sdk;

      expect(DataHubError).not.toBeUndefined();
      expect(ValidationError).not.toBeUndefined();
      expect(UnauthorizedError).not.toBeUndefined();
      expect(NotFoundError).not.toBeUndefined();
      expect(NetworkError).not.toBeUndefined();
    });

    it('should export config types', () => {
      // TypeScript types are compile-time only, but we can verify the default config is exported
      const { DEFAULT_CONFIG } = sdk;
      expect(DEFAULT_CONFIG).not.toBeUndefined();
      expect(DEFAULT_CONFIG.timeout).toBe(30000);
    });
  });

  describe('TypeScript Compilation', () => {
    it('should compile without errors', () => {
      // This test verifies that the TypeScript code compiles
      // If there are compilation errors, this test will fail during build
      expect(sdk).not.toBeUndefined();
    });

    it('should have type definitions', () => {
      // Verify that types are properly exported
      const client = new DataHubClient({
        baseUrl: 'https://api.example.com/api/v1',
        apiToken: 'test-token',
      });

      // TypeScript should infer types correctly
      expect(client).toBeInstanceOf(DataHubClient);
    });
  });
});
