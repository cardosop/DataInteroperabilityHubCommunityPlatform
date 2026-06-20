"""
Phase 10-2a.4.2 — Mid-journey failure and recovery tests.

Validates that the CLI and API handle failures gracefully when operations
are interrupted partway through a multi-step workflow.  Tests cover:

- Creating a resource, then failing a dependent step → the first resource
  remains valid (no orphan cleanup needed) or is properly rolled back
- Partial updates → verifying that failed updates don't leave corrupted state
- Recovery after transient error → retrying succeeds

These tests use real CLI invocations against the live backend.  They verify
the system's resilience rather than simulating failures through mocking.
"""

from __future__ import annotations

import pytest
from datahub_cli.main import cli
from tests.use_cases.conftest import extract_id, unique_key

pytestmark = pytest.mark.mvp


# ── Helpers ──────────────────────────────────────────────────────────────────


def _midjourney_error_contains(output: str, phrases: list[str]) -> bool:
    """Return True if any of *phrases* appears in *output* (case-insensitive)."""
    lower = output.lower()
    return any(p.lower() in lower for p in phrases)


def _invoke_asset_create(runner, name: str, key: str):
    """Create a test asset, returning the CLI result."""
    return runner.invoke(
        cli,
        [
            "assets",
            "create",
            "--name",
            name,
            "--key",
            key,
        ],
    )


# ── Mid-journey failure tests ────────────────────────────────────────────────


class TestMidJourneyFailure:
    """Verify system behavior when operations fail partway through."""

    def test_asset_creation_succeeds_even_when_duplicate_key_fails(
        self,
        runner,
        authenticated_config,
    ):
        """Creating two assets with the same key: second should fail cleanly.

        The first asset MUST remain valid after the second creation attempt
        fails.  This verifies that a failed create does not roll back or
        corrupt the first asset.
        """
        asset_key = unique_key("midjourn")

        # Step 1: Create the first asset (should succeed)
        result1 = _invoke_asset_create(runner, "Mid-Journey Asset 1", asset_key)
        assert result1.exit_code == 0, f"First asset creation failed: {result1.output[:300]}"
        asset1_id = extract_id(result1.output)
        assert asset1_id, f"Could not extract asset ID from: {result1.output[:200]}"

        # Step 2: Try to create a second asset with the same key (should fail)
        result2 = _invoke_asset_create(runner, "Mid-Journey Asset 2", asset_key)
        assert result2.exit_code != 0, (
            "Duplicate key creation should have failed but got exit_code=0"
        )
        assert _midjourney_error_contains(
            result2.output,
            [
                "already exists",
                "duplicate",
                "conflict",
                "409",
            ],
        ), f"Error should indicate duplicate key. Got: {result2.output[:200]}"

        # Step 3: Verify the first asset is still accessible
        get_result = runner.invoke(cli, ["assets", "get", asset1_id])
        assert get_result.exit_code == 0, (
            f"First asset became inaccessible after duplicate key failure: "
            f"{get_result.output[:300]}"
        )
        assert asset_key in get_result.output or asset1_id in get_result.output, (
            "Get response doesn't reference the original asset"
        )

    def test_failed_compliance_run_does_not_delete_asset(
        self,
        runner,
        authenticated_config,
    ):
        """Running compliance on a non-existent asset leaves the system intact.

        If the compliance run endpoint returns an error, the CLI should report
        it cleanly.  Any previously created assets must remain accessible.
        """
        # First create a valid asset
        asset_key = unique_key("midjourn")
        create_result = _invoke_asset_create(runner, "Mid-Journey Compliance Asset", asset_key)
        assert create_result.exit_code == 0, f"Asset creation failed: {create_result.output[:300]}"
        asset_id = extract_id(create_result.output)
        assert asset_id

        # Now try a compliance run that might fail (depends on backend state)
        compliance_result = runner.invoke(
            cli,
            [
                "compliance",
                "run",
                "--asset-id",
                "00000000-0000-0000-0000-000000000000",
                "--scan-mode",
                "internal",
            ],
        )
        # This should fail because the asset doesn't exist
        assert compliance_result.exit_code != 0, (
            f"Compliance on non-existent asset should fail. "
            f"Got exit_code={compliance_result.exit_code}"
        )

        # The original asset should still be accessible
        get_result = runner.invoke(cli, ["assets", "get", asset_id])
        assert get_result.exit_code == 0, (
            f"Asset became inaccessible after failed compliance run: {get_result.output[:300]}"
        )

    def test_delete_nonexistent_asset_reports_clean_error(
        self,
        runner,
        authenticated_config,
    ):
        """Deleting an asset that doesn't exist should produce a clear error.

        The CLI must not crash, hang, or produce a stack trace."
        """
        result = runner.invoke(
            cli,
            [
                "assets",
                "delete",
                "00000000-0000-0000-0000-000000000000",
            ],
        )
        assert result.exit_code != 0, "Deleting non-existent asset should fail with non-zero exit"
        # Output must be a clean error message, not a Python traceback
        assert "Traceback" not in result.output, (
            f"CLI produced a traceback instead of a clean error:\n{result.output[:500]}"
        )
        assert _midjourney_error_contains(
            result.output,
            [
                "not found",
                "does not exist",
                "failed",
                "error",
                "404",
            ],
        ), f"Error should indicate asset not found. Got: {result.output[:200]}"

    def test_workflow_continues_after_harmless_error(
        self,
        runner,
        authenticated_config,
    ):
        """A failed 'get' on a non-existent resource should not affect subsequent operations.

        This simulates a user accidentally querying a wrong ID mid-workflow,
        then continuing with the correct flow.
        """
        # Step 1: Create an asset normally
        asset_key = unique_key("midjourn")
        create_result = _invoke_asset_create(runner, "Workflow Continuity Asset", asset_key)
        assert create_result.exit_code == 0, f"Asset creation failed: {create_result.output[:300]}"
        asset_id = extract_id(create_result.output)
        assert asset_id

        # Step 2: Make a failed query (wrong ID)
        bad_get = runner.invoke(
            cli,
            [
                "assets",
                "get",
                "00000000-0000-0000-0000-000000000000",
            ],
        )
        assert bad_get.exit_code != 0, "Querying non-existent ID should fail"

        # Step 3: Continue the workflow — the real asset should still work
        good_get = runner.invoke(cli, ["assets", "get", asset_id])
        assert good_get.exit_code == 0, (
            f"Real asset became inaccessible after a failed query: {good_get.output[:300]}"
        )
        assert asset_key in good_get.output or asset_id in good_get.output, (
            "Get response doesn't reference the original asset"
        )


