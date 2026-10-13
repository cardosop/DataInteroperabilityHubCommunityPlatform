"""Phase 4 (openspec add-databricks-jobs task 4.3) — Databricks jobs client.

CRUD + run-now + runs/get|list for the workspace's jobs
(``/api/2.1/jobs/*`` — the pinned 2.1 jobs surface), built on the
production ``DatabricksApiClient`` (retries, breaker, version-pinned
paths). The client owns NO credentials: the caller constructs it with
the identity-resolved client (the 3.2 mirror's contract — "the caller
owns the client").

- **Gate-first (D3 / the 2.4 denylist discipline)** — the task
  allowlist and the cluster-policy guard run BEFORE any network call.
  Spark SQL, notebook, and SQL-warehouse tasks are allowed; Python
  tasks (spark_python / python_wheel) are gated by
  ``python_tasks_enabled`` (default OFF — fail-closed); every other
  task kind (known or unknown) is refused; a job cluster without a
  cluster policy id is refused. A refusal raises
  ``DatabricksJobTaskError`` (``DATABRICKS_JOB_TASK_FORBIDDEN``) with
  ZERO jobs API calls — an ungoverned job can never be created through
  the Hub.
- **The tenant flag** — ``python_tasks_enabled`` is the CALLER's input
  (resolved from the tenant's
  ``databricks_jobs_python_tasks_enabled`` flag at the 4.5 boundary;
  the flag field + registry entry ship with this task per the 0.12
  flag discipline). The client itself stays ORM-free — the default
  False keeps every Python task refused until a caller opts in.
- **Shape discipline** — wrong TYPES raise TypeError, wrong VALUES
  raise ValueError (the repo's boundary convention) BEFORE any network
  call.
- **Errors** — workspace rejections propagate the classified
  ``Databricks*Error`` family; malformed/non-object 2xx bodies are
  classified ``DatabricksApiError`` (the 0.7 discipline) while mutation
  answers tolerate the API's legitimate empty-body 200.

A task may reference an ``existing_cluster_id`` — that is NOT a job
cluster (nothing new is created), so the policy guard leaves it alone.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from hub.apps.databricks_admin.client import DatabricksApiClient, DatabricksApiError

if TYPE_CHECKING:
    import httpx

# The D3 allowlist — Spark SQL / notebook / SQL-warehouse tasks.
_ALLOWED_TASK_KINDS = frozenset({"spark_sql_task", "notebook_task", "sql_task"})
# The Python family — gated by python_tasks_enabled (default OFF).
_PYTHON_TASK_KINDS = frozenset({"spark_python_task", "python_wheel_task"})
# Known-but-never-allowed kinds — refused by name, fail-closed. A task
# kind OUTSIDE every set is refused as an unknown task shape.
_KNOWN_FORBIDDEN_KINDS = frozenset(
    {
        "dbt_task",
        "spark_jar_task",
        "spark_submit_task",
        "pipeline_task",
        "run_job_task",
        "for_each_task",
        "clean_rooms_notebook_task",
    }
)
_ALL_KIND_KEYS = _ALLOWED_TASK_KINDS | _PYTHON_TASK_KINDS | _KNOWN_FORBIDDEN_KINDS


class DatabricksJobTaskError(DatabricksApiError):
    """The Hub's own gate failure — a job definition carrying a task or
    cluster configuration the allowlist/policy guard refuses (the D3
    gate-first discipline). Refused BEFORE any jobs API call."""

    def __init__(self, message: str):
        super().__init__(message, code="DATABRICKS_JOB_TASK_FORBIDDEN")


class DatabricksJobsClient:
    """Databricks jobs client (see module docstring)."""

    def __init__(self, client: DatabricksApiClient, *, python_tasks_enabled: bool = False):
        if not isinstance(python_tasks_enabled, bool):
            raise TypeError("python_tasks_enabled must be a bool")
        self._client = client
        self._python_tasks_enabled = python_tasks_enabled

    # ── reads ───────────────────────────────────────────────────────────

    def list_jobs(self) -> list[dict]:
        """List the workspace's jobs (the ``jobs`` array)."""
        response = self._client.request("GET", "jobs.list")
        payload = self._parse_json_object(response, "jobs.list")
        jobs = payload.get("jobs")
        if not isinstance(jobs, list):
            raise DatabricksApiError(
                "jobs.list returned a non-list 'jobs' field",
                status_code=response.status_code,
            )
        return jobs

    def get_job(self, job_id: str) -> dict:
        """Fetch one job's payload (job_id/settings/creator/...)."""
        job_id = self._require_job_id(job_id)
        response = self._client.request("GET", "jobs.get", params={"job_id": job_id})
        return self._parse_json_object(response, "jobs.get")

    def get_run(self, run_id: str) -> dict:
        """Fetch one run's payload (run_id/state/run_duration/...)."""
        run_id = self._require_run_id(run_id)
        response = self._client.request("GET", "jobs.runs.get", params={"run_id": run_id})
        return self._parse_json_object(response, "jobs.runs.get")

    def list_runs(self, *, job_id: str | None = None, page_token: str | None = None) -> list[dict]:
        """List runs (the ``runs`` array), optionally filtered by job."""
        params: dict = {}
        if job_id is not None:
            params["job_id"] = self._require_job_id(job_id)
        if page_token is not None:
            if not isinstance(page_token, str) or not page_token.strip():
                raise ValueError("page_token must be a non-empty string")
            params["page_token"] = page_token
        response = self._client.request("GET", "jobs.runs.list", params=params)
        payload = self._parse_json_object(response, "jobs.runs.list")
        runs = payload.get("runs")
        if not isinstance(runs, list):
            raise DatabricksApiError(
                "jobs.runs.list returned a non-list 'runs' field",
                status_code=response.status_code,
            )
        return runs

    # ── mutations ───────────────────────────────────────────────────────

    def create_job(
        self,
        *,
        name: str,
        tasks: list,
        job_clusters: list | None = None,
        schedule: dict | None = None,
        max_concurrent_runs: int | None = None,
    ) -> str:
        """Create a job; returns the response's job id.

        The gate (allowlist + cluster policy) runs BEFORE any network
        call; the allowed envelope ships the caller's fields EXACTLY
        (the spec scenario).
        """
        payload = self._build_job_settings(name, tasks, job_clusters, schedule, max_concurrent_runs)
        response = self._client.request("POST", "jobs.create", json=payload)
        body = self._parse_json_object(response, "jobs.create")
        job_id = str(body.get("job_id") or "").strip()
        if not job_id:
            raise DatabricksApiError(
                "jobs.create returned no job id", status_code=response.status_code
            )
        return job_id

    def update_job(
        self,
        job_id: str,
        *,
        name: str,
        tasks: list,
        job_clusters: list | None = None,
        schedule: dict | None = None,
    ) -> dict:
        """Update a job — POST ``{"job_id", "new_settings"}``.

        The jobs API REPLACES the settings entirely: a field omitted
        from ``new_settings`` is reset on the workspace side, so the
        caller ships the full intended settings (name + tasks are
        required). The gate runs on the new settings BEFORE any call.
        """
        job_id = self._require_job_id(job_id)
        new_settings = self._build_job_settings(name, tasks, job_clusters, schedule, None)
        response = self._client.request(
            "POST", "jobs.update", json={"job_id": job_id, "new_settings": new_settings}
        )
        return self._parse_mutation_json(response, "jobs.update")

    def delete_job(self, job_id: str) -> None:
        """Delete the job (the API answers without a body)."""
        job_id = self._require_job_id(job_id)
        self._client.request("POST", "jobs.delete", json={"job_id": job_id})

    def run_now(self, job_id: str) -> str:
        """Trigger a job run; returns the response's run id.

        No gate applies — the job was created through the allowlist;
        run-now merely executes it.
        """
        job_id = self._require_job_id(job_id)
        response = self._client.request("POST", "jobs.run_now", json={"job_id": job_id})
        body = self._parse_json_object(response, "jobs.run_now")
        run_id = str(body.get("run_id") or "").strip()
        if not run_id:
            raise DatabricksApiError(
                "jobs.run_now returned no run id", status_code=response.status_code
            )
        return run_id

    # ── the gate ────────────────────────────────────────────────────────

    def _build_job_settings(
        self,
        name: str,
        tasks: list,
        job_clusters: list | None,
        schedule: dict | None,
        max_concurrent_runs: int | None,
    ) -> dict:
        """The create/update envelope: shape checks + the gate run
        BEFORE any network call (wrong TYPES raise TypeError, wrong
        VALUES raise ValueError, refused configurations raise
        ``DatabricksJobTaskError`` — all with ZERO calls)."""
        if not isinstance(name, str):
            raise TypeError("name must be a string")
        if not name.strip():
            raise ValueError("name must be a non-empty string")
        self._gate_tasks(tasks)
        self._gate_job_clusters(job_clusters)
        if schedule is not None and not isinstance(schedule, dict):
            raise TypeError("schedule must be a dict")
        if max_concurrent_runs is not None:
            if not isinstance(max_concurrent_runs, int) or isinstance(max_concurrent_runs, bool):
                raise TypeError("max_concurrent_runs must be an integer")
            if max_concurrent_runs < 1:
                raise ValueError("max_concurrent_runs must be a positive integer")
        payload: dict = {"name": name, "tasks": tasks}
        if job_clusters:
            payload["job_clusters"] = job_clusters
        if schedule is not None:
            payload["schedule"] = schedule
        if max_concurrent_runs is not None:
            payload["max_concurrent_runs"] = max_concurrent_runs
        return payload

    def _gate_tasks(self, tasks: list) -> None:
        """The D3 task allowlist. Refusals raise
        ``DatabricksJobTaskError`` BEFORE any network call."""
        if not isinstance(tasks, list):
            raise TypeError("tasks must be a list of task dicts")
        if not tasks:
            raise ValueError("tasks must contain at least one task")
        for index, task in enumerate(tasks):
            if not isinstance(task, dict):
                raise TypeError(f"tasks[{index}] must be a dict")
            kinds = [
                kind for kind in _ALL_KIND_KEYS if kind in task and isinstance(task[kind], dict)
            ]
            malformed = [
                kind for kind in _ALL_KIND_KEYS if kind in task and not isinstance(task[kind], dict)
            ]
            if malformed:
                raise DatabricksJobTaskError(
                    f"tasks[{index}] carries a malformed {malformed[0]} payload "
                    "(expected an object) — the allowlist refuses it"
                )
            if len(kinds) != 1:
                raise DatabricksJobTaskError(
                    f"tasks[{index}] must carry exactly one task kind — the allowlist "
                    "refuses ambiguous or unknown task shapes"
                )
            kind = kinds[0]
            if kind in _PYTHON_TASK_KINDS:
                if not self._python_tasks_enabled:
                    raise DatabricksJobTaskError(
                        f"tasks[{index}] carries a Python task ({kind}) — gated by "
                        "databricks_jobs_python_tasks_enabled (off for this caller)"
                    )
                continue
            if kind not in _ALLOWED_TASK_KINDS:
                raise DatabricksJobTaskError(
                    f"tasks[{index}] carries task kind {kind} — outside the allowlist "
                    "(Spark SQL / notebook / SQL warehouse; Python flag-gated)"
                )

    @staticmethod
    def _gate_job_clusters(job_clusters: list | None) -> None:
        """The D3 cluster-policy guard: a job cluster REQUIRES a
        cluster policy id — an ungoverned cluster must never be
        creatable through the Hub."""
        if job_clusters is None:
            return
        if not isinstance(job_clusters, list):
            raise TypeError("job_clusters must be a list of cluster dicts")
        for index, entry in enumerate(job_clusters):
            if not isinstance(entry, dict):
                raise TypeError(f"job_clusters[{index}] must be a dict")
            new_cluster = entry.get("new_cluster")
            if not isinstance(new_cluster, dict):
                raise DatabricksJobTaskError(
                    f"job_clusters[{index}] carries no new_cluster definition — "
                    "every job cluster must define its cluster"
                )
            policy_id = new_cluster.get("cluster_policy_id")
            if not isinstance(policy_id, str) or not policy_id.strip():
                raise DatabricksJobTaskError(
                    f"job_clusters[{index}] carries no cluster policy id — an "
                    "ungoverned cluster must never be creatable through the Hub"
                )

    # ── internals ───────────────────────────────────────────────────────

    @staticmethod
    def _require_job_id(job_id: str) -> str:
        """A missing/empty id would query ``jobs/get`` with no target —
        a silently wrong call. Fail at development time instead (the
        0.7 resolve_warehouse_id discipline)."""
        if not isinstance(job_id, str):
            raise TypeError("job id must be a string")
        job_id = job_id.strip()
        if not job_id:
            raise ValueError("job id must not be empty")
        return job_id

    @staticmethod
    def _require_run_id(run_id: str) -> str:
        if not isinstance(run_id, str):
            raise TypeError("run id must be a string")
        run_id = run_id.strip()
        if not run_id:
            raise ValueError("run id must not be empty")
        return run_id

    @staticmethod
    def _parse_json_object(response: httpx.Response, operation: str) -> dict:
        """Strict object parse for READ/create answers — a malformed or
        non-object 2xx body is a classified client error, never a leaked
        JSONDecodeError (the 0.7 discipline)."""
        try:
            payload = response.json()
        except ValueError as exc:
            raise DatabricksApiError(
                f"{operation} returned a non-JSON body", status_code=response.status_code
            ) from exc
        if not isinstance(payload, dict):
            raise DatabricksApiError(
                f"{operation} returned a non-object body", status_code=response.status_code
            )
        return payload

    @staticmethod
    def _parse_mutation_json(response: httpx.Response, operation: str) -> dict:
        """Lenient object parse for mutation answers: the jobs API's
        update/delete may legitimately answer 200 with an EMPTY body —
        that is a successful call (``{}``), never a parse crash."""
        if not response.content:
            return {}
        try:
            payload = response.json()
        except ValueError as exc:
            raise DatabricksApiError(
                f"{operation} returned a non-JSON body", status_code=response.status_code
            ) from exc
        if payload is None:
            return {}
        if not isinstance(payload, dict):
            raise DatabricksApiError(
                f"{operation} returned a non-object body", status_code=response.status_code
            )
        return payload
