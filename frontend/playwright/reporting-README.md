# Playwright Test Reporting

Comprehensive test reporting configuration for Playwright E2E tests.

## Features

- **HTML Reports**: Detailed HTML reports with attachments (screenshots, videos, traces)
- **Video Recording**: Automatic video recording on test failure
- **Screenshot Capture**: Automatic screenshot capture on test failure
- **JUnit Reports**: XML reports for CI/CD integration
- **JSON Reports**: Machine-readable JSON reports
- **Notifications**: Slack and Email notifications
- **Test Dashboard**: Optional HTML dashboard for visualizing test metrics
- **Result Aggregation**: Aggregate results across multiple browsers/projects

## Configuration

### HTML Reports

HTML reports are automatically generated in `playwright/reports/html/`. They include:
- Test execution timeline
- Screenshots and videos (attached automatically)
- Console logs
- Network requests
- Trace files

View reports:
```bash
npm run test:e2e:report
```

Or open directly:
```bash
open playwright/reports/html/index.html
```

### Video Recording

Videos are automatically recorded for failed tests and saved to `playwright/test-results/`.

Configuration in `playwright.config.ts`:
- `video: 'retain-on-failure'` - Keep videos only for failed tests
- Videos are automatically attached to HTML reports

### Screenshot Capture

Screenshots are automatically captured on test failure and saved to `playwright/test-results/`.

Configuration in `playwright.config.ts`:
- `screenshot: 'only-on-failure'` - Take screenshots only when tests fail
- Screenshots are automatically attached to HTML reports

### Notifications

#### Slack Notifications

Configure Slack webhook URL in GitHub Secrets:
- `SLACK_WEBHOOK_URL`: Your Slack webhook URL

Notifications are sent automatically on:
- Push to main/develop branches
- Manual workflow dispatch

#### Email Notifications

Configure SMTP settings in GitHub Secrets:
- `EMAIL_TO`: Recipient email address(es)
- `SMTP_HOST`: SMTP server hostname
- `SMTP_PORT`: SMTP server port (default: 587)
- `SMTP_USER`: SMTP username
- `SMTP_PASSWORD`: SMTP password

### Test Dashboard

Generate an HTML dashboard:
```bash
npm run test:e2e:dashboard
```

The dashboard includes:
- Overall test statistics
- Per-browser results
- Success rate visualization
- Test history (if enabled)

### Result Aggregation

Test results are automatically aggregated across:
- Multiple browsers (Chromium, Firefox, WebKit)
- Multiple projects
- Multiple test runs

Aggregated results are:
- Uploaded as artifacts
- Commented on PRs
- Included in notifications

## CI/CD Integration

### GitHub Actions

The `playwright-e2e.yml` workflow automatically:
1. Runs tests on multiple browsers
2. Generates HTML, JUnit, and JSON reports
3. Uploads videos, screenshots, and traces on failure
4. Aggregates results across browsers
5. Comments on PRs with test results
6. Sends notifications (if configured)

### Artifacts

The following artifacts are uploaded:
- `playwright-html-report-{browser}`: HTML reports (30 days retention)
- `playwright-junit-report-{browser}`: JUnit XML reports (30 days retention)
- `playwright-json-report-{browser}`: JSON reports (30 days retention)
- `playwright-videos-{browser}`: Test videos (7 days retention, failures only)
- `playwright-screenshots-{browser}`: Test screenshots (7 days retention, failures only)
- `playwright-traces-{browser}`: Test traces (7 days retention, failures only)
- `playwright-aggregated-results`: Aggregated summary (90 days retention)

## Usage

### Programmatic Access

```typescript
import {
  parseHTMLReport,
  parseJUnitReport,
  generateTestSummary,
  aggregateTestResults,
  sendSlackNotification,
  sendEmailNotification,
} from './playwright/utils/test-reporting'

// Parse HTML report
const summary = parseHTMLReport('./playwright/reports/html')

// Parse JUnit report
const junitSummary = parseJUnitReport('./playwright/reports/junit.xml')

// Generate summary
const markdown = generateTestSummary([summary, junitSummary])

// Aggregate results
const aggregated = aggregateTestResults([
  { type: 'html', path: './playwright/reports/html', browser: 'chromium' },
  { type: 'junit', path: './playwright/reports/junit.xml', browser: 'firefox' },
])

// Send notifications
await sendSlackNotification(aggregated, {
  webhookUrl: process.env.SLACK_WEBHOOK_URL!,
})

await sendEmailNotification(aggregated, {
  to: 'team@example.com',
  from: 'tests@example.com',
})
```

### Dashboard Generation

```typescript
import { generateTestDashboard, saveDashboard } from './playwright/utils/test-dashboard'

const summaries = [
  {
    browser: 'chromium',
    total: 100,
    passed: 95,
    failed: 5,
    skipped: 0,
    duration: 120000,
    timestamp: new Date().toISOString(),
  },
]

const html = generateTestDashboard(summaries, {
  title: 'Playwright Test Dashboard',
  includeCharts: true,
})

saveDashboard(html, './playwright/reports/dashboard.html')
```

## Best Practices

1. **Review HTML Reports**: Always review HTML reports for failed tests to see screenshots, videos, and traces
2. **Check Artifacts**: Download and review videos/screenshots for failed tests in CI/CD
3. **Monitor Notifications**: Set up Slack/Email notifications to stay informed about test results
4. **Use Dashboard**: Generate dashboard for visualizing test trends over time
5. **Aggregate Results**: Use aggregation to get overall test health across all browsers

## Troubleshooting

### Reports Not Generated

- Check that tests ran successfully
- Verify `playwright/reports/` directory exists
- Check Playwright configuration for reporter settings

### Videos/Screenshots Missing

- Verify `video: 'retain-on-failure'` in config
- Verify `screenshot: 'only-on-failure'` in config
- Check that tests actually failed (videos/screenshots only on failure)

### Notifications Not Sending

- Verify webhook URL/credentials are set in GitHub Secrets
- Check workflow logs for notification errors
- Ensure notification job runs (only on push/workflow_dispatch)

### Dashboard Not Generating

- Ensure test summaries are available
- Check that output directory is writable
- Verify dashboard utility is imported correctly

