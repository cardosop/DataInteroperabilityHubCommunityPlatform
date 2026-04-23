// Fixture. Expected counts:
//
// - test_skip_true_count: 0
// - page_on_pageerror_count: 2
// - page_request_call_count: 0
// - verify_via_api_call_count: 0

import { test } from '@playwright/test';

test('a', async ({ page }) => {
  page.on('pageerror', (err) => {
    console.log(err);
  });
  await page.goto('/');
});

test('b', async ({ page }) => {
  // different events — not pageerror
  page.on('console', () => {});
  page.on('response', () => {});
});

// page.on('pageerror', (e) => {});  <-- comment, must not count

test('c', async ({ page }) => {
  const handler = (err: Error) => {
    void err;
  };
  page.on('pageerror', handler);
});
