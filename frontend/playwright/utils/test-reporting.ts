/**
 * Test Reporting Utilities
 *
 * Comprehensive utilities for test result reporting, notifications, and aggregation.
 * Supports HTML reports, video recording, screenshot capture, and notifications.
 */

import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'fs'
import { join } from 'path'

/**
 * Test result summary interface
 */
export interface TestResultSummary {
  total: number
  passed: number
  failed: number
  skipped: number
  duration: number
  timestamp: string
  browser?: string
  project?: string
}

/**
 * Parse Playwright HTML report index
 */
export function parseHTMLReport(reportPath: string): TestResultSummary | null {
  try {
    const indexPath = join(reportPath, 'index.html')
    if (!existsSync(indexPath)) {
      return null
    }

    // Read and parse HTML report
    const html = readFileSync(indexPath, 'utf-8')

    // Extract test statistics from HTML
    const totalMatch = html.match(/Total:\s*(\d+)/i)
    const passedMatch = html.match(/Passed:\s*(\d+)/i)
    const failedMatch = html.match(/Failed:\s*(\d+)/i)
    const skippedMatch = html.match(/Skipped:\s*(\d+)/i)
    const durationMatch = html.match(/Duration:\s*([\d.]+)/i)

    return {
      total: totalMatch ? parseInt(totalMatch[1], 10) : 0,
      passed: passedMatch ? parseInt(passedMatch[1], 10) : 0,
      failed: failedMatch ? parseInt(failedMatch[1], 10) : 0,
      skipped: skippedMatch ? parseInt(skippedMatch[1], 10) : 0,
      duration: durationMatch ? parseFloat(durationMatch[1]) : 0,
      timestamp: new Date().toISOString(),
    }
  } catch (error) {
    console.error('Error parsing HTML report:', error)
    return null
  }
}

/**
 * Parse JUnit XML report
 */
export function parseJUnitReport(xmlPath: string): TestResultSummary | null {
  try {
    if (!existsSync(xmlPath)) {
      return null
    }

    const xml = readFileSync(xmlPath, 'utf-8')

    // Extract test statistics from JUnit XML
    const testsMatch = xml.match(/tests="(\d+)"/)
    const failuresMatch = xml.match(/failures="(\d+)"/)
    const errorsMatch = xml.match(/errors="(\d+)"/)
    const skippedMatch = xml.match(/skipped="(\d+)"/)
    const timeMatch = xml.match(/time="([\d.]+)"/)

    const total = testsMatch ? parseInt(testsMatch[1], 10) : 0
    const failures = failuresMatch ? parseInt(failuresMatch[1], 10) : 0
    const errors = errorsMatch ? parseInt(errorsMatch[1], 10) : 0
    const skipped = skippedMatch ? parseInt(skippedMatch[1], 10) : 0

    return {
      total,
      passed: total - failures - errors - skipped,
      failed: failures + errors,
      skipped,
      duration: timeMatch ? parseFloat(timeMatch[1]) : 0,
      timestamp: new Date().toISOString(),
    }
  } catch (error) {
    console.error('Error parsing JUnit report:', error)
    return null
  }
}

/**
 * Generate test result summary markdown
 */
export function generateTestSummary(
  summaries: TestResultSummary[],
  options: {
    title?: string
    includeBrowser?: boolean
    includeProject?: boolean
  } = {}
): string {
  const { title = 'Test Results Summary', includeBrowser = true, includeProject = true } = options

  const totalTests = summaries.reduce((sum, s) => sum + s.total, 0)
  const totalPassed = summaries.reduce((sum, s) => sum + s.passed, 0)
  const totalFailed = summaries.reduce((sum, s) => sum + s.failed, 0)
  const totalSkipped = summaries.reduce((sum, s) => sum + s.skipped, 0)
  const totalDuration = summaries.reduce((sum, s) => sum + s.duration, 0)
  const successRate = totalTests > 0 ? ((totalPassed / totalTests) * 100).toFixed(2) : '0.00'

  let markdown = `# ${title}\n\n`
  markdown += `**Generated**: ${new Date().toISOString()}\n\n`
  markdown += `## Overall Statistics\n\n`
  markdown += `- **Total Tests**: ${totalTests}\n`
  markdown += `- **Passed**: ${totalPassed}\n`
  markdown += `- **Failed**: ${totalFailed}\n`
  markdown += `- **Skipped**: ${totalSkipped}\n`
  markdown += `- **Success Rate**: ${successRate}%\n`
  markdown += `- **Total Duration**: ${totalDuration.toFixed(2)}s\n\n`

  if (summaries.length > 1) {
    markdown += `## Per Browser/Project\n\n`
    markdown += `| Browser/Project | Total | Passed | Failed | Skipped | Duration |\n`
    markdown += `|----------------|-------|--------|--------|---------|----------|\n`

    summaries.forEach((summary) => {
      const identifier = includeBrowser && summary.browser
        ? summary.browser
        : includeProject && summary.project
        ? summary.project
        : 'Unknown'
      markdown += `| ${identifier} | ${summary.total} | ${summary.passed} | ${summary.failed} | ${summary.skipped} | ${summary.duration.toFixed(2)}s |\n`
    })
    markdown += `\n`
  }

  markdown += `## Status\n\n`
  if (totalFailed === 0) {
    markdown += `✅ All tests passed\n`
  } else {
    markdown += `❌ ${totalFailed} test(s) failed\n`
  }

  return markdown
}

