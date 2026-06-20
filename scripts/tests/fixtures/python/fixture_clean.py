"""Fixture with zero swallows, zero ORM, zero status assertions."""

import contextlib


def clean():
    try:
        pass
    except Exception:
        raise


def also_clean():
    with contextlib.suppress(ValueError):
        pass
