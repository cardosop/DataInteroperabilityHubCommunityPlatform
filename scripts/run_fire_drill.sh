#!/bin/bash
# 285.12.6.3 4C — Quarterly fire drill: chaos smoke test
set -euo pipefail
echo "=== Meshant Fire Drill — $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
echo ""
echo "1. Verifying API health..."
curl -sf http://localhost:8000/api/health/ > /dev/null && echo "   ✅ API healthy" || echo "   ❌ API down"
echo ""
echo "2. Verifying database connectivity..."
python3 -c "
import os, sys
sys.path.insert(0, '.')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hub.settings')
import django; django.setup()
from django.db import connection
connection.ensure_connection()
print('   ✅ Database connected')
" 2>/dev/null || echo "   ❌ Database unreachable"
echo ""
echo "3. Verifying Redis connectivity..."
python3 -c "
from django.core.cache import cache
cache.set('fire_drill_test', 'ok', 10)
assert cache.get('fire_drill_test') == 'ok'
print('   ✅ Redis connected')
" 2>/dev/null || echo "   ❌ Redis unreachable"
echo ""
echo "Fire drill complete. Run quarterly per docs/SLO.md."
