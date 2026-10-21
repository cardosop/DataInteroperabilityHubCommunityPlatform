#!/bin/bash
# Normalize bare Python asserts in Django test files to self.assert*().
# Usage: ./scripts/normalize_test_asserts.sh <test_file.py>
#
# Applies transformations from most-specific to least-specific so
# that patterns like "assert resp.status_code == 200" are handled
# before the generic "assert x == y" catch-all.
#
# This script is idempotent — running it twice on the same file
# produces the same result (no double-wrapping).
set -euo pipefail

FILE="$1"

if [ ! -f "$FILE" ]; then
    echo "ERROR: file not found: $FILE" >&2
    exit 1
fi

echo "=== Normalizing asserts in: $FILE ==="

# ------------------------------------------------------------------
# Phase 1 — Exact pattern matches (most specific first)
# ------------------------------------------------------------------

# resp.status_code patterns (shorthand variable name)
sed -i \
  -e 's/assert resp\.status_code == 200/self.assertEqual(resp.status_code, status.HTTP_200_OK)/g' \
  -e 's/assert resp\.status_code == 201/self.assertEqual(resp.status_code, status.HTTP_201_CREATED)/g' \
  -e 's/assert resp\.status_code == 204/self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)/g' \
  -e 's/assert resp\.status_code == 400/self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)/g' \
  -e 's/assert resp\.status_code == 401/self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)/g' \
  -e 's/assert resp\.status_code == 403/self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)/g' \
  -e 's/assert resp\.status_code == 404/self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)/g' \
  -e 's/assert resp\.status_code == 409/self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)/g' \
  "$FILE"

# response.status_code patterns (long variable name)
sed -i \
  -e 's/assert response\.status_code == 200/self.assertEqual(response.status_code, status.HTTP_200_OK)/g' \
  -e 's/assert response\.status_code == 201/self.assertEqual(response.status_code, status.HTTP_201_CREATED)/g' \
  -e 's/assert response\.status_code == 204/self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)/g' \
  -e 's/assert response\.status_code == 400/self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)/g' \
  -e 's/assert response\.status_code == 401/self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)/g' \
  -e 's/assert response\.status_code == 403/self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)/g' \
  -e 's/assert response\.status_code == 404/self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)/g' \
  -e 's/assert response\.status_code == 409/self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)/g' \
  -e 's/assert response\.status_code == 422/self.assertEqual(response.status_code, 422)/g' \
  -e 's/assert response\.status_code == 500/self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)/g' \
  "$FILE"

# Boolean identity checks
sed -i \
  -e 's/assert \(.*\) is None$/self.assertIsNone(\1)/g' \
  -e 's/assert \(.*\) is not None$/self.assertIsNotNone(\1)/g' \
  -e 's/assert \(.*\) is True$/self.assertTrue(\1)/g' \
  -e 's/assert \(.*\) is False$/self.assertFalse(\1)/g' \
  "$FILE"

# assert not x (must come before equality-check patterns)
sed -i \
  -e 's/assert not \(.*\)$/self.assertFalse(\1)/g' \
  "$FILE"

# ------------------------------------------------------------------
# Phase 2 — Generic expression patterns
# ------------------------------------------------------------------

# Equality
sed -i \
  -e 's/assert \(.*\) == \(.*\)$/self.assertEqual(\1, \2)/g' \
  -e 's/assert \(.*\) != \(.*\)$/self.assertNotEqual(\1, \2)/g' \
  "$FILE"

# Containment
sed -i \
  -e 's/assert \(.*\) in \(.*\)$/self.assertIn(\1, \2)/g' \
  -e 's/assert \(.*\) not in \(.*\)$/self.assertNotIn(\1, \2)/g' \
  "$FILE"

# Comparisons
sed -i \
  -e 's/assert \(.*\) >= \(.*\)$/self.assertGreaterEqual(\1, \2)/g' \
  -e 's/assert \(.*\) <= \(.*\)$/self.assertLessEqual(\1, \2)/g' \
  -e 's/assert \(.*\) > \(.*\)$/self.assertGreater(\1, \2)/g' \
  -e 's/assert \(.*\) < \(.*\)$/self.assertLess(\1, \2)/g' \
  "$FILE"

# ------------------------------------------------------------------
# Phase 3 — Add missing imports
# ------------------------------------------------------------------

# Add "from rest_framework import status" if status codes are used
if grep -q 'status\.HTTP_' "$FILE" && ! grep -q 'from rest_framework import status' "$FILE"; then
    # Insert after the last existing import line
    LAST_IMPORT=$(grep -n '^from\|^import' "$FILE" | tail -1 | cut -d: -f1)
    if [ -n "$LAST_IMPORT" ]; then
        sed -i "${LAST_IMPORT}a from rest_framework import status" "$FILE"
    fi
fi

echo "Done."
