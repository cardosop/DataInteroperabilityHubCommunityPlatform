/**
 * Playwright Global Setup
 *
 * Runs once before all tests.
 * Use this to:
 * - Set up test databases
 * - Authenticate and get tokens
 * - Prepare test data
 * - Start external services
 */

import { chromium, type FullConfig } from '@playwright/test'
import { config } from '../src/lib/config'

async function globalSetup(config: FullConfig) {
  console.log('Starting Playwright global setup...')

  // Example: Authenticate and save storage state
  // This can be used to avoid logging in for every test
  const browser = await chromium.launch()
  const context = await browser.newContext({
    baseURL: config.projects[0].use.baseURL,
  })
  const page = await context.newPage()

  // Perform authentication if needed
  // const token = process.env.TEST_AUTH_TOKEN
  // if (token) {
  //   await page.goto('/login')
  //   await page.fill('[name="email"]', 'test@example.com')
  //   await page.fill('[name="password"]', 'password')
  //   await page.click('button[type="submit"]')
  //   await page.waitForURL('**/dashboard')
  //   await context.storageState({ path: 'playwright/.auth/user.json' })
  // }

  await browser.close()

  console.log('Playwright global setup completed.')
}

export default globalSetup

