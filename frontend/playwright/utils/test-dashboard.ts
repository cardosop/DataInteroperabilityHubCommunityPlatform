/**
 * Test Dashboard Generator
 *
 * Generates an HTML dashboard for viewing test results.
 * Optional feature for visualizing test metrics over time.
 */

import { readFileSync, writeFileSync, existsSync, mkdirSync, readdirSync } from 'fs'
import { join } from 'path'

/**
 * Dashboard configuration
 */
export interface DashboardConfig {
  title?: string
  outputPath?: string
  includeCharts?: boolean
  includeHistory?: boolean
  historyPath?: string
}

/**
 * Generate HTML dashboard from test results
 */
export function generateTestDashboard(
  summaries: Array<{
    browser?: string
    project?: string
    total: number
    passed: number
    failed: number
    skipped: number
    duration: number
    timestamp: string
  }>,
  config: DashboardConfig = {}
): string {
  const {
    title = 'Playwright Test Dashboard',
    includeCharts = true,
    includeHistory = false,
    historyPath,
  } = config

  const totalTests = summaries.reduce((sum, s) => sum + s.total, 0)
  const totalPassed = summaries.reduce((sum, s) => sum + s.passed, 0)
  const totalFailed = summaries.reduce((sum, s) => sum + s.failed, 0)
  const totalSkipped = summaries.reduce((sum, s) => sum + s.skipped, 0)
  const totalDuration = summaries.reduce((sum, s) => sum + s.duration, 0)
  const successRate = totalTests > 0 ? ((totalPassed / totalTests) * 100).toFixed(2) : '0.00'

  // Load history if available
  let historyData: any[] = []
  if (includeHistory && historyPath && existsSync(historyPath)) {
    try {
      const historyFiles = readdirSync(historyPath).filter((f) => f.endsWith('.json'))
      historyData = historyFiles.map((file) => {
        const content = readFileSync(join(historyPath, file), 'utf-8')
        return JSON.parse(content)
      })
    } catch (error) {
      console.error('Error loading history:', error)
    }
  }

  const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${title}</title>
  <style>
    * {
      margin: 0;
      padding: 0;
      box-sizing: border-box;
    }

    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
      background: #f5f5f5;
      color: #333;
      padding: 20px;
    }

    .container {
      max-width: 1200px;
      margin: 0 auto;
    }

    header {
      background: white;
      padding: 20px;
      border-radius: 8px;
      margin-bottom: 20px;
      box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }

    h1 {
      color: #2196F3;
      margin-bottom: 10px;
    }

    .stats-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 20px;
      margin-bottom: 20px;
    }

    .stat-card {
      background: white;
      padding: 20px;
      border-radius: 8px;
      box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }

    .stat-card h3 {
      font-size: 14px;
      color: #666;
      margin-bottom: 10px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }

    .stat-card .value {
      font-size: 32px;
      font-weight: bold;
      color: #2196F3;
    }

    .stat-card.passed .value {
      color: #4CAF50;
    }

    .stat-card.failed .value {
      color: #F44336;
    }

    .stat-card.skipped .value {
      color: #FF9800;
    }

    .browser-table {
      background: white;
      padding: 20px;
      border-radius: 8px;
      box-shadow: 0 2px 4px rgba(0,0,0,0.1);
      margin-bottom: 20px;
    }

    table {
      width: 100%;
      border-collapse: collapse;
    }

    th, td {
      padding: 12px;
      text-align: left;
      border-bottom: 1px solid #eee;
    }

    th {
      background: #f9f9f9;
      font-weight: 600;
      color: #666;
    }

    tr:hover {
      background: #f9f9f9;
    }

    .status-badge {
      display: inline-block;
      padding: 4px 8px;
      border-radius: 4px;
      font-size: 12px;
      font-weight: 600;
    }

    .status-badge.passed {
      background: #E8F5E9;
      color: #4CAF50;
    }

    .status-badge.failed {
      background: #FFEBEE;
      color: #F44336;
    }

    .status-badge.partial {
      background: #FFF3E0;
      color: #FF9800;
    }

    .chart-container {
      background: white;
      padding: 20px;
      border-radius: 8px;
      box-shadow: 0 2px 4px rgba(0,0,0,0.1);
      margin-bottom: 20px;
    }

    .progress-bar {
      width: 100%;
      height: 30px;
      background: #E0E0E0;
      border-radius: 15px;
      overflow: hidden;
      margin-top: 10px;
    }

    .progress-fill {
      height: 100%;
      background: linear-gradient(90deg, #4CAF50, #8BC34A);
      transition: width 0.3s ease;
      display: flex;
      align-items: center;
      justify-content: center;
      color: white;
      font-weight: 600;
      font-size: 14px;
    }

    footer {
      text-align: center;
      color: #666;
      margin-top: 40px;
      padding: 20px;
    }
  </style>
  ${includeCharts ? '<script src="https://cdn.jsdelivr.net/npm/chart.js@3.9.1/dist/chart.min.js"></script>' : ''}
</head>
<body>
  <div class="container">
    <header>
      <h1>${title}</h1>
      <p>Generated: ${new Date().toISOString()}</p>
    </header>

    <div class="stats-grid">
      <div class="stat-card">
        <h3>Total Tests</h3>
        <div class="value">${totalTests}</div>
      </div>
      <div class="stat-card passed">
        <h3>Passed</h3>
        <div class="value">${totalPassed}</div>
      </div>
      <div class="stat-card failed">
        <h3>Failed</h3>
        <div class="value">${totalFailed}</div>
      </div>
      <div class="stat-card skipped">
        <h3>Skipped</h3>
        <div class="value">${totalSkipped}</div>
      </div>
      <div class="stat-card">
        <h3>Success Rate</h3>
        <div class="value">${successRate}%</div>
        <div class="progress-bar">
          <div class="progress-fill" style="width: ${successRate}%">${successRate}%</div>
        </div>
      </div>
      <div class="stat-card">
        <h3>Duration</h3>
        <div class="value">${(totalDuration / 1000).toFixed(2)}s</div>
      </div>
    </div>

    <div class="browser-table">
      <h2>Per Browser Results</h2>
      <table>
        <thead>
          <tr>
            <th>Browser</th>
            <th>Total</th>
            <th>Passed</th>
            <th>Failed</th>
            <th>Skipped</th>
            <th>Success Rate</th>
            <th>Duration</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          ${summaries
            .map(
              (s) => `
          <tr>
            <td><strong>${s.browser || s.project || 'Unknown'}</strong></td>
            <td>${s.total}</td>
            <td>${s.passed}</td>
            <td>${s.failed}</td>
            <td>${s.skipped}</td>
            <td>${s.total > 0 ? ((s.passed / s.total) * 100).toFixed(2) : '0.00'}%</td>
            <td>${(s.duration / 1000).toFixed(2)}s</td>
            <td>
              <span class="status-badge ${
                s.failed === 0 ? 'passed' : s.passed > 0 ? 'partial' : 'failed'
              }">
                ${s.failed === 0 ? '✅ Passed' : s.passed > 0 ? '⚠️ Partial' : '❌ Failed'}
              </span>
            </td>
          </tr>
          `
            )
            .join('')}
        </tbody>
      </table>
    </div>

    ${includeCharts && historyData.length > 0 ? `
    <div class="chart-container">
      <h2>Test History</h2>
      <canvas id="historyChart" width="400" height="200"></canvas>
      <script>
        const ctx = document.getElementById('historyChart').getContext('2d');
        const historyData = ${JSON.stringify(historyData)};
        new Chart(ctx, {
          type: 'line',
          data: {
            labels: historyData.map(d => new Date(d.timestamp).toLocaleDateString()),
            datasets: [{
              label: 'Passed',
              data: historyData.map(d => d.passed),
              borderColor: '#4CAF50',
              backgroundColor: 'rgba(76, 175, 80, 0.1)',
            }, {
              label: 'Failed',
              data: historyData.map(d => d.failed),
              borderColor: '#F44336',
              backgroundColor: 'rgba(244, 67, 54, 0.1)',
            }]
          },
          options: {
            responsive: true,
            scales: {
              y: {
                beginAtZero: true
              }
            }
          }
        });
      </script>
    </div>
    ` : ''}

    <footer>
      <p>Playwright Test Dashboard - Generated automatically</p>
    </footer>
  </div>
</body>
</html>`

  return html
}

/**
 * Save dashboard to file
 */
export function saveDashboard(html: string, outputPath: string): void {
  try {
    const dir = join(outputPath, '..')
    if (!existsSync(dir)) {
      mkdirSync(dir, { recursive: true })
    }
    writeFileSync(outputPath, html, 'utf-8')
    console.log(`Dashboard saved to ${outputPath}`)
  } catch (error) {
    console.error('Error saving dashboard:', error)
    throw error
  }
}

