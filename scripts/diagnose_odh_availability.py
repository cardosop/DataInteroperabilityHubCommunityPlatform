#!/usr/bin/env python3
"""
One-off diagnostic: run inside api-service-test with same env as batch pytest to find
where _check_odh_inference_available() fails. Usage:
  docker compose -f docker-compose.test.yml exec -T api-service-test \\
    bash -c 'cd /app && PYTHONPATH=/app DJANGO_SETTINGS_MODULE=hub.settings python scripts/diagnose_odh_availability.py'
"""

import os
import sys


def step(name, fn):
    try:
        result = fn()
        print(f"[OK] {name}: {result}")
        return result
    except Exception as e:
        print(f"[FAIL] {name}: {type(e).__name__}: {e}", file=sys.stderr)
        raise


# 1) Env URL
url_env = os.environ.get("ODH_INFERENCE_SCHEDULER_URL")
print(f"1. ODH_INFERENCE_SCHEDULER_URL (env): {url_env!r}")

# 2) Django settings (requires Django setup)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hub.settings")
import django

django.setup()
from django.conf import settings

url_settings = getattr(settings, "ODH_INFERENCE_SCHEDULER_URL", None)
print(f"2. ODH_INFERENCE_SCHEDULER_URL (settings): {url_settings!r}")

base_url = url_env or url_settings
if not base_url:
    print("ABORT: no base_url (env and settings both empty/None)")
    sys.exit(1)

# 3) Health check
import urllib.request

health_url = base_url.rstrip("/") + "/health"
print(f"3. Health URL: {health_url}")
for attempt in range(3):
    try:
        req = urllib.request.Request(health_url, method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            status = getattr(resp, "status", 200)
            body = resp.read()[:200]
        print(f"   Attempt {attempt + 1}: status={status} body={body[:80]!r}")
        if status != 200:
            continue
        break
    except Exception as e:
        print(f"   Attempt {attempt + 1}: {type(e).__name__}: {e}")
else:
    print("ABORT: health check never returned 200")
    sys.exit(1)

# 4) Path resolution: repo root from this script (scripts/diagnose_odh_availability.py -> parent.parent)
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent
services_root = repo_root / "services"
inference_client_path = services_root / "odh-integration" / "inference_client.py"
print(
    f"4. repo_root={repo_root} inference_client_path={inference_client_path} exists={inference_client_path.exists()}"
)

if not inference_client_path.exists():
    print("ABORT: inference_client.py not found")
    sys.exit(1)

# 5) Load client module and instantiate
sys.path.insert(0, str(services_root))
sys.path.insert(0, str(repo_root))
import importlib.util

spec = importlib.util.spec_from_file_location("inference_client", str(inference_client_path))
if not spec or not spec.loader:
    print("ABORT: spec or spec.loader is None")
    sys.exit(1)
inference_client_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inference_client_module)
ODHInferenceClient = inference_client_module.ODHInferenceClient
print("5. Module loaded, instantiating ODHInferenceClient()...")
try:
    client = ODHInferenceClient()
    print(f"   [OK] client.base_url={getattr(client, 'base_url', '?')}")
except Exception as e:
    print(f"   [FAIL] {type(e).__name__}: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)

print("All steps OK. _check_odh_inference_available() would return (True, client).")
