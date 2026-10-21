"""
W1.10 (G5) — the refresh-grace period narrowed to a RETRY-ONLY contract.

The pre-fix grace was a takeover primitive: whoever presented a stolen
refresh token within the 5s window of the victim's rotation was MINTED
a fresh token pair (access + refresh, same family) and the victim's
sibling was REVOKED — the exact outcomes G5 forbids: "replay inside
the window must not mint a new pair for the victim nor revoke the
victim's sibling".

New contract (the "original-user retry only" design branch):

* the stale presenter gets 401 ``TOKEN_STALE`` and NOTHING else — no
  pair minted, no cookies set, no sibling revoked, family untouched;
* the legitimate concurrent tab's browser cookie jar already holds the
  rotated token (the rotation response updated the shared jar), so the
  client retries ONCE with the current token and succeeds;
* an attacker retrying the stolen token after the window closes hits
  the unchanged theft response — the whole family is revoked (the
  11.2 contract).

No mocks: real refresh-token rows, the real rotation chain, the real
view over the real DRF stack.
"""

import uuid
from datetime import timedelta

import pytest
from django.core.cache import cache
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.auth.models import RefreshToken
from hub.apps.auth.tests.test_security_hardening import _create_user

pytestmark = pytest.mark.django_db(transaction=True)

REFRESH_URL = "/api/v1/auth/refresh/"


class RefreshGraceRetryOnlyTest(TransactionTestCase):
    """The adversarial replay matrix against the narrowed grace contract."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user, _password = _create_user()

    def _family(self, *, revoked_ago=None, sibling_ago=None):
        """A rotation chain: token_old (seq 0) + token_new (seq 1).

        ``revoked_ago`` backdates token_old's revocation; ``sibling_ago``
        backdates token_new's creation (the grace window anchor).
        """
        family_id = uuid.uuid4()
        token_old_raw = RefreshToken.generate_token()
        token_new_raw = RefreshToken.generate_token()
        RefreshToken.objects.create(
            user=self.user,
            token_hash=RefreshToken.hash_token(token_old_raw),
            family_id=family_id,
            sequence_number=0,
            expires_at=timezone.now() + timedelta(hours=24),
            revoked_at=(
                timezone.now() - timedelta(seconds=revoked_ago)
                if revoked_ago is not None
                else None
            ),
        )
        token_new = RefreshToken.objects.create(
            user=self.user,
            token_hash=RefreshToken.hash_token(token_new_raw),
            family_id=family_id,
            sequence_number=1,
            expires_at=timezone.now() + timedelta(hours=24),
        )
        if sibling_ago is not None:
            RefreshToken.objects.filter(pk=token_new.pk).update(
                created_at=timezone.now() - timedelta(seconds=sibling_ago)
            )
        return family_id, token_old_raw, token_new_raw, token_new

    def _refresh(self, token_str):
        return self.client.post(
            REFRESH_URL, {"refresh_token": token_str}, format="json"
        )

    # ── the G5 pins ──────────────────────────────────────────────────────

    @override_settings(REFRESH_TOKEN_GRACE_PERIOD_SECONDS=5)
    def test_stale_presenter_inside_window_gets_401_and_nothing_else(self):
        """An attacker replaying the stolen token inside the window is
        minted NOTHING and the victim's sibling survives."""
        family_id, token_old_raw, _token_new_raw, token_new = self._family(
            revoked_ago=2
        )

        response = self._refresh(token_old_raw)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.json()["code"], "TOKEN_STALE")
        # No pair minted for the presenter — no body tokens, no cookies.
        self.assertNotIn("access_token", response.data)
        self.assertNotIn("refresh_token", response.data)
        self.assertEqual(response.cookies, {})

        # The victim's sibling is NOT revoked.
        token_new.refresh_from_db()
        self.assertIsNone(token_new.revoked_at)
        # No new sibling was minted — the family is exactly 2 rows.
        seqs = list(
            RefreshToken.objects.filter(family_id=family_id)
            .order_by("sequence_number")
            .values_list("sequence_number", flat=True)
        )
        self.assertEqual(seqs, [0, 1])

    @override_settings(REFRESH_TOKEN_GRACE_PERIOD_SECONDS=5)
    def test_original_holder_retry_with_current_token_succeeds(self):
        """The original-user retry leg: after the stale 401, the CURRENT
        token (already in the browser's jar) rotates normally."""
        _family_id, token_old_raw, token_new_raw, _token_new = self._family(
            revoked_ago=2
        )

        stale_response = self._refresh(token_old_raw)
        self.assertEqual(stale_response.status_code, status.HTTP_401_UNAUTHORIZED)

        retry_response = self._refresh(token_new_raw)
        self.assertEqual(retry_response.status_code, status.HTTP_200_OK)
        self.assertIn("access_token", retry_response.data)

    @override_settings(REFRESH_TOKEN_GRACE_PERIOD_SECONDS=5)
    def test_replay_outside_window_revokes_family(self):
        """After the window closes, the stale token is a genuine replay —
        the whole family is revoked (the unchanged 11.2 theft response)."""
        family_id, token_old_raw, token_new_raw, token_new = self._family(
            revoked_ago=30, sibling_ago=30
        )

        response = self._refresh(token_old_raw)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotEqual(response.json().get("code"), "TOKEN_STALE")
        # The sibling was revoked too (family-wide revocation).
        token_new.refresh_from_db()
        self.assertIsNotNone(token_new.revoked_at)
        self.assertTrue(
            RefreshToken.objects.filter(
                family_id=family_id, revoked_at__isnull=True
            ).count()
            == 0
        )

    @override_settings(REFRESH_TOKEN_GRACE_PERIOD_SECONDS=0)
    def test_grace_disabled_revokes_family_immediately(self):
        """grace=0 removes the retry window entirely — revoked token →
        family revoked, no stale path."""
        family_id, token_old_raw, _token_new_raw, _token_new = self._family(
            revoked_ago=1
        )

        response = self._refresh(token_old_raw)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotEqual(response.json().get("code"), "TOKEN_STALE")
        self.assertTrue(
            RefreshToken.objects.filter(
                family_id=family_id, revoked_at__isnull=True
            ).count()
            == 0
        )