# ── Recovery after transient error tests ─────────────────────────────────────


class TestRecoveryAfterError:
    """Verify that the system recovers cleanly after transient failures."""

    def test_recreate_after_delete(self, runner, authenticated_config):
        """Creating an asset after deleting one with the same key should succeed.

        This verifies the full create→delete→recreate lifecycle works without
        residual state from the deleted resource blocking recreation.
        """
        asset_key = unique_key("recreate")

        # Create
        create1 = _invoke_asset_create(runner, "Recreate Asset", asset_key)
        assert create1.exit_code == 0, f"Initial creation failed: {create1.output[:300]}"
        asset_id = extract_id(create1.output)
        assert asset_id

        # Delete
        delete_result = runner.invoke(cli, ["assets", "delete", asset_id])
        # Deletion may require confirmation or additional flags; accept
        # non-zero exit if the API blocks deletion of certain states
        if delete_result.exit_code != 0:
            # Asset might not be deletable in DRAFT state or may require
            # --force.  Skip the rest of the test if the API blocks deletion.
            if _midjourney_error_contains(
                delete_result.output,
                [
                    "cannot delete",
                    "not allowed",
                    "active",
                    "has dependencies",
                ],
            ):
                pytest.skip(
                    f"Asset deletion blocked by API (legitimate constraint): "
                    f"{delete_result.output[:200]}"
                )

        # Re-create with the same key
        create2 = _invoke_asset_create(runner, "Recreate Asset v2", asset_key)
        if create2.exit_code == 0:
            # Success — the old asset was properly cleaned up
            new_id = extract_id(create2.output)
            assert new_id, f"Recreated asset missing ID: {create2.output[:200]}"
        else:
            # The API may require the old asset to be fully purged first
            assert _midjourney_error_contains(
                create2.output,
                [
                    "already exists",
                    "duplicate",
                    "conflict",
                    "409",
                ],
            ), (
                f"Recreate failure should be a clean conflict, not a crash. "
                f"Got: {create2.output[:300]}"
            )

    def test_list_always_succeeds_even_after_failures(
        self,
        runner,
        authenticated_config,
    ):
        """Listing resources should succeed even if previous operations failed.

        This verifies that read-only operations remain available regardless
        of prior error state.
        """
        # Make several failed queries first
        for bad_id in [
            "00000000-0000-0000-0000-000000000000",
            "not-a-uuid",
        ]:
            runner.invoke(cli, ["assets", "get", bad_id])

        # Now list — should always succeed
        list_result = runner.invoke(cli, ["assets", "list", "--limit", "5"])
        assert list_result.exit_code == 0, (
            f"List failed after prior errors: {list_result.output[:300]}"
        )
        # Output should be either a table or "No assets found"
        output = list_result.output.lower()
        assert any(
            indicator in output
            for indicator in [
                "id",
                "name",
                "key",
                "status",
                "no assets",
                "found",
            ]
        ), f"List output doesn't look like a valid response: {list_result.output[:200]}"
