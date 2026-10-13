"""Pin the public-tree probe in ``tests/_django_bootstrap.py``.

The probe decides whether ``ensure_django()`` must set ``HUB_CORE_ONLY=1``
BEFORE the first ``django.setup()`` (Django's app registry is not
reentrant, so a wrong decision cannot be recovered).  An off-by-one in the
path computation (``parents[3]`` instead of ``parents[2]``) made the
PRIVATE tree look like the public one, so ``HUB_CORE_ONLY=1`` was set on
every host run and any test importing a paid model died at collection with
``RuntimeError: Model class ... doesn't declare an explicit app_label``
(measured 2026-08-28 in the marketplace CLI/SDK consistency file).
"""

from tests._django_bootstrap import _public_tree_missing_paid_apps


def test_private_tree_is_not_detected_as_public():
    """The private repo ships the paid app directories — probe must be False."""
    assert _public_tree_missing_paid_apps() is False
