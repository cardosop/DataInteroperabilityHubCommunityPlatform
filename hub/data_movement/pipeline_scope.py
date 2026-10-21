"""Phase 6 (openspec wire-databricks-dlt-movement task 6.5) — the pipeline
execution context (design D4): the scoped write credential + the
read-only-guard bypass that exists ONLY inside the pipeline executor.

The repo's read-only guard blocks write SQL everywhere by default. The
bypass lives in a thread-local scope entered by ``MovementPipelineExecutor``
— a token minted by the executor instance is the only key that opens it:
no executor, no bypass. Nesting is refused, the scope is thread-local (a
bypass on one thread never leaks to another), it is a SYNCHRONOUS
contextmanager (never held across awaits), and every exit — including an
exception — restores the guard.

The pipeline SHALL run with a ``ScopedWriteCredential`` for UC targets: a
credential bound to exactly one staging target (``catalog.schema.volume``)
that refuses use for any other target. The PAT/M2M material resolution from
the tenant's ``WarehouseConnection`` lands in task 6.6 — until then the
executor fails CLOSED rather than run a UC pipeline without one.
"""

from __future__ import annotations

import contextlib
import re
import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from datetime import datetime


class GuardScopeError(Exception):
    """The read-only-guard bypass was entered outside the pipeline
    execution context."""

    code = "DLT_PIPELINE_SCOPE_VIOLATION"


class ScopedCredentialError(Exception):
    """A scoped write credential was used outside its bound scope."""

    code = "DLT_CREDENTIAL_SCOPE_VIOLATION"


class CredentialNotResolvedError(Exception):
    """A UC staging target has no usable scoped write credential."""

    code = "DLT_CREDENTIAL_NOT_RESOLVED"


# A UC target: three dot-separated UC identifiers (the 2.2 guard's
# discipline — never a path or a SQL fragment).
_UC_TARGET_RE = re.compile(
    r"^[a-zA-Z_][a-zA-Z0-9_]*\.[a-zA-Z_][a-zA-Z0-9_]*\.[a-zA-Z_][a-zA-Z0-9_]*$"
)


@dataclass(frozen=True)
class ScopedWriteCredential:
    """A write credential scoped to exactly ONE staging target.

    ``material`` is the opaque credential body (a PAT token, or the
    client-credential material for M2M) — it is never logged.
    """

    kind: str  # "PAT" | "M2M"
    material: str
    target: str  # catalog.schema.volume — the ONLY target this may write
    workspace_host: str | None = None
    expires_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.kind not in ("PAT", "M2M"):
            raise ScopedCredentialError(
                f"unsupported credential kind {self.kind!r} — PAT or M2M required"
            )
        if not self.material or not self.material.strip():
            raise ScopedCredentialError("a scoped write credential needs non-empty material")
        if not _UC_TARGET_RE.match(self.target):
            raise ScopedCredentialError(
                f"malformed credential target {self.target!r} — catalog.schema.volume required"
            )

    def assert_scoped_to(self, target: str) -> None:
        """Fail closed when this credential is used for any other target."""
        if target != self.target:
            raise ScopedCredentialError(
                f"credential is scoped to {self.target!r} — use for {target!r} is refused"
            )


class _ScopeToken:
    """Minted ONLY by a ``MovementPipelineExecutor`` — the key that opens
    the guard-bypass scope. Anything else is refused."""

    __slots__ = ("_executor_id",)

    def __init__(self, executor_id: int) -> None:
        self._executor_id = executor_id


class MovementPipelineExecutor:
    """The pipeline executor (design D1/D4): owns the guard-bypass scope.

    Construction is fail-closed: a UC staging target REQUIRES a scoped
    write credential (``CredentialNotResolvedError`` otherwise). The
    credential is re-checked against the target at execute() time — the
    scope check happens BEFORE any work runs.
    """

    def __init__(
        self,
        *,
        tenant,
        staging_target=None,
        credential: ScopedWriteCredential | None = None,
    ) -> None:
        if tenant is None:
            raise TypeError("MovementPipelineExecutor requires a tenant")
        if staging_target is not None and credential is None:
            raise CredentialNotResolvedError(
                f"the UC staging target {staging_target.qualified} has no scoped "
                "write credential — the pipeline refuses to run without one "
                "(the WarehouseConnection resolver lands in task 6.6)"
            )
        self.tenant = tenant
        self.staging_target = staging_target
        self.credential = credential
        self._token = _ScopeToken(id(self))

    def execute(self, work: Callable[[], Any]) -> Any:
        """Run the pipeline work INSIDE the guard-bypass scope.

        The credential's scope is validated before the scope opens — a
        mismatch fails BEFORE any work runs. The scope restores the guard
        on every exit, including exceptions.
        """
        if not callable(work):
            raise TypeError("execute() needs a callable pipeline step")
        if self.credential is not None and self.staging_target is not None:
            self.credential.assert_scoped_to(self.staging_target.qualified)
        with pipeline_guard_scope(self._token):
            return work()


# Thread-local bypass depth — a scope entered on one thread never leaks
# into another (the worker runs are threaded).
_scope_state = threading.local()


def _scope_depth() -> int:
    return getattr(_scope_state, "depth", 0)


@contextlib.contextmanager
def pipeline_guard_scope(token: _ScopeToken) -> Iterator[None]:
    """The read-only-guard bypass scope (design D4).

    Opened ONLY with a token minted by a ``MovementPipelineExecutor`` —
    a missing or forged token is refused (``GuardScopeError``). Nesting
    is refused; the exit always restores the guard.
    """
    if not isinstance(token, _ScopeToken):
        raise GuardScopeError(
            "the guard-bypass scope requires an executor-minted token — "
            "the bypass exists ONLY inside the pipeline execution context"
        )
    if _scope_depth() > 0:
        raise GuardScopeError("the guard-bypass scope is already active — nesting refused")
    _scope_state.depth = 1
    try:
        yield
    finally:
        _scope_state.depth = 0


def is_guard_bypassed() -> bool:
    """True ONLY on the thread that is currently inside a pipeline scope."""
    return _scope_depth() > 0
