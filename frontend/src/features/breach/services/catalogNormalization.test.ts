/**
 * breachService.getTemplateCatalog — response-shape normalization (Phase 1.5).
 *
 * ``BreachTemplateEditorPage`` stores ``catalog.templates`` and calls
 * ``rows.find``/``rows.map`` on it. The backend returns
 * ``{"templates": [...]}`` today; a missing/non-array ``templates`` key
 * (drift, error envelope) crashed the render with
 * "rows.find is not a function". Normalize the key at the service boundary
 * so the editor renders the empty state instead of crashing.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../../shared/api/client');

import { apiClient } from '../../../shared/api/client';
import { breachService } from './breachService';

describe('breachService.getTemplateCatalog', () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it('passes a valid templates array through unchanged', async () => {
    const catalog = {
      templates: [
        { id: 't1', regime: 'gdpr', name: 'GDPR breach' },
        { id: 't2', regime: 'ccpa', name: 'CCPA breach' },
      ],
    };
    vi.mocked(apiClient.getClient().get).mockResolvedValue({ data: catalog } as never);

    await expect(breachService.getTemplateCatalog()).resolves.toEqual(catalog);
  });

  it('normalizes a missing templates key to []', async () => {
    vi.mocked(apiClient.getClient().get).mockResolvedValue({
      data: { error: 'proxy exploded' },
    } as never);

    await expect(breachService.getTemplateCatalog()).resolves.toEqual({ templates: [] });
  });

  it('normalizes a non-array templates value to []', async () => {
    vi.mocked(apiClient.getClient().get).mockResolvedValue({
      data: { templates: { gdpr: 'not an array' } },
    } as never);

    await expect(breachService.getTemplateCatalog()).resolves.toEqual({ templates: [] });
  });

  it('normalizes a null payload to an empty catalog', async () => {
    vi.mocked(apiClient.getClient().get).mockResolvedValue({ data: null } as never);

    await expect(breachService.getTemplateCatalog()).resolves.toEqual({ templates: [] });
  });
});