/**
 * Send Slack notification
 */
export async function sendSlackNotification(
  summary: TestResultSummary | TestResultSummary[],
  options: {
    webhookUrl: string
    channel?: string
    username?: string
    iconEmoji?: string
  }
): Promise<void> {
  const { webhookUrl, channel, username = 'Playwright Tests', iconEmoji = ':robot_face:' } = options

  const summaries = Array.isArray(summary) ? summary : [summary]
  const overallSummary = summaries.reduce(
    (acc, s) => ({
      total: acc.total + s.total,
      passed: acc.passed + s.passed,
      failed: acc.failed + s.failed,
      skipped: acc.skipped + s.skipped,
      duration: acc.duration + s.duration,
    }),
    { total: 0, passed: 0, failed: 0, skipped: 0, duration: 0 }
  )

  const successRate = overallSummary.total > 0
    ? ((overallSummary.passed / overallSummary.total) * 100).toFixed(2)
    : '0.00'

  const color = overallSummary.failed === 0 ? 'good' : 'danger'
  const status = overallSummary.failed === 0 ? '✅ All tests passed' : `❌ ${overallSummary.failed} test(s) failed`

  const blocks = [
    {
      type: 'header',
      text: {
        type: 'plain_text',
        text: 'Playwright Test Results',
      },
    },
    {
      type: 'section',
      fields: [
        {
          type: 'mrkdwn',
          text: `*Total Tests:*\n${overallSummary.total}`,
        },
        {
          type: 'mrkdwn',
          text: `*Passed:*\n${overallSummary.passed}`,
        },
        {
          type: 'mrkdwn',
          text: `*Failed:*\n${overallSummary.failed}`,
        },
        {
          type: 'mrkdwn',
          text: `*Success Rate:*\n${successRate}%`,
        },
      ],
    },
    {
      type: 'section',
      text: {
        type: 'mrkdwn',
        text: `*Status:* ${status}\n*Duration:* ${overallSummary.duration.toFixed(2)}s`,
      },
    },
  ]

  const payload = {
    channel,
    username,
    icon_emoji: iconEmoji,
    attachments: [
      {
        color,
        blocks,
      },
    ],
  }

  try {
    const response = await fetch(webhookUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    })

    if (!response.ok) {
      throw new Error(`Slack API error: ${response.statusText}`)
    }
  } catch (error) {
    console.error('Error sending Slack notification:', error)
    throw error
  }
}

/**
 * Send email notification
 */
export async function sendEmailNotification(
  summary: TestResultSummary | TestResultSummary[],
  options: {
    to: string | string[]
    from: string
    subject?: string
    smtpHost?: string
    smtpPort?: number
    smtpUser?: string
    smtpPassword?: string
  }
): Promise<void> {
  const {
    to,
    from,
    subject = 'Playwright Test Results',
    smtpHost = process.env.SMTP_HOST || 'localhost',
    smtpPort = parseInt(process.env.SMTP_PORT || '587', 10),
    smtpUser = process.env.SMTP_USER,
    smtpPassword = process.env.SMTP_PASSWORD,
  } = options

  const summaries = Array.isArray(summary) ? summary : [summary]
  const markdown = generateTestSummary(summaries)

  // Convert markdown to HTML (simple conversion)
  const html = markdown
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>\n')
    .replace(/✅/g, '✅')
    .replace(/❌/g, '❌')

  const recipients = Array.isArray(to) ? to : [to]

  // Note: This is a simplified email sending function
  // In production, use a proper email library like nodemailer
  const emailPayload = {
    from,
    to: recipients.join(', '),
    subject,
    html,
    text: markdown,
  }

  console.log('Email notification payload:', emailPayload)
  console.warn('Email sending not implemented. Use nodemailer or similar library in production.')

  // In a real implementation, you would use nodemailer or similar:
  // const transporter = nodemailer.createTransport({
  //   host: smtpHost,
  //   port: smtpPort,
  //   auth: smtpUser && smtpPassword ? {
  //     user: smtpUser,
  //     pass: smtpPassword,
  //   } : undefined,
  // })
  // await transporter.sendMail(emailPayload)
}

/**
 * Aggregate test results from multiple sources
 */
export function aggregateTestResults(
  sources: Array<{ type: 'html' | 'junit'; path: string; browser?: string; project?: string }>
): TestResultSummary[] {
  const results: TestResultSummary[] = []

  for (const source of sources) {
    let summary: TestResultSummary | null = null

    if (source.type === 'html') {
      summary = parseHTMLReport(source.path)
    } else if (source.type === 'junit') {
      summary = parseJUnitReport(source.path)
    }

    if (summary) {
      summary.browser = source.browser
      summary.project = source.project
      results.push(summary)
    }
  }

  return results
}

/**
 * Save test summary to file
 */
export function saveTestSummary(summary: string, outputPath: string): void {
  try {
    const dir = join(outputPath, '..')
    if (!existsSync(dir)) {
      mkdirSync(dir, { recursive: true })
    }
    writeFileSync(outputPath, summary, 'utf-8')
    console.log(`Test summary saved to ${outputPath}`)
  } catch (error) {
    console.error('Error saving test summary:', error)
    throw error
  }
}

