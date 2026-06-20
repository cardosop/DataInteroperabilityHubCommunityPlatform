"""Shared ODCS test helpers — avoids duplication between ODCS test files."""

import json
import time as _time
import uuid
import warnings
from typing import Optional


def create_odcs_contract_via_api(api_base_url: str, api_key: str) -> Optional[str]:
    """
    Create an ODCS contract via the API for testing.

    Retries once on timeout (the API can be slow under concurrent test load).

    Args:
        api_base_url: API base URL (e.g. ``http://localhost:8001/api/v1``)
        api_key: API key or JWT access token for authentication

    Returns:
        Contract ID (UUID) if successful, ``None`` otherwise.
    """
    import requests

    last_exc = None
    for attempt in range(2):
        try:
            odcs_content = json.dumps(
                {
                    "apiVersion": "odcs.io/v3.0.2",
                    "kind": "DataContract",
                    "id": f"test-odcs-contract-{uuid.uuid4().hex[:8]}",
                    "name": "Test ODCS Contract for SDK Export Tests",
                    "version": "1.0.0",
                    "schema": {
                        "fields": [
                            {"name": "id", "type": "string", "nullable": False},
                            {"name": "name", "type": "string", "nullable": False},
                        ]
                    },
                }
            )

            contract_data = {
                "original_raw": odcs_content,
                "original_format": "JSON",
                "original_spec_type": "ODCS",
            }

            # Auto-detect auth header: JWT tokens (contain dots) use Bearer,
            # plain API keys use ApiKey — matches DataHubClient._get_headers().
            auth_value = f"Bearer {api_key}" if "." in api_key else f"ApiKey {api_key}"
            response = requests.post(
                f"{api_base_url}/contracts/",
                json=contract_data,
                headers={
                    "Authorization": auth_value,
                    "Content-Type": "application/json",
                },
                timeout=30,
            )

            if response.status_code in [200, 201]:
                result = response.json()
                return result.get("id") or result.get("contract_id")

            # Non-success status — log and return None (no retry for 4xx/5xx)
            try:
                error_data = response.json()
                print(f"Contract creation failed: {error_data}")
            except (ValueError, AttributeError):
                print(
                    f"Contract creation failed with status {response.status_code}: {response.text}"
                )
            return None

        except (ConnectionError, TimeoutError, OSError, ValueError) as exc:
            last_exc = exc
            if attempt < 1:  # retry once after 5s backoff
                _time.sleep(5)
                continue
        break  # exhausted retries — fall through to warning

    warnings.warn(f"Exception creating contract after retries: {last_exc!r}")
    return None


def delete_odcs_contract(api_base_url: str, api_key: str, contract_id: str) -> None:
    """Best-effort cleanup: delete an ODCS contract.  Ignores network errors."""
    import requests

    try:
        auth_value = f"Bearer {api_key}" if "." in api_key else f"ApiKey {api_key}"
        requests.delete(
            f"{api_base_url}/contracts/{contract_id}/",
            headers={"Authorization": auth_value},
            timeout=5,
        )
    except requests.RequestException:
        pass  # cleanup best-effort
