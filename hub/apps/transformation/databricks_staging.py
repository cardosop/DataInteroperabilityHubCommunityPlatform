"""Phase 11 (openspec add-databricks-control-plane task 11.4) — dbt
artifact/seed staging through the workspace's managed UC volume
(design D4).

The stage rides the PINNED production client (the caller owns identity
— the client is constructed from the registered estate by the 11.2
target selection; never a second HTTP stack): the volume CRUD pins
(``uc.volumes.create`` / ``uc.volumes.delete``) + the volume's
file-write pin (``fs.files.upload`` — the additive 11.4 pin).

The create → use → remove contract: a failed stage removes the partial
volume BEST-EFFORT before the error surfaces — the workspace estate is
never polluted. The cleanup's own failure is swallowed (a leftover
volume is removable by the operator; a crashed run is never silent).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # core-guard: full-mode-only — TYPE_CHECKING-only import (no runtime coupling)
    from hub.apps.databricks_admin.client import DatabricksApiClient

import structlog

logger = structlog.get_logger(__name__)

# The UC volume path prefix the Databricks Files API addresses managed
# volumes under (the API's own convention).
_FS_VOLUMES_PREFIX = "Volumes"


class DbtStagingError(Exception):
    """A stage that failed — the volume was removed best-effort before
    this raised (the estate is never polluted)."""

    def __init__(self, phase: str, detail: str):
        self.phase = phase
        super().__init__(f"dbt staging failed at {phase}: {detail}")


def _split_volume_full_name(volume_full_name: str) -> tuple[str, str, str]:
    """``catalog.schema.volume`` → the three UC identifiers (validated
    fail-closed — a malformed name refuses before any network call)."""
    parts = volume_full_name.split(".")
    if len(parts) != 3 or any(not part for part in parts):
        raise DbtStagingError(
            "parse", f"volume full name {volume_full_name!r} is not catalog.schema.volume"
        )
    return parts[0], parts[1], parts[2]


def _volume_path(volume_full_name: str, relative_path: str) -> str:
    """The Files-API object path for a file inside the volume."""
    return f"{_FS_VOLUMES_PREFIX}/{volume_full_name}/{relative_path.lstrip('/')}"


def stage_dbt_seeds(
    client: DatabricksApiClient,
    *,
    volume_full_name: str,
    files: dict[str, bytes],
) -> list[str]:
    """Create the managed volume and upload the seed/artifact files.

    Returns the volume-relative staged paths (one per uploaded file).
    A failure at ANY phase removes the volume best-effort (a
    not-yet-created volume's cleanup is a no-op) and raises
    ``DbtStagingError`` — the create → use → remove contract.
    """
    catalog, schema, volume = _split_volume_full_name(volume_full_name)
    # Gate-first: every file validates BEFORE the first network call.
    if not files:
        raise DbtStagingError("validate", "no files to stage")
    for relative_path, content in files.items():
        if not isinstance(content, bytes):
            raise DbtStagingError("validate", f"{relative_path!r} content is not bytes")

    try:
        client.request(
            "POST",
            "uc.volumes.create",
            json={
                "name": volume,
                "catalog_name": catalog,
                "schema_name": schema,
                "volume_type": "MANAGED",
            },
        )
    except Exception as exc:
        raise DbtStagingError("create", str(exc)) from exc

    staged: list[str] = []
    try:
        for relative_path, content in files.items():
            client.request(
                "PUT",
                "fs.files.upload",
                path_params={"path": _volume_path(volume_full_name, relative_path)},
                content=content,
            )
            # The consumer-facing volume path (dbt seed paths) is the
            # slash-separated form; the Files API wire path (above) is
            # the dot-joined full name — the API's own convention.
            staged.append(f"/Volumes/{catalog}/{schema}/{volume}/{relative_path.lstrip('/')}")
    except Exception as exc:
        remove_staged_volume(client, volume_full_name=volume_full_name)
        raise DbtStagingError("upload", str(exc)) from exc

    logger.info(
        "dbt_stage_completed",
        volume=volume_full_name,
        staged_count=len(staged),
    )
    return staged


def remove_staged_volume(
    client: DatabricksApiClient,
    *,
    volume_full_name: str,
) -> None:
    """Remove the staged volume — best-effort: a 404 (the volume
    already gone) is a CLEAN estate, and any other failure is logged,
    never raised (the run's own failure carries the meaning)."""
    _split_volume_full_name(volume_full_name)
    try:
        client.request(
            "DELETE",
            "uc.volumes.delete",
            path_params={"full_name": volume_full_name},
        )
    except Exception as exc:
        logger.warning(
            "dbt_stage_cleanup_failed",
            volume=volume_full_name,
            error=str(exc),
        )
