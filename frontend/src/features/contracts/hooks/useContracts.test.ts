/**
 * useContracts tests — Phase 105
 */
import { describe, expect, it } from 'vitest';

// Import the hooks module to verify exports
import * as hookModule from './useContracts';

describe('useContracts', () => {
  it('exports hook functions', () => {
    const exports = Object.keys(hookModule);
    expect(exports.length).toBeGreaterThan(0);
    // All exports should be functions (hooks)
    for (const key of exports) {
      expect(typeof hookModule[key as keyof typeof hookModule]).toBe('function');
    }
  });

  it('all exported hooks follow use* naming convention', () => {
    const exports = Object.keys(hookModule);
    for (const key of exports) {
      if (typeof hookModule[key as keyof typeof hookModule] === 'function') {
        expect(key).toMatch(/^use[A-Z]/);
      }
    }
  });

  it('exports useContracts', () => {
    expect(hookModule.useContracts).toBeDefined();
    expect(typeof hookModule.useContracts).toBe('function');
  });

  it('exports useContract', () => {
    expect(hookModule.useContract).toBeDefined();
    expect(typeof hookModule.useContract).toBe('function');
  });

  it('exports useCreateContract', () => {
    expect(hookModule.useCreateContract).toBeDefined();
    expect(typeof hookModule.useCreateContract).toBe('function');
  });

  it('exports useUpdateContract', () => {
    expect(hookModule.useUpdateContract).toBeDefined();
    expect(typeof hookModule.useUpdateContract).toBe('function');
  });

  it('exports useDeleteContract', () => {
    expect(hookModule.useDeleteContract).toBeDefined();
    expect(typeof hookModule.useDeleteContract).toBe('function');
  });

  // Merged ODPS hooks (211.A5.3)
  it('exports useContractWorkflowStatus', () => {
    expect(hookModule.useContractWorkflowStatus).toBeDefined();
    expect(typeof hookModule.useContractWorkflowStatus).toBe('function');
  });

  it('exports useODPSWorkflowStatus as deprecated alias', () => {
    expect(hookModule.useODPSWorkflowStatus).toBeDefined();
    expect(hookModule.useODPSWorkflowStatus).toBe(hookModule.useContractWorkflowStatus);
  });

  it('exports useCreateODPSProduct', () => {
    expect(hookModule.useCreateODPSProduct).toBeDefined();
    expect(typeof hookModule.useCreateODPSProduct).toBe('function');
  });

  it('exports useLinkODPS', () => {
    expect(hookModule.useLinkODPS).toBeDefined();
    expect(typeof hookModule.useLinkODPS).toBe('function');
  });

  it('exports useUnlinkODPS', () => {
    expect(hookModule.useUnlinkODPS).toBeDefined();
    expect(typeof hookModule.useUnlinkODPS).toBe('function');
  });

  it('exports useContractLinks', () => {
    expect(hookModule.useContractLinks).toBeDefined();
    expect(typeof hookModule.useContractLinks).toBe('function');
  });

  it('exports useODPSLinks as deprecated alias', () => {
    expect(hookModule.useODPSLinks).toBeDefined();
    expect(hookModule.useODPSLinks).toBe(hookModule.useContractLinks);
  });

  it('exports useExportODPS', () => {
    expect(hookModule.useExportODPS).toBeDefined();
    expect(typeof hookModule.useExportODPS).toBe('function');
  });

  it('exports useDownloadODPS', () => {
    expect(hookModule.useDownloadODPS).toBeDefined();
    expect(typeof hookModule.useDownloadODPS).toBe('function');
  });

});
