// Fixture. Expected counts:
//
// - test_skip_true_count: 0
// - page_on_pageerror_count: 0
// - page_request_call_count: 3   (get, post, patch)
// - verify_via_api_call_count: 1 (verifyViaApi(...) once)

import { test } from '@playwright/test';

async function verifyViaApi(_page: unknown, _endpoint: string, _expected: unknown) {
  // stub — counting logic looks at CALL not body
}

test('uses verifyViaApi', async ({ page }) => {
  await page.click('button');
  await verifyViaApi(page, '/api/v1/assets/1/', { status: 'ACTIVE' });
});

test('uses page.request.get / post / patch', async ({ page }) => {
  await page.click('button');
  const r1 = await page.request.get('/api/v1/assets/');
  void r1;
  const r2 = await page.request.post('/api/v1/login/', { data: {} });
  void r2;
  const r3 = await page.request.patch('/api/v1/assets/1/', { data: {} });
  void r3;
});

// const r4 = await page.request.get('/commented');  <-- must not count
