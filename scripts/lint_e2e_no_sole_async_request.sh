#!/usr/bin/env bash
# TR.B.12 — CI lint rule: E2E spec files SHALL NOT use `async ({ request })`
# as the sole interaction pattern (blocking).
set -euo pipefail

E2E_DIR="${1:-frontend/e2e}"

# Find E2E specs that use `async ({ request })` as the only interaction pattern
# (i.e., no `page.` calls for browser interaction)
VIOLATIONS=$(grep -rl "async ({ request })" "$E2E_DIR" --include="*.ts" 2>/dev/null | while read f; do
  # Check if file also has browser interactions (page.goto, page.click, etc.)
  if ! grep -q "page\.\(goto\|click\|fill\|locator\|waitFor\|selectOption\|check\|uncheck\)" "$f"; then
    echo "  $f"
  fi
done)

if [ -n "$VIOLATIONS" ]; then
  echo "TR.B.12: The following E2E specs use async ({ request }) as sole interaction pattern:"
  echo "$VIOLATIONS"
  echo "These MUST be relocated to backend integration tests or add browser interactions."
  exit 1
fi

echo "TR.B.12: All E2E specs use browser interactions. ✅"
exit 0
