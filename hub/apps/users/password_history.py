"""
Phase 225.1 — password-history service.

A thin, pure function API on top of :class:`hub.apps.users.models.PasswordHistory`:

- ``record_password_change(user)`` — snapshot the user's current hashed
  password into history. Idempotent against the `unique_together`
  constraint (if the exact same hash is already present we silently do
  nothing instead of raising ``IntegrityError``).

- ``is_password_reused(user, plaintext)`` — return ``True`` iff any of the
  user's last ``PASSWORD_HISTORY_WINDOW`` historical hashes verifies
  against the supplied plaintext via Django's hasher (constant-time,
  salt-aware). Returns ``False`` when there is no history.

Keeping this outside ``models.py`` avoids circular imports with the auth
views and lets callers depend on a narrow, testable surface.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib.auth.hashers import check_password
from django.db import IntegrityError, transaction

from hub.apps.users.models import PasswordHistory

if TYPE_CHECKING:  # pragma: no cover
    from hub.apps.users.models import User

#: Number of most-recent historical hashes consulted by ``is_password_reused``.
#: Must stay in lockstep with the assertions in Phase 225.1 tests and any
#: policy copy surfaced to users.
PASSWORD_HISTORY_WINDOW = 5


def record_password_change(user: "User") -> PasswordHistory | None:
    """
    Persist the user's currently set password hash as a history entry.

    Callers must invoke :meth:`User.set_password` (or equivalent) *before*
    this function so ``user.password`` already holds the new hasher output.

    Returns the created row, or ``None`` if the hash was already on file
    for this user (unique-constraint no-op — no exception is raised).
    """
    hashed = user.password
    if not hashed:
        # Defensive: a user without a usable password (e.g. freshly invited,
        # social-login-only) has nothing to record.
        return None

    try:
        with transaction.atomic():
            return PasswordHistory.objects.create(user=user, password_hash=hashed)
    except IntegrityError:
        # Same salted hash recorded twice for the same user — treat as a
        # successful no-op rather than surfacing a DB error to the caller.
        return None


def is_password_reused(
    user: "User",
    plaintext: str,
    *,
    window: int = PASSWORD_HISTORY_WINDOW,
) -> bool:
    """
    Return True if *plaintext* matches any of the user's last *window*
    historical password hashes.

    Uses :func:`django.contrib.auth.hashers.check_password`, which is
    constant-time against the supplied hash and honours the hasher
    configured at the time of storage (so migrations between bcrypt /
    argon2 / PBKDF2 remain transparent).

    ``window <= 0`` disables the check and returns ``False``.
    """
    if window <= 0 or not plaintext:
        return False

    recent_hashes = PasswordHistory.objects.filter(user=user).values_list(
        "password_hash", flat=True
    )[:window]
    for stored_hash in recent_hashes:
        if check_password(plaintext, stored_hash):
            return True
    return False
