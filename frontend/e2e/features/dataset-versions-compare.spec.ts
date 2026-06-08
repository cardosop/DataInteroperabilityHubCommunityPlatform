/**
 * Phase 260.3.A — Dataset version schema compare (Gap 5).
 * Real backend file lifecycle + versioning API + Compare UI.
 */

import { expect } from '@playwright/test';
import { test as testWithCleanup } from '../fixtures/test-data-cleanup';
import { getTestUser } from '../fixtures/auth';
import { loginAndNavigateToRoute } from '../fixtures/helpers';
import {
  createDatasetViaApi,
  createDatasetVersionViaApi,
  fetchDatasetViaApi,
  fetchDatasetVersionsViaApi,
} from '../fixtures/api-assets';

testWithCleanup.describe('Feature: dataset versions compare', () => {
  testWithCleanup.setTimeout(180000);

  testWithCleanup(
    'provision v2 with backward-compatible schema then Compare shows FIELD_ADDED',
    async ({ page, cleanup }) => {
      const user = await getTestUser();
      const datasetId = await createDatasetViaApi(user, { forceNew: true, cleanup });

      const detail = await fetchDatasetViaApi(user, datasetId);
      const baseFields = [...((detail.schema_json?.fields as Record<string, unknown>[]) ?? [])];
      const extendedFields = [
        ...baseFields,
        { name: 'region', data_type: 'string', nullable: true },
      ];

      const v2 = await createDatasetVersionViaApi(user, datasetId, {
        semantic_version: '1.1.0',
        schema_json: { fields: extendedFields },
      });
      cleanup.track({ type: 'dataset', id: v2.id, owner: user });

      const versions = await fetchDatasetVersionsViaApi(user, datasetId);
      expect(versions.length).toBeGreaterThanOrEqual(2);

      await loginAndNavigateToRoute(page, user, `/datasets/${datasetId}/versions`, {
        timeout: 120000,
        contentSelector: '.dataset-versions-page, .dataset-versions-header, h1',
      });

      // noverify: opens the in-page Compare Versions form; no mutation.
      await page.getByTestId('dataset-version-compare-toggle').click();

      const oldest = versions[0];
      const newest = versions[versions.length - 1];

      await page.getByTestId('dataset-version-compare-select-1').selectOption(oldest.id);
      await page.getByTestId('dataset-version-compare-select-2').selectOption(newest.id);
      // noverify: submits a read-only diff query (GET /datasets/{id}/versions/diff/)
      // — produces a DatasetVersionDiffView render, no backend write or
      // audit emission.
      await page.getByTestId('dataset-version-compare-submit').click();

      const panel = page.getByTestId('dataset-version-diff-view');
      await expect(panel).toBeVisible({ timeout: 60000 });

      await expect(panel.getByTestId('dataset-version-diff-summary')).toContainText('FIELD_ADDED');

      const added = page.getByRole('region', { name: /Added fields/i });
      await expect(added.locator('td').filter({ hasText: /^region$/ })).toBeVisible();
    }
  );
});
