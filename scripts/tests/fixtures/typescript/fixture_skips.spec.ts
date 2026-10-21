// Fixture for e2e_metrics TypeScript counting. Expected counts:
//
// - test_skip_true_count: 3    (literal `true` as first arg)
// - page_on_pageerror_count: 0
// - page_request_call_count: 0
// - verify_via_api_call_count: 0

import { test } from '@playwright/test';

test('literal true counts', async ({ page }) => {
  test.skip(true, 'literal — counts');
  await page.goto('/');
});

test('variable does not count', async ({ page }) => {
  const cond = process.env.CI === 'true';
  test.skip(cond, 'conditional — does NOT count');
});

test('positional literal counts', async () => {
  test.skip(true);
});

test('commented skip does not count', async () => {
  // test.skip(true, 'in comment — does NOT count');
});

test.describe('group', () => {
  test('inner literal counts', async () => {
    test.skip(true, 'inside describe — counts');
  });
});
