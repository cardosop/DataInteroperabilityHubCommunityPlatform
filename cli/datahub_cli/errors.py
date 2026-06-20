"""
Typed CLI error classes (278.AA.13).

Replaces generic ``click.ClickException`` with typed exceptions that carry
machine-readable error codes and distinct exit codes for scripting.
"""

from __future__ import annotations

import click

# -- Exit code constants (align with sysexits.h conventions) ----------------

EX_OK = 0
EX_USAGE = 64  # command-line usage error
EX_DATAERR = 65  # data format error
EX_NOINPUT = 66  # cannot open input
EX_UNAVAILABLE = 69  # service unavailable
EX_SOFTWARE = 70  # internal software error
EX_IOERR = 74  # input/output error
EX_TEMPFAIL = 75  # temporary failure — may retry
EX_CONFIG = 78  # configuration error


# -- Base CLI error ---------------------------------------------------------


class CLIError(click.ClickException):
    """Base typed CLI exception.

    Subclasses :class:`click.ClickException` so existing ``except
    ClickException`` handlers continue to work.  Adds an ``exit_code``
    and a machine-readable ``error_code`` for scripting.
    """

    exit_code: int = EX_SOFTWARE

    def __init__(self, message: str, error_code: str = "CLI_ERROR") -> None:
        super().__init__(message)
        self.error_code = error_code

    def format_message(self) -> str:
        return f"[{self.error_code}] {self.message}"


# -- Domain error classes ---------------------------------------------------


class CLIAuthError(CLIError):
    """Authentication / authorisation failure (exit 77 for permission)."""

    exit_code = 77


class CLINotFoundError(CLIError):
    """Resource not found (HTTP 404 equivalent)."""

    exit_code = 68  # EX_NOHOST-ish — "host name unknown" mapped to resource


class CLIValidationError(CLIError):
    """Client-side or server-side validation error."""

    exit_code = EX_DATAERR


class CLINetworkError(CLIError):
    """Transient network / connection error — safe to retry."""

    exit_code = EX_TEMPFAIL


class CLIServerError(CLIError):
    """Server-side error (HTTP 5xx equivalent)."""

    exit_code = EX_UNAVAILABLE


class CLIRateLimitError(CLIError):
    """Rate-limited (HTTP 429 equivalent)."""

    exit_code = EX_TEMPFAIL


class CLIConfigError(CLIError):
    """Configuration missing or invalid (API URL, token, etc.)."""

    exit_code = EX_CONFIG


# -- Convenience factory ----------------------------------------------------


def error_from_http_status(
    status_code: int,
    message: str,
    error_code: str = "",
) -> CLIError:
    """Return the appropriate :class:`CLIError` subclass for an HTTP status.

    Args:
        status_code: HTTP response status code.
        message: Human-readable error message.
        error_code: Optional machine-readable error code.

    Returns:
        A typed :class:`CLIError` instance.
    """
    code = error_code or f"HTTP_{status_code}"
    if status_code == 401 or status_code == 403:
        return CLIAuthError(message, code)
    if status_code == 404:
        return CLINotFoundError(message, code)
    if status_code == 422 or status_code == 400:
        return CLIValidationError(message, code)
    if status_code == 429:
        return CLIRateLimitError(message, code)
    if 500 <= status_code < 600:
        return CLIServerError(message, code)
    return CLIError(message, code)
