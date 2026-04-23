"""Fixture with zero swallows, zero ORM, zero status assertions."""


def clean():
    try:
        pass
    except Exception:
        raise


def also_clean():
    try:
        pass
    except ValueError:
        pass
