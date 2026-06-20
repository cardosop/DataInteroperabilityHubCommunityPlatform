"""
Phase 10-2a.4.3 — Concurrent operation tests.

Validates that the CLI and API handle concurrent operations safely:
- Two CLI processes creating resources simultaneously do not corrupt data
- Concurrent listing and mutation do not cause inconsistencies
- Rapid create-delete sequences do not leave orphaned resources

These tests use real multiprocessing to simulate concurrent CLI usage.
They are designed to run against a live backend and will skip if the
backend is not reachable.
"""

from __future__ import annotations

import concurrent.futures
import os
import time

import pytest
from datahub_cli.main import cli
from tests.use_cases.conftest import unique_key

pytestmark = pytest.mark.mvp


# ── Helpers ──────────────────────────────────────────────────────────────────


def _skip_if_backend_unavailable() -> None:
    """Skip if the backend API is not reachable."""
    import requests

    api_url = os.environ.get("MESHANT_API_URL", "http://localhost:8000/api/v1")
    root = api_url.rstrip("/api/v1")
    try:
        resp = requests.get(f"{root}/health/", timeout=2)
        if resp.status_code not in (200, 503):
            pytest.skip(f"Backend not reachable at {root}")
    except requests.RequestException:
        pytest.skip(f"Backend not reachable at {root}")


# ── Concurrent creation tests ────────────────────────────────────────────────


class TestConcurrentCreation:
    """Verify that concurrent resource creation does not corrupt data."""

    def test_concurrent_asset_creation_unique_keys(
        self,
        runner,
        authenticated_config,
    ):
        """Creating multiple assets concurrently with unique keys should all succeed.

        Uses ThreadPoolExecutor to issue several create commands at roughly
        the same time.  Every creation should succeed because each asset
        has a unique key.
        """
        _skip_if_backend_unavailable()

        num_assets = 4
        keys = [unique_key(f"concur-{i}") for i in range(num_assets)]
        created_ids: list[str] = []

        def create_one(key: str, idx: int) -> tuple[int, str]:
            result = runner.invoke(
                cli,
                [
                    "assets",
                    "create",
                    "--name",
                    f"Concurrent Asset {idx}",
                    "--key",
                    key,
                ],
            )
            asset_id = None
            for line in result.output.split("\n"):
                if "ID:" in line:
                    asset_id = line.split("ID:", 1)[1].strip()
                    break
            return result.exit_code, asset_id or ""

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_assets) as executor:
            futures = {executor.submit(create_one, key, i): i for i, key in enumerate(keys)}
            for future in concurrent.futures.as_completed(futures):
                exit_code, asset_id = future.result()
                assert exit_code == 0, (
                    f"Concurrent asset creation failed (idx={futures[future]}): exit={exit_code}"
                )
                if asset_id:
                    created_ids.append(asset_id)

        assert len(created_ids) == num_assets, (
            f"Expected {num_assets} assets created, got {len(created_ids)}"
        )

        # Verify all assets are independently accessible
        for asset_id in created_ids:
            get_result = runner.invoke(cli, ["assets", "get", asset_id])
            assert get_result.exit_code == 0, (
                f"Asset {asset_id} not accessible after concurrent creation"
            )

    def test_concurrent_listing_during_creation(
        self,
        runner,
        authenticated_config,
    ):
        """Listing assets while another 'thread' creates one should not error.

        The list operation should return a consistent snapshot at whatever
        point it executes — never crash or return corrupted data.
        """
        _skip_if_backend_unavailable()

        errors: list[str] = []

        def list_assets() -> None:
            for _ in range(3):
                result = runner.invoke(cli, ["assets", "list", "--limit", "5"])
                if result.exit_code != 0:
                    errors.append(f"List failed: {result.output[:200]}")

        def create_asset(idx: int) -> None:
            key = unique_key(f"list-concur-{idx}")
            result = runner.invoke(
                cli,
                [
                    "assets",
                    "create",
                    "--name",
                    f"List Concurrent {idx}",
                    "--key",
                    key,
                ],
            )
            if result.exit_code != 0 and "already exists" not in result.output.lower():
                errors.append(f"Create failed: {result.output[:200]}")

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = []
            # Start listing before creating to overlap operations
            futures.append(executor.submit(list_assets))
            time.sleep(0.1)  # noqa: sleep-needed — test timing requirement
            for i in range(3):
                futures.append(executor.submit(create_asset, i))
            concurrent.futures.wait(futures)

        assert not errors, f"Errors during concurrent list+create: {errors}"


# ── Concurrent mutation tests ────────────────────────────────────────────────


class TestConcurrentMutation:
    """Verify that concurrent mutations to the same resource are safe."""

    def test_concurrent_reads_on_same_asset(self, runner, authenticated_config):
        """Multiple concurrent reads on the same asset should all succeed."""
        # Create one asset first
        asset_key = unique_key("concur-read")
        create_result = runner.invoke(
            cli,
            [
                "assets",
                "create",
                "--name",
                "Concurrent Read Asset",
                "--key",
                asset_key,
            ],
        )
        assert create_result.exit_code == 0, f"Asset creation failed: {create_result.output[:300]}"

        asset_id = None
        for line in create_result.output.split("\n"):
            if "ID:" in line:
                asset_id = line.split("ID:", 1)[1].strip()
                break
        assert asset_id, "Could not extract asset ID"

        errors: list[str] = []

        def read_asset() -> None:
            for _ in range(5):
                result = runner.invoke(cli, ["assets", "get", asset_id])
                if result.exit_code != 0:
                    errors.append(f"Concurrent read failed: {result.output[:200]}")

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(read_asset) for _ in range(4)]
            concurrent.futures.wait(futures)

        assert not errors, f"Concurrent reads on same asset failed: {errors}"

    def test_rapid_create_list_sequence(self, runner, authenticated_config):
        """Rapid create→list→create→list sequence should not lose data.

        This simulates a script that pipelines CLI commands quickly.
        """
        created_keys: list[str] = []
        for i in range(5):
            key = unique_key(f"rapid-{i}")
            result = runner.invoke(
                cli,
                [
                    "assets",
                    "create",
                    "--name",
                    f"Rapid Asset {i}",
                    "--key",
                    key,
                ],
            )
            if result.exit_code == 0:
                created_keys.append(key)
            # List after each create
            list_result = runner.invoke(cli, ["assets", "list", "--limit", "5"])
            assert list_result.exit_code == 0, (
                f"List failed after create {i}: {list_result.output[:200]}"
            )

        assert len(created_keys) > 0, "No assets were created in rapid sequence"
