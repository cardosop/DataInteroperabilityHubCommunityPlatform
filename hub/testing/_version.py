"""
Version sentinel for hub.testing app.

Validates at import time that the installed Django version matches what the
patch suite was authored against.  Raises RuntimeError on mismatch so the
error is loud and immediate.
"""

import django

DJANGO_PATCH_VERSION = "4.2"

_installed = django.get_version()
# Match on major.minor prefix so 4.2.x is accepted.
if not _installed.startswith(DJANGO_PATCH_VERSION):
    raise RuntimeError(
        f"hub.testing patches authored for Django {DJANGO_PATCH_VERSION}.x, "
        f"but Django {_installed} is installed."
    )
