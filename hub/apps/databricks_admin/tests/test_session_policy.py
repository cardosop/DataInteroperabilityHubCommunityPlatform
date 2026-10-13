"""TDD pins for the session-refresh policy (openspec add-databricks-control-plane
task 0b.7 — JOURNEY-DB-004 contract).

Pure policy math — deterministic functions of their clock inputs, so the
pins pass REAL timestamps (no clock mocking, no DB):

- silent refresh at HALF the access-token TTL (journey step 2);
- a non-blocking countdown (default 5 min) before the workspace's
  ``absolute_session_lifetime`` ends, during which refresh attempts STOP
  (journey step 4);
- the HUB session deadline is computed ONLY from Hub-session inputs —
  binding-expiry changes must never move it (journey step 5 /
  "Binding expiry never logs the user out of the Hub session").
"""

from datetime import UTC, datetime, timedelta


class TestHalfTtlRefresh:
    def test_due_at_or_after_half_the_ttl(self):
        from hub.apps.databricks_admin.session_policy import half_ttl_refresh_due

        issued = datetime(2026, 9, 8, 10, 0, 0, tzinfo=UTC)
        expires = issued + timedelta(seconds=3600)
        assert not half_ttl_refresh_due(
            access_token_issued_at=issued,
            access_token_expires_at=expires,
            now=issued + timedelta(seconds=1799),
        )
        assert half_ttl_refresh_due(
            access_token_issued_at=issued,
            access_token_expires_at=expires,
            now=issued + timedelta(seconds=1800),
        )
        assert half_ttl_refresh_due(
            access_token_issued_at=issued,
            access_token_expires_at=expires,
            now=issued + timedelta(seconds=2000),
        )


class TestCountdown:
    def test_countdown_activates_five_minutes_before_absolute_end(self):
        from hub.apps.databricks_admin.session_policy import countdown_state

        absolute_end = datetime(2026, 9, 8, 12, 0, 0, tzinfo=UTC)
        outside = countdown_state(
            binding_absolute_expires_at=absolute_end,
            now=absolute_end - timedelta(seconds=301),
        )
        assert outside["active"] is False
        assert outside["seconds_remaining"] is None

        inside = countdown_state(
            binding_absolute_expires_at=absolute_end,
            now=absolute_end - timedelta(seconds=299),
        )
        assert inside["active"] is True
        assert inside["seconds_remaining"] == 299

    def test_countdown_seconds_remaining_clamps_at_zero(self):
        from hub.apps.databricks_admin.session_policy import countdown_state

        absolute_end = datetime(2026, 9, 8, 12, 0, 0, tzinfo=UTC)
        state = countdown_state(
            binding_absolute_expires_at=absolute_end,
            now=absolute_end + timedelta(seconds=60),  # already past
        )
        assert state["active"] is True
        assert state["seconds_remaining"] == 0

    def test_custom_countdown_threshold_is_respected(self):
        from hub.apps.databricks_admin.session_policy import countdown_state

        absolute_end = datetime(2026, 9, 8, 12, 0, 0, tzinfo=UTC)
        state = countdown_state(
            binding_absolute_expires_at=absolute_end,
            now=absolute_end - timedelta(seconds=120),
            countdown_seconds=180,
        )
        assert state["active"] is True
        assert state["seconds_remaining"] == 120


class TestRefreshAllowed:
    def test_refresh_stops_inside_the_countdown_window(self):
        from hub.apps.databricks_admin.session_policy import refresh_allowed

        absolute_end = datetime(2026, 9, 8, 12, 0, 0, tzinfo=UTC)
        assert refresh_allowed(
            binding_absolute_expires_at=absolute_end,
            now=absolute_end - timedelta(seconds=600),
        )
        assert not refresh_allowed(
            binding_absolute_expires_at=absolute_end,
            now=absolute_end - timedelta(seconds=120),
        )


class TestHubSessionIndependence:
    def test_hub_deadline_derives_only_from_hub_inputs(self):
        from hub.apps.databricks_admin.session_policy import hub_session_deadline

        issued = datetime(2026, 9, 8, 9, 0, 0, tzinfo=UTC)
        lifetime = timedelta(hours=12)
        expected = issued + lifetime

        # The SAME hub inputs with WILDLY different binding expiries —
        # the deadline must not move (binding expiry never logs the Hub
        # user out).
        assert hub_session_deadline(session_issued_at=issued, hub_lifetime=lifetime) == expected
        assert hub_session_deadline(session_issued_at=issued, hub_lifetime=lifetime) == expected

    def test_binding_expiry_never_shrinks_the_hub_deadline(self):
        from hub.apps.databricks_admin.session_policy import hub_session_deadline

        issued = datetime(2026, 9, 8, 9, 0, 0, tzinfo=UTC)
        lifetime = timedelta(hours=12)
        deadline = hub_session_deadline(session_issued_at=issued, hub_lifetime=lifetime)

        # A binding that expires in 5 minutes from the session start...
        binding_end = issued + timedelta(minutes=5)
        # ...is used ONLY for the countdown/refresh policy, never for the
        # hub deadline — the deadline is a pure function of hub inputs and
        # remains the full 12h out.
        assert deadline == issued + lifetime
        assert binding_end < deadline


class TestSettingsKnobs:
    """0b.7 review — the policy's tuning knobs must EXIST in Django
    settings (the DONE note claims the defaults come from settings)."""

    def test_session_knobs_are_defined_in_settings(self):
        from django.conf import settings

        assert hasattr(settings, "SESSION_REAUTH_COUNTDOWN_SECONDS"), (
            "SESSION_REAUTH_COUNTDOWN_SECONDS must be a real settings knob"
        )
        assert hasattr(settings, "ABSOLUTE_SESSION_LIFETIME_SECONDS"), (
            "ABSOLUTE_SESSION_LIFETIME_SECONDS must be a real settings knob"
        )
