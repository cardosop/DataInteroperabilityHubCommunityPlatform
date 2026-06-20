"""
285.9.1.2 — DbtExecutor: wraps dbt Core CLI for transformation pipelines.

Integrates with credential_resolver (Step 1.1) for warehouse and git
credentials.  Manages temp profiles.yml on tmpfs, executes dbt commands
via subprocess, and captures structured results + error logs.

Phased coverage:
  285.9.1.2.1 — DbtExecutor class (dbt_run, dbt_test, dbt_docs_generate, dbt_parse)
  285.9.1.2.2 — dbt profile resolution (tmpfs profiles.yml, DBT_PROFILES_DIR, cleanup)
  285.9.1.2.3 — dbt log capture (run_results.json parsing, dbt.log ERROR forwarding)
"""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
import subprocess
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

import structlog
import yaml

from .credential_resolver import resolve_warehouse_credentials
from .exceptions import TransformationExecutionError

logger = structlog.get_logger(__name__)

# Default location for tmpfs-backed work directories.
_DEFAULT_WORK_DIR_ROOT = "/tmp"


class DbtExecutor:
    """Execute dbt Core commands for a transformation pipeline run.

    Each instance is scoped to a single pipeline execution (one run_id).
    The work directory lives on tmpfs (``/tmp/meshant_dbt_{run_id}/``)
    so it survives crashes without disk writes and is auto-cleaned on
    next reboot.
    """

    def __init__(
        self,
        run_id: str,
        tenant_slug: str,
        pipeline_id: str,
        warehouse_credential_ref: str,
        git_credential_ref: str,
        work_dir_root: str = _DEFAULT_WORK_DIR_ROOT,
    ):
        self.run_id = self._sanitize_path_component(run_id)
        self.tenant_slug = self._sanitize_path_component(tenant_slug)
        self.pipeline_id = self._sanitize_path_component(pipeline_id)
        self.warehouse_credential_ref = warehouse_credential_ref
        self.git_credential_ref = git_credential_ref

        # Profile name per Step 1.2 convention.
        self.profile_name = f"meshant_{self.tenant_slug}_{self.pipeline_id}"

        # Work directory on tmpfs.
        self.work_dir = os.path.join(work_dir_root, f"meshant_dbt_{self.run_id}")

    # ── Public execution API (285.9.1.2.1) ────────────────────────────

    def dbt_run(
        self,
        project_path: str,
        models: list[str] | None = None,
        target: str = "prod",
    ) -> dict[str, Any]:
        """Run dbt models.

        Args:
            project_path: Path to the dbt project (with dbt_project.yml).
            models: Optional list of model names to select (--select).
            target: dbt target name (default ``prod``).

        Returns:
            Dict with ``results`` (per-model dicts), ``elapsed_total``,
            ``error_logs``, and ``span_attributes`` (Prefect-span-compatible).
        """
        return self._execute("run", project_path, models=models, target=target)

    def dbt_test(self, project_path: str, target: str = "prod") -> dict[str, Any]:
        """Run dbt tests on the project."""
        return self._execute("test", project_path, target=target)

    def dbt_docs_generate(self, project_path: str, target: str = "prod") -> dict[str, Any]:
        """Generate catalog.json and manifest.json."""
        return self._execute("docs-generate", project_path, target=target)

    def dbt_parse(self, project_path: str, target: str = "prod") -> dict[str, Any]:
        """Validate the dbt project without executing models."""
        return self._execute("parse", project_path, target=target)

    def dbt_deps(self, project_path: str, target: str = "prod") -> dict[str, Any]:
        """Install dbt packages (``dbt deps``). Call before dbt_run
        when the project has a ``packages.yml``."""
        return self._execute("deps", project_path, target=target)

    # ── Internal: execution pipeline ──────────────────────────────────

    def _execute(
        self,
        action: str,
        project_path: str,
        models: list[str] | None = None,
        target: str = "prod",
    ) -> dict[str, Any]:
        """Run a dbt command end-to-end with profile setup, execution,
        result parsing, and cleanup."""
        with self._profile_context():
            cmd = self._build_dbt_command(
                action, project_path=project_path, models=models, target=target
            )
            logger.info(
                "dbt_command_starting",
                action=action,
                run_id=self.run_id,
                project_path=project_path,
            )
            self._run_dbt_command(cmd, cwd=project_path)

        # Parse results from the project's target directory.
        run_results_path = os.path.join(project_path, "target", "run_results.json")
        dbt_log_path = os.path.join(project_path, "logs", "dbt.log")

        results = self._parse_run_results(run_results_path)
        elapsed_total = self._parse_elapsed_time(run_results_path)
        error_logs = self._capture_error_logs(dbt_log_path)
        span_attrs = self._build_span_attributes(results, elapsed_total)

        logger.info(
            "dbt_command_completed",
            action=action,
            run_id=self.run_id,
            models_run=len(results),
            models_success=sum(1 for r in results if r.get("status") == "success"),
            models_error=sum(1 for r in results if r.get("status") == "error"),
            elapsed_total=elapsed_total,
            error_log_lines=len(error_logs),
        )

        return {
            "results": results,
            "elapsed_total": elapsed_total,
            "error_logs": error_logs,
            "span_attributes": span_attrs,
        }

    # ── Profile resolution (285.9.1.2.2) ──────────────────────────────

    @contextmanager
    def _profile_context(self) -> Generator[None, None, None]:
        """Context manager that sets up profiles.yml, yields, and cleans up.

        Cleanup runs in a ``finally`` block so a crash / exception never
        leaves a stale profiles.yml on disk.
        """
        self._setup_profile()
        try:
            yield
        finally:
            self._cleanup_profile()

    def _setup_profile(self) -> None:
        """Resolve warehouse credentials and write profiles.yml to the
        tmpfs work directory.  Sets ``DBT_PROFILES_DIR`` so the dbt CLI
        discovers it."""
        profile = resolve_warehouse_credentials(
            self.warehouse_credential_ref,
            profile_name=self.profile_name,
        )

        os.makedirs(self.work_dir, exist_ok=True)
        profile_path = os.path.join(self.work_dir, "profiles.yml")
        with open(profile_path, "w") as f:
            yaml.dump(profile, f, default_flow_style=False, sort_keys=False)
        # Restrict to owner-only — credentials must not be world-readable.
        os.chmod(profile_path, stat.S_IRUSR | stat.S_IWUSR)

        os.environ["DBT_PROFILES_DIR"] = self.work_dir
        logger.debug(
            "dbt_profiles_yml_written",
            work_dir=self.work_dir,
            profile_name=self.profile_name,
        )

    def _cleanup_profile(self) -> None:
        """Remove the tmpfs work directory and unset DBT_PROFILES_DIR."""
        if os.environ.get("DBT_PROFILES_DIR") == self.work_dir:
            del os.environ["DBT_PROFILES_DIR"]

        try:
            if os.path.isdir(self.work_dir):
                shutil.rmtree(self.work_dir)
                logger.debug("dbt_work_dir_cleaned", work_dir=self.work_dir)
        except OSError as exc:
            # tmpfs — OSError is unlikely, but don't crash the pipeline
            # over a cleanup failure.
            logger.warning(
                "dbt_work_dir_cleanup_failed",
                work_dir=self.work_dir,
                error=str(exc),
            )

    # ── Git clone (285.9.1.2.4) ──────────────────────────────────────

    def _clone_dbt_project(self, repo_url: str, branch: str = "main") -> str:
        """Clone a dbt project from a git repository into the work
        directory and return the path to the project root (the directory
        containing ``dbt_project.yml``).

        Authentication uses the ``git_credential_ref`` resolved via
        ``credential_resolver`` (SSH key or HTTPS token).

        Raises:
            TransformationExecutionError: If the clone fails or no
                ``dbt_project.yml`` is found.
        """
        from .credential_resolver import resolve_git_credentials

        project_path = os.path.join(self.work_dir, "project")
        os.makedirs(project_path, exist_ok=True)

        try:
            import git as _git
        except ImportError:
            raise TransformationExecutionError(
                "GitPython is required for dbt project cloning. "
                "Install it with: pip install GitPython"
            )

        # Resolve git credentials (SSH key or HTTPS token).
        git_creds = None
        if self.git_credential_ref:
            try:
                git_creds = resolve_git_credentials(self.git_credential_ref)
            except Exception as exc:
                logger.warning(
                    "dbt_git_credential_resolution_failed",
                    git_credential_ref=self.git_credential_ref,
                    error=str(exc),
                )
                # Continue without credentials (public repo fallback).

        clone_kwargs: dict[str, Any] = {
            "depth": 1,
            "single_branch": True,
            "branch": branch,
        }

        if git_creds:
            if "ssh_key" in git_creds:
                clone_kwargs["env"] = {
                    "GIT_SSH_COMMAND": (
                        f"ssh -i {git_creds['ssh_key']} -o StrictHostKeyChecking=no"
                    ),
                }
            elif "username" in git_creds:
                # HTTPS with token — embed in URL
                from urllib.parse import urlparse, urlunparse

                parsed = urlparse(repo_url)
                repo_url = urlunparse(
                    parsed._replace(
                        netloc=f"{git_creds['username']}:{git_creds['password']}@{parsed.hostname}",
                    )
                )

        try:
            repo = _git.Repo.clone_from(
                repo_url,
                project_path,
                **clone_kwargs,
            )
            commit_sha = repo.head.commit.hexsha
            logger.info(
                "dbt_project_cloned",
                repo_url=repo_url,
                branch=branch,
                commit_sha=commit_sha,
                project_path=project_path,
            )
        except Exception as exc:
            raise TransformationExecutionError(
                f"Failed to clone dbt project from {repo_url}: {exc}"
            ) from exc

        # Validate dbt_project.yml exists in the cloned directory.
        if not os.path.isfile(os.path.join(project_path, "dbt_project.yml")):
            raise TransformationExecutionError(
                f"Cloned dbt project at {project_path} does not contain "
                "dbt_project.yml. Verify the repository URL and branch."
            )

        return project_path

    # ── Command construction (285.9.1.2.1) ────────────────────────────

    def _build_dbt_command(
        self,
        action: str,
        project_path: str,
        models: list[str] | None = None,
        target: str = "prod",
    ) -> list[str]:
        """Build the dbt CLI argument list.

        The ``DBT_PROFILES_DIR`` env var is set by ``_setup_profile()``
        so dbt picks it up automatically, but we also pass
        ``--profiles-dir`` explicitly for robustness.
        """
        cmd: list[str] = ["dbt"]

        # Handle compound commands like "docs-generate" → "docs" "generate"
        if "-" in action:
            cmd.extend(action.split("-"))
        else:
            cmd.append(action)

        cmd.extend(["--project-dir", project_path])
        cmd.extend(["--profiles-dir", self.work_dir])
        cmd.extend(["--target", target])

        if models:
            cmd.append("--select")
            cmd.extend(models)

        return cmd

    def _run_dbt_command(self, cmd: list[str], cwd: str, timeout_seconds: int = 3600) -> None:
        """Execute a dbt CLI command via subprocess.

        Raises:
            TransformationExecutionError: If dbt exits non-zero.
        """
        env = os.environ.copy()
        # Ensure DBT_PROFILES_DIR is in the subprocess env.
        env.setdefault("DBT_PROFILES_DIR", self.work_dir)

        try:
            result = subprocess.run(
                cmd,
                check=False,
                cwd=cwd,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            logger.error(
                "dbt_command_timeout",
                action=cmd[1] if len(cmd) > 1 else cmd[0],
                run_id=self.run_id,
                timeout_s=timeout_seconds,
            )
            raise TransformationExecutionError(
                f"dbt command timed out after {timeout_seconds}s: {' '.join(cmd)}"
            ) from exc
        except FileNotFoundError:
            raise TransformationExecutionError(
                "dbt executable not found. Ensure dbt Core is installed and available on PATH."
            )

        if result.returncode != 0:
            stderr_tail = result.stderr[-2000:] if result.stderr else ""
            logger.error(
                "dbt_command_failed",
                action=cmd[1] if len(cmd) > 1 else cmd[0],
                run_id=self.run_id,
                returncode=result.returncode,
                stderr_tail=stderr_tail,
            )
            raise TransformationExecutionError(
                f"dbt command exited with code {result.returncode}: {' '.join(cmd)}\n{stderr_tail}"
            )

        # Log stdout tail for debugging
        stdout_tail = result.stdout[-500:] if result.stdout else ""
        logger.debug(
            "dbt_command_stdout",
            action=cmd[1] if len(cmd) > 1 else cmd[0],
            stdout_tail=stdout_tail,
        )

    # ── Log capture (285.9.1.2.3) ─────────────────────────────────────

    @staticmethod
    def _parse_run_results(run_results_path: str) -> list[dict[str, Any]]:
        """Parse ``target/run_results.json`` into a list of per-model
        result dicts with extracted timing and row-count data.

        Returns an empty list when the file is missing or unparseable
        (dbt may not produce run_results.json for parse/docs-generate).
        """
        if not os.path.isfile(run_results_path):
            logger.debug("run_results_not_found", path=run_results_path)
            return []

        try:
            with open(run_results_path) as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("run_results_unparseable", path=run_results_path, error=str(exc))
            return []

        parsed: list[dict[str, Any]] = []
        for result in data.get("results", []):
            model_result: dict[str, Any] = {
                "unique_id": result.get("unique_id", "unknown"),
                "status": result.get("status", "unknown"),
                "execution_time_seconds": result.get("execution_time", 0.0),
                "message": result.get("message", ""),
                "rows_affected": (
                    result.get("adapter_response", {}).get("rows_affected", 0)
                    if isinstance(result.get("adapter_response"), dict)
                    else 0
                ),
            }
            # Extract thread_id for concurrency tracking
            thread = result.get("thread_id")
            if thread:
                model_result["thread_id"] = thread
            # Compute per-phase timing from the timing array when both
            # timestamps are present.
            for timing in result.get("timing", []):
                name = timing.get("name", "")
                if name in ("compile", "execute"):
                    started = timing.get("started_at")
                    completed = timing.get("completed_at")
                    if started and completed:
                        try:
                            from datetime import datetime

                            dt_start = datetime.fromisoformat(started.replace("Z", "+00:00"))
                            dt_end = datetime.fromisoformat(completed.replace("Z", "+00:00"))
                            model_result[f"timing_{name}_seconds"] = (
                                dt_end - dt_start
                            ).total_seconds()
                        except (ValueError, TypeError):
                            pass
            parsed.append(model_result)

        return parsed

    @staticmethod
    def _parse_elapsed_time(run_results_path: str) -> float | None:
        """Return the total ``elapsed_time`` from run_results.json, or
        None if unavailable."""
        if not os.path.isfile(run_results_path):
            return None
        try:
            with open(run_results_path) as f:
                data = json.load(f)
            return data.get("elapsed_time")
        except (json.JSONDecodeError, OSError):
            return None

    @staticmethod
    def _capture_error_logs(dbt_log_path: str) -> list[str]:
        """Extract ERROR-level lines from ``logs/dbt.log``.

        Returns a list of log lines containing ``[error]`` (dbt's
        structured log marker).  Empty list when the file is missing.
        """
        if not os.path.isfile(dbt_log_path):
            return []

        error_lines: list[str] = []
        try:
            with open(dbt_log_path) as f:
                for line in f:
                    if re.search(r"\[error\]", line, re.IGNORECASE):
                        error_lines.append(line.rstrip("\n"))
        except OSError as exc:
            logger.warning("dbt_log_unreadable", path=dbt_log_path, error=str(exc))
            return []

        return error_lines

    @staticmethod
    def _build_span_attributes(
        results: list[dict[str, Any]], elapsed_total: float | None
    ) -> dict[str, Any]:
        """Build a Prefect-span-compatible dict from parsed dbt results.

        Includes aggregate counts, total timing + rows, and per-model
        breakdowns for fine-grained observability.
        """
        total = len(results)
        success = sum(1 for r in results if r.get("status") == "success")
        error = sum(1 for r in results if r.get("status") == "error")
        skipped = sum(1 for r in results if r.get("status") == "skipped")
        total_rows = sum(r.get("rows_affected", 0) for r in results)

        attrs: dict[str, Any] = {
            "dbt.models_run": total,
            "dbt.models_success": success,
            "dbt.models_error": error,
            "dbt.models_skipped": skipped,
            "dbt.total_rows_affected": total_rows,
        }
        if elapsed_total is not None:
            attrs["dbt.total_elapsed_seconds"] = elapsed_total

        # Per-model timing and row counts as separate span attributes.
        for r in results:
            uid = r.get("unique_id", "unknown")
            exec_time = r.get("execution_time_seconds")
            if exec_time is not None:
                attrs[f"dbt.model_timing.{uid}"] = exec_time
            rows = r.get("rows_affected", 0)
            attrs[f"dbt.model_rows.{uid}"] = rows

        return attrs

    @staticmethod
    def _sanitize_path_component(value: str) -> str:
        """Replace characters unsafe for path components with underscores."""
        return re.sub(r"[^a-zA-Z0-9._-]", "_", value)
