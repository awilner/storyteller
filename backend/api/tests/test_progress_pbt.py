# Feature: per-user-progress-tracking — Property-based tests
"""
Property-based tests for per-user progress tracking.

Uses Hypothesis to verify correctness properties from the design document.
"""

from django.contrib.auth.models import User
from rest_framework.test import APIClient

from hypothesis import given, settings, strategies as st
from hypothesis.extra.django import TestCase

from api.models import Project, ProjectShare


# ── Strategies ────────────────────────────────────────────────

# Valid positive integer targets (1 to 1,000,000)
valid_target = st.integers(min_value=1, max_value=1_000_000)

# Role strategy for users who can set targets (owner or co-author)
writer_role = st.sampled_from(["owner", "co-author"])


# ── Helpers ───────────────────────────────────────────────────

def _make_user(prefix="user"):
    """Create a unique user for each Hypothesis example."""
    username = f"{prefix}_{User.objects.count()}_{id(object())}"
    return User.objects.create_user(username=username, password="testpass")


def _make_project_with_user(role):
    """
    Create a project and return (project, user, role).

    If role is 'owner', the user is the project owner.
    If role is 'co-author', a separate owner is created and the user
    is added as a co-author via ProjectShare.
    """
    if role == "owner":
        user = _make_user("owner")
        project = Project.objects.create(owner=user, title="Test Project")
        return project, user
    else:
        owner = _make_user("owner")
        project = Project.objects.create(owner=owner, title="Test Project")
        user = _make_user("coauthor")
        ProjectShare.objects.create(
            project=project, user=user, role="co-author",
        )
        return project, user


def _auth_client(user):
    """Return an APIClient authenticated as the given user."""
    client = APIClient()
    client.force_authenticate(user=user)
    return client


# ── Property 1: Target storage round-trip ─────────────────────


class TargetStorageRoundTripPropertyTest(TestCase):
    """
    Property 1: Target storage round-trip.

    For any user (owner or co-author) on a project, and any valid positive
    integer values for daily_target and session_target, storing those targets
    via the PATCH endpoint and then retrieving them via the GET endpoint
    should return the same values in the response.

    # Feature: per-user-progress-tracking, Property 1: Target storage round-trip
    **Validates: Requirements 1.1, 1.2, 10.2**
    """

    @given(
        role=writer_role,
        daily=valid_target,
        session=valid_target,
    )
    @settings(max_examples=20, deadline=None)
    def test_target_storage_round_trip(self, role, daily, session):
        """
        PATCH daily_target and session_target, then GET and verify the
        returned values match exactly.

        # Feature: per-user-progress-tracking, Property 1: Target storage round-trip
        # **Validates: Requirements 1.1, 1.2, 10.2**
        """
        project, user = _make_project_with_user(role)
        client = _auth_client(user)

        # PATCH targets
        patch_resp = client.patch(
            f"/api/projects/{project.pk}/progress/",
            data={"daily_target": daily, "session_target": session},
            format="json",
        )
        assert patch_resp.status_code == 200, (
            f"PATCH failed with {patch_resp.status_code}: {patch_resp.data}"
        )

        # GET progress
        get_resp = client.get(f"/api/projects/{project.pk}/progress/")
        assert get_resp.status_code == 200, (
            f"GET failed with {get_resp.status_code}: {get_resp.data}"
        )

        data = get_resp.data
        assert data["daily_target"] == daily, (
            f"daily_target: expected {daily}, got {data['daily_target']}"
        )
        assert data["session_target"] == session, (
            f"session_target: expected {session}, got {data['session_target']}"
        )


# ── Property 2: Target update isolation ───────────────────────


# Strategy for generating a pair of user roles where both can set targets
# (owner + co-author, or two co-authors)
user_pair_roles = st.sampled_from([
    ("owner", "co-author"),
    ("co-author", "co-author"),
])


def _make_project_with_two_users(role_a, role_b):
    """
    Create a project and two users with the given roles.

    Returns (project, user_a, user_b).

    Supported combinations:
      - ("owner", "co-author"): user_a is the owner, user_b is a co-author
      - ("co-author", "co-author"): a separate owner is created, both users
        are added as co-authors via ProjectShare
    """
    if role_a == "owner":
        user_a = _make_user("ownerA")
        project = Project.objects.create(owner=user_a, title="Test Project")
        user_b = _make_user("coauthorB")
        ProjectShare.objects.create(
            project=project, user=user_b, role="co-author",
        )
        return project, user_a, user_b
    else:
        # Both are co-authors; create a separate owner
        owner = _make_user("owner")
        project = Project.objects.create(owner=owner, title="Test Project")
        user_a = _make_user("coauthorA")
        user_b = _make_user("coauthorB")
        ProjectShare.objects.create(
            project=project, user=user_a, role="co-author",
        )
        ProjectShare.objects.create(
            project=project, user=user_b, role="co-author",
        )
        return project, user_a, user_b


class TargetUpdateIsolationPropertyTest(TestCase):
    """
    Property 2: Target update isolation.

    For any two users (owner + co-author, or two co-authors) on the same
    project, each with their own daily_target and session_target, updating
    one user's targets should leave the other user's daily_target and
    session_target values unchanged.

    # Feature: per-user-progress-tracking, Property 2: Target update isolation
    **Validates: Requirements 1.3, 1.4**
    """

    @given(
        roles=user_pair_roles,
        daily_a=valid_target,
        session_a=valid_target,
        daily_b=valid_target,
        session_b=valid_target,
        new_daily_a=valid_target,
        new_session_a=valid_target,
    )
    @settings(max_examples=20, deadline=None)
    def test_target_update_isolation(
        self, roles, daily_a, session_a, daily_b, session_b,
        new_daily_a, new_session_a,
    ):
        """
        Set targets for both users, then update user A's targets and verify
        user B's targets remain unchanged.

        # Feature: per-user-progress-tracking, Property 2: Target update isolation
        # **Validates: Requirements 1.3, 1.4**
        """
        role_a, role_b = roles
        project, user_a, user_b = _make_project_with_two_users(role_a, role_b)
        client_a = _auth_client(user_a)
        client_b = _auth_client(user_b)

        # Set initial targets for user A
        resp = client_a.patch(
            f"/api/projects/{project.pk}/progress/",
            data={"daily_target": daily_a, "session_target": session_a},
            format="json",
        )
        assert resp.status_code == 200, (
            f"PATCH user_a initial failed: {resp.status_code}: {resp.data}"
        )

        # Set initial targets for user B
        resp = client_b.patch(
            f"/api/projects/{project.pk}/progress/",
            data={"daily_target": daily_b, "session_target": session_b},
            format="json",
        )
        assert resp.status_code == 200, (
            f"PATCH user_b initial failed: {resp.status_code}: {resp.data}"
        )

        # Update user A's targets to new values
        resp = client_a.patch(
            f"/api/projects/{project.pk}/progress/",
            data={"daily_target": new_daily_a, "session_target": new_session_a},
            format="json",
        )
        assert resp.status_code == 200, (
            f"PATCH user_a update failed: {resp.status_code}: {resp.data}"
        )

        # GET user B's progress and verify targets are unchanged
        get_resp = client_b.get(f"/api/projects/{project.pk}/progress/")
        assert get_resp.status_code == 200, (
            f"GET user_b failed: {get_resp.status_code}: {get_resp.data}"
        )

        data = get_resp.data
        assert data["daily_target"] == daily_b, (
            f"user_b daily_target changed: expected {daily_b}, got {data['daily_target']}"
        )
        assert data["session_target"] == session_b, (
            f"user_b session_target changed: expected {session_b}, got {data['session_target']}"
        )


# ── Strategy: invalid targets ─────────────────────────────────

# Invalid target values: zero, negative integers, floats, and non-numeric strings
invalid_target = st.one_of(
    st.just(0),                                          # zero
    st.integers(max_value=-1),                           # negative integers
    st.floats(allow_nan=False, allow_infinity=False).filter(
        lambda x: not x.is_integer()
    ),                                                   # non-integer floats
    st.text(min_size=1, max_size=20).filter(
        lambda s: not s.strip().lstrip("-").isdigit()
    ),                                                   # non-numeric strings
)


# ── Property 3: Target validation rejects invalid values ──────


class TargetValidationRejectsInvalidValuesPropertyTest(TestCase):
    """
    Property 3: Target validation rejects invalid values.

    For any value that is not a positive integer (including zero, negative
    numbers, floats, and non-numeric strings), submitting it as a daily_target
    or session_target should be rejected with a validation error, and the
    user's existing target values should remain unchanged.

    # Feature: per-user-progress-tracking, Property 3: Target validation rejects invalid values
    **Validates: Requirements 1.5**
    """

    @given(
        role=writer_role,
        initial_daily=valid_target,
        initial_session=valid_target,
        bad_value=invalid_target,
    )
    @settings(max_examples=20, deadline=None)
    def test_invalid_daily_target_rejected(self, role, initial_daily, initial_session, bad_value):
        """
        Set valid targets, then PATCH with an invalid daily_target.
        Assert 400 response and that existing targets are unchanged.

        # Feature: per-user-progress-tracking, Property 3: Target validation rejects invalid values
        # **Validates: Requirements 1.5**
        """
        project, user = _make_project_with_user(role)
        client = _auth_client(user)

        # Set valid initial targets
        resp = client.patch(
            f"/api/projects/{project.pk}/progress/",
            data={"daily_target": initial_daily, "session_target": initial_session},
            format="json",
        )
        assert resp.status_code == 200, (
            f"Initial PATCH failed: {resp.status_code}: {resp.data}"
        )

        # PATCH with invalid daily_target
        resp = client.patch(
            f"/api/projects/{project.pk}/progress/",
            data={"daily_target": bad_value},
            format="json",
        )
        assert resp.status_code == 400, (
            f"Expected 400 for daily_target={bad_value!r}, got {resp.status_code}: {resp.data}"
        )

        # GET and verify targets are unchanged
        get_resp = client.get(f"/api/projects/{project.pk}/progress/")
        assert get_resp.status_code == 200
        assert get_resp.data["daily_target"] == initial_daily, (
            f"daily_target changed after invalid PATCH: expected {initial_daily}, got {get_resp.data['daily_target']}"
        )
        assert get_resp.data["session_target"] == initial_session, (
            f"session_target changed after invalid PATCH: expected {initial_session}, got {get_resp.data['session_target']}"
        )

    @given(
        role=writer_role,
        initial_daily=valid_target,
        initial_session=valid_target,
        bad_value=invalid_target,
    )
    @settings(max_examples=20, deadline=None)
    def test_invalid_session_target_rejected(self, role, initial_daily, initial_session, bad_value):
        """
        Set valid targets, then PATCH with an invalid session_target.
        Assert 400 response and that existing targets are unchanged.

        # Feature: per-user-progress-tracking, Property 3: Target validation rejects invalid values
        # **Validates: Requirements 1.5**
        """
        project, user = _make_project_with_user(role)
        client = _auth_client(user)

        # Set valid initial targets
        resp = client.patch(
            f"/api/projects/{project.pk}/progress/",
            data={"daily_target": initial_daily, "session_target": initial_session},
            format="json",
        )
        assert resp.status_code == 200, (
            f"Initial PATCH failed: {resp.status_code}: {resp.data}"
        )

        # PATCH with invalid session_target
        resp = client.patch(
            f"/api/projects/{project.pk}/progress/",
            data={"session_target": bad_value},
            format="json",
        )
        assert resp.status_code == 400, (
            f"Expected 400 for session_target={bad_value!r}, got {resp.status_code}: {resp.data}"
        )

        # GET and verify targets are unchanged
        get_resp = client.get(f"/api/projects/{project.pk}/progress/")
        assert get_resp.status_code == 200
        assert get_resp.data["daily_target"] == initial_daily, (
            f"daily_target changed after invalid PATCH: expected {initial_daily}, got {get_resp.data['daily_target']}"
        )
        assert get_resp.data["session_target"] == initial_session, (
            f"session_target changed after invalid PATCH: expected {initial_session}, got {get_resp.data['session_target']}"
        )


# ── Property 4: Session reset isolation ───────────────────────


class SessionResetIsolationPropertyTest(TestCase):
    """
    Property 4: Session reset isolation.

    For any two users (owners or co-authors) on the same project, each with
    active session state (session_start_word_count and session_started_at),
    resetting one user's session should create a SessionWordCount record only
    for that user and update only that user's session start state, leaving the
    other user's session state unchanged.

    # Feature: per-user-progress-tracking, Property 4: Session reset isolation
    **Validates: Requirements 4.1, 4.2**
    """

    @given(
        roles=user_pair_roles,
        start_wc_a=st.integers(min_value=1, max_value=100_000),
        start_wc_b=st.integers(min_value=1, max_value=100_000),
    )
    @settings(max_examples=20, deadline=None)
    def test_session_reset_isolation(self, roles, start_wc_a, start_wc_b):
        """
        Set up active sessions for two users, reset user A's session, then
        verify user B's session state in UserProgressSettings is unchanged.

        # Feature: per-user-progress-tracking, Property 4: Session reset isolation
        # **Validates: Requirements 4.1, 4.2**
        """
        from django.utils import timezone

        from api.models import SessionWordCount, UserProgressSettings

        role_a, role_b = roles
        project, user_a, user_b = _make_project_with_two_users(role_a, role_b)

        # Create active session state for both users directly in UserProgressSettings
        now = timezone.now()

        ups_a, _ = UserProgressSettings.objects.get_or_create(
            project=project, user=user_a,
        )
        ups_a.session_start_word_count = start_wc_a
        ups_a.session_started_at = now
        ups_a.save(update_fields=["session_start_word_count", "session_started_at", "updated_at"])

        ups_b, _ = UserProgressSettings.objects.get_or_create(
            project=project, user=user_b,
        )
        ups_b.session_start_word_count = start_wc_b
        ups_b.session_started_at = now
        ups_b.save(update_fields=["session_start_word_count", "session_started_at", "updated_at"])

        # Record user B's session state before the reset
        b_start_wc_before = ups_b.session_start_word_count
        b_started_at_before = ups_b.session_started_at

        # Count existing SessionWordCount records for each user
        swc_count_a_before = SessionWordCount.objects.filter(
            project=project, user=user_a,
        ).count()
        swc_count_b_before = SessionWordCount.objects.filter(
            project=project, user=user_b,
        ).count()

        # Reset user A's session
        client_a = _auth_client(user_a)
        resp = client_a.post(
            f"/api/projects/{project.pk}/progress/",
            data={"action": "reset_session"},
            format="json",
        )
        assert resp.status_code == 200, (
            f"POST reset_session failed: {resp.status_code}: {resp.data}"
        )

        # Verify user B's session state is unchanged
        ups_b.refresh_from_db()
        assert ups_b.session_start_word_count == b_start_wc_before, (
            f"User B session_start_word_count changed: "
            f"expected {b_start_wc_before}, got {ups_b.session_start_word_count}"
        )
        assert ups_b.session_started_at == b_started_at_before, (
            f"User B session_started_at changed: "
            f"expected {b_started_at_before}, got {ups_b.session_started_at}"
        )

        # Verify no new SessionWordCount records were created for user B
        swc_count_b_after = SessionWordCount.objects.filter(
            project=project, user=user_b,
        ).count()
        assert swc_count_b_after == swc_count_b_before, (
            f"SessionWordCount records created for user B: "
            f"expected {swc_count_b_before}, got {swc_count_b_after}"
        )


# ── Property 5: Progress data is user-scoped ──────────────────


class ProgressDataUserScopedPropertyTest(TestCase):
    """
    Property 5: Progress data is user-scoped.

    For any project with DailyWordCount and SessionWordCount records belonging
    to multiple users, the GET progress response for a given user should
    contain only that user's daily_counts and sessions records — no records
    belonging to other users should appear.

    # Feature: per-user-progress-tracking, Property 5: Progress data is user-scoped
    **Validates: Requirements 5.1, 5.2**
    """

    @given(
        roles=user_pair_roles,
        daily_wc_a=st.lists(
            st.tuples(
                st.integers(min_value=1, max_value=28),  # day of month
                st.integers(min_value=0, max_value=10_000),  # word count
            ),
            min_size=1,
            max_size=5,
            unique_by=lambda t: t[0],
        ),
        daily_wc_b=st.lists(
            st.tuples(
                st.integers(min_value=1, max_value=28),
                st.integers(min_value=0, max_value=10_000),
            ),
            min_size=1,
            max_size=5,
            unique_by=lambda t: t[0],
        ),
        session_wc_a=st.lists(
            st.integers(min_value=1, max_value=10_000),
            min_size=1,
            max_size=5,
        ),
        session_wc_b=st.lists(
            st.integers(min_value=1, max_value=10_000),
            min_size=1,
            max_size=5,
        ),
    )
    @settings(max_examples=20, deadline=None)
    def test_progress_data_is_user_scoped(
        self, roles, daily_wc_a, daily_wc_b, session_wc_a, session_wc_b,
    ):
        """
        Create DailyWordCount and SessionWordCount records for two users,
        then GET progress for each user and verify the response contains
        only that user's records.

        # Feature: per-user-progress-tracking, Property 5: Progress data is user-scoped
        # **Validates: Requirements 5.1, 5.2**
        """
        import datetime

        from api.models import DailyWordCount, SessionWordCount

        role_a, role_b = roles
        project, user_a, user_b = _make_project_with_two_users(role_a, role_b)

        # Create DailyWordCount records for user A
        for day, wc in daily_wc_a:
            DailyWordCount.objects.create(
                project=project,
                user=user_a,
                date=datetime.date(2025, 1, day),
                word_count=wc,
            )

        # Create DailyWordCount records for user B
        for day, wc in daily_wc_b:
            DailyWordCount.objects.create(
                project=project,
                user=user_b,
                date=datetime.date(2025, 2, day),  # different month to avoid unique constraint clash
                word_count=wc,
            )

        # Create SessionWordCount records for user A
        base_time = datetime.datetime(2025, 1, 15, 10, 0, 0)
        for i, wc in enumerate(session_wc_a):
            started = base_time + datetime.timedelta(hours=i * 2)
            ended = started + datetime.timedelta(hours=1)
            SessionWordCount.objects.create(
                project=project,
                user=user_a,
                started_at=started,
                ended_at=ended,
                word_count=wc,
            )

        # Create SessionWordCount records for user B
        base_time_b = datetime.datetime(2025, 2, 15, 10, 0, 0)
        for i, wc in enumerate(session_wc_b):
            started = base_time_b + datetime.timedelta(hours=i * 2)
            ended = started + datetime.timedelta(hours=1)
            SessionWordCount.objects.create(
                project=project,
                user=user_b,
                started_at=started,
                ended_at=ended,
                word_count=wc,
            )

        # GET progress for user A
        client_a = _auth_client(user_a)
        resp_a = client_a.get(f"/api/projects/{project.pk}/progress/")
        assert resp_a.status_code == 200, (
            f"GET user_a failed: {resp_a.status_code}: {resp_a.data}"
        )

        # The GET handler may upsert a daily record for "today" for the
        # requesting user, so the returned daily_counts may include one
        # extra record beyond what we explicitly created.  We verify that
        # every explicitly-created record for user A is present and that
        # none of user B's records leak through.

        returned_daily_a = resp_a.data["daily_counts"]
        returned_sessions_a = resp_a.data["sessions"]

        # Build sets of (date_str, word_count) for what we created
        expected_daily_dates_a = {
            datetime.date(2025, 1, day).isoformat() for day, _ in daily_wc_a
        }
        expected_daily_dates_b = {
            datetime.date(2025, 2, day).isoformat() for day, _ in daily_wc_b
        }

        returned_daily_dates_a = {r["date"] for r in returned_daily_a}

        # All of user A's created dates must be present
        assert expected_daily_dates_a.issubset(returned_daily_dates_a), (
            f"Missing user A daily dates: "
            f"{expected_daily_dates_a - returned_daily_dates_a}"
        )
        # None of user B's dates should appear
        assert expected_daily_dates_b.isdisjoint(returned_daily_dates_a), (
            f"User B daily dates leaked into user A response: "
            f"{expected_daily_dates_b & returned_daily_dates_a}"
        )

        # Sessions: user A should see only their sessions
        expected_session_wcs_a = sorted(session_wc_a)
        returned_session_wcs_a = sorted(r["word_count"] for r in returned_sessions_a)
        assert returned_session_wcs_a == expected_session_wcs_a, (
            f"User A sessions mismatch: expected {expected_session_wcs_a}, "
            f"got {returned_session_wcs_a}"
        )

        # GET progress for user B
        client_b = _auth_client(user_b)
        resp_b = client_b.get(f"/api/projects/{project.pk}/progress/")
        assert resp_b.status_code == 200, (
            f"GET user_b failed: {resp_b.status_code}: {resp_b.data}"
        )

        returned_daily_b = resp_b.data["daily_counts"]
        returned_sessions_b = resp_b.data["sessions"]

        returned_daily_dates_b = {r["date"] for r in returned_daily_b}

        # All of user B's created dates must be present
        assert expected_daily_dates_b.issubset(returned_daily_dates_b), (
            f"Missing user B daily dates: "
            f"{expected_daily_dates_b - returned_daily_dates_b}"
        )
        # None of user A's dates should appear
        assert expected_daily_dates_a.isdisjoint(returned_daily_dates_b), (
            f"User A daily dates leaked into user B response: "
            f"{expected_daily_dates_a & returned_daily_dates_b}"
        )

        # Sessions: user B should see only their sessions
        expected_session_wcs_b = sorted(session_wc_b)
        returned_session_wcs_b = sorted(r["word_count"] for r in returned_sessions_b)
        assert returned_session_wcs_b == expected_session_wcs_b, (
            f"User B sessions mismatch: expected {expected_session_wcs_b}, "
            f"got {returned_session_wcs_b}"
        )


# ── Property 6: Read-only users cannot modify progress ────────


# Strategy for generating PATCH payloads that a read-only user might attempt
patch_payload = st.fixed_dictionaries(
    {},
    optional={
        "daily_target": valid_target,
        "session_target": valid_target,
        "manuscript_target": valid_target,
        "ranking_visibility": st.sampled_from(["owner", "coauthors", "all"]),
    },
).filter(lambda d: len(d) > 0)  # at least one field


class ReadOnlyUsersCannotModifyProgressPropertyTest(TestCase):
    """
    Property 6: Read-only users cannot modify progress.

    For any read-only user on a project, and any PATCH payload (target updates)
    or POST payload (session reset), the Progress_Service should reject the
    request with a 403 status code, and no UserProgressSettings,
    SessionWordCount, or Project.settings values should be modified.

    # Feature: per-user-progress-tracking, Property 6: Read-only users cannot modify progress
    **Validates: Requirements 6.4**
    """

    @given(payload=patch_payload)
    @settings(max_examples=20, deadline=None)
    def test_readonly_user_patch_rejected(self, payload):
        """
        PATCH with any combination of target/toggle fields from a read-only
        user should return 403 and leave all data unchanged.

        # Feature: per-user-progress-tracking, Property 6: Read-only users cannot modify progress
        # **Validates: Requirements 6.4**
        """
        from api.models import SessionWordCount, UserProgressSettings

        owner = _make_user("owner")
        project = Project.objects.create(owner=owner, title="Test Project")
        readonly_user = _make_user("readonly")
        ProjectShare.objects.create(
            project=project, user=readonly_user, role="read-only",
        )

        # Snapshot state before the request
        settings_before = dict(project.settings or {})
        ups_count_before = UserProgressSettings.objects.filter(
            project=project,
        ).count()
        swc_count_before = SessionWordCount.objects.filter(
            project=project,
        ).count()

        client = _auth_client(readonly_user)
        resp = client.patch(
            f"/api/projects/{project.pk}/progress/",
            data=payload,
            format="json",
        )

        assert resp.status_code == 403, (
            f"Expected 403 for read-only PATCH, got {resp.status_code}: {resp.data}"
        )

        # Verify no data was modified
        project.refresh_from_db()
        assert dict(project.settings or {}) == settings_before, (
            f"Project.settings changed after read-only PATCH: "
            f"before={settings_before}, after={project.settings}"
        )

        ups_count_after = UserProgressSettings.objects.filter(
            project=project,
        ).count()
        assert ups_count_after == ups_count_before, (
            f"UserProgressSettings records changed: "
            f"before={ups_count_before}, after={ups_count_after}"
        )

        swc_count_after = SessionWordCount.objects.filter(
            project=project,
        ).count()
        assert swc_count_after == swc_count_before, (
            f"SessionWordCount records changed: "
            f"before={swc_count_before}, after={swc_count_after}"
        )

    @given(data=st.data())
    @settings(max_examples=20, deadline=None)
    def test_readonly_user_post_reset_rejected(self, data):
        """
        POST with action=reset_session from a read-only user should return
        403 and leave all data unchanged.

        # Feature: per-user-progress-tracking, Property 6: Read-only users cannot modify progress
        # **Validates: Requirements 6.4**
        """
        from api.models import SessionWordCount, UserProgressSettings

        owner = _make_user("owner")
        project = Project.objects.create(owner=owner, title="Test Project")
        readonly_user = _make_user("readonly")
        ProjectShare.objects.create(
            project=project, user=readonly_user, role="read-only",
        )

        # Snapshot state before the request
        settings_before = dict(project.settings or {})
        ups_count_before = UserProgressSettings.objects.filter(
            project=project,
        ).count()
        swc_count_before = SessionWordCount.objects.filter(
            project=project,
        ).count()

        client = _auth_client(readonly_user)
        resp = client.post(
            f"/api/projects/{project.pk}/progress/",
            data={"action": "reset_session"},
            format="json",
        )

        assert resp.status_code == 403, (
            f"Expected 403 for read-only POST reset, got {resp.status_code}: {resp.data}"
        )

        # Verify no data was modified
        project.refresh_from_db()
        assert dict(project.settings or {}) == settings_before, (
            f"Project.settings changed after read-only POST: "
            f"before={settings_before}, after={project.settings}"
        )

        ups_count_after = UserProgressSettings.objects.filter(
            project=project,
        ).count()
        assert ups_count_after == ups_count_before, (
            f"UserProgressSettings records changed: "
            f"before={ups_count_before}, after={ups_count_after}"
        )

        swc_count_after = SessionWordCount.objects.filter(
            project=project,
        ).count()
        assert swc_count_after == swc_count_before, (
            f"SessionWordCount records changed: "
            f"before={swc_count_before}, after={swc_count_after}"
        )

# ── Property 7: Contribution ranking correctness ──────────────


class ContributionRankingCorrectnessPropertyTest(TestCase):
    """
    Property 7: Contribution ranking correctness.

    For any project with DailyWordCount records for multiple users, the
    contribution_ranking returned by the Progress_Service should list each
    participant with a total_word_count equal to the sum of that user's
    DailyWordCount.word_count values for the project, and the list should
    be sorted in descending order by total_word_count.

    # Feature: per-user-progress-tracking, Property 7: Contribution ranking correctness
    **Validates: Requirements 7.2, 7.3**
    """

    @given(
        word_counts_by_user=st.lists(
            st.lists(
                st.integers(min_value=-5_000, max_value=10_000),
                min_size=1,
                max_size=5,
            ),
            min_size=2,
            max_size=4,
        ),
    )
    @settings(max_examples=20, deadline=None)
    def test_contribution_ranking_correctness(self, word_counts_by_user):
        """
        Create DailyWordCount records for multiple co-authors with random
        word counts, GET progress as the owner, and verify that
        contribution_ranking totals match the sum of each user's
        DailyWordCount records and are sorted descending.

        # Feature: per-user-progress-tracking, Property 7: Contribution ranking correctness
        # **Validates: Requirements 7.2, 7.3**
        """
        import datetime

        from api.models import DailyWordCount

        # Create owner and project
        owner = _make_user("owner")
        project = Project.objects.create(owner=owner, title="Test Project")

        # Create co-author users
        coauthors = []
        for i in range(len(word_counts_by_user)):
            u = _make_user(f"coauthor{i}")
            ProjectShare.objects.create(
                project=project, user=u, role="co-author",
            )
            coauthors.append(u)

        # Build expected totals per user from the generated word counts
        # and create DailyWordCount records
        expected_totals = {}  # user_id -> total
        for user_idx, wc_list in enumerate(word_counts_by_user):
            user = coauthors[user_idx]
            total = 0
            for day_idx, wc in enumerate(wc_list):
                # Use distinct months per user to avoid unique constraint clashes
                month = (user_idx % 11) + 1  # months 1-11
                day = day_idx + 1
                DailyWordCount.objects.create(
                    project=project,
                    user=user,
                    date=datetime.date(2024, month, day),
                    word_count=wc,
                )
                total += wc
            expected_totals[user.pk] = total

        # GET progress as the owner — the owner always sees contribution_ranking
        client = _auth_client(owner)
        resp = client.get(f"/api/projects/{project.pk}/progress/")
        assert resp.status_code == 200, (
            f"GET failed: {resp.status_code}: {resp.data}"
        )

        ranking = resp.data.get("contribution_ranking")
        assert ranking is not None, (
            "contribution_ranking missing from owner GET response"
        )

        # The GET handler upserts a DailyWordCount for "today" for the
        # requesting user (the owner). The owner has no pre-seeded records,
        # so the ranking may include an extra entry for the owner with
        # today's word count. We account for this by separating the owner's
        # entry from the co-author entries.

        ranking_by_user = {r["user_id"]: r for r in ranking}

        # Verify each co-author's total matches the sum of their DailyWordCount records
        for user in coauthors:
            uid = user.pk
            assert uid in ranking_by_user, (
                f"User {user.username} (id={uid}) missing from ranking"
            )
            actual_total = ranking_by_user[uid]["total_word_count"]
            assert actual_total == expected_totals[uid], (
                f"User {user.username}: expected total {expected_totals[uid]}, "
                f"got {actual_total}"
            )

        # Verify the ranking is sorted in descending order by total_word_count
        totals_in_order = [r["total_word_count"] for r in ranking]
        assert totals_in_order == sorted(totals_in_order, reverse=True), (
            f"Ranking not sorted descending: {totals_in_order}"
        )


# ── Property 8: Ranking visibility respects settings ──────────

# The three visibility levels
ranking_visibility_level = st.sampled_from(["owner", "coauthors", "all"])


class RankingVisibilityRespectsSettingsPropertyTest(TestCase):
    """
    Property 8: Ranking visibility respects settings.

    For any project with a ranking_visibility setting ("owner", "coauthors",
    or "all"), the contribution_ranking field should be present in the GET
    response if and only if: (a) the requesting user is the owner, OR
    (b) the requesting user is a co-author and visibility is "coauthors"
    or "all", OR (c) the requesting user is a read-only user and visibility
    is "all".

    # Feature: per-user-progress-tracking, Property 8: Ranking visibility respects toggle settings
    **Validates: Requirements 8.2, 8.3, 8.4, 8.5, 10.3**
    """

    @given(visibility=ranking_visibility_level)
    @settings(max_examples=20, deadline=None)
    def test_ranking_visibility_respects_settings(self, visibility):
        """
        Set ranking_visibility via PATCH as the owner, then GET progress as
        owner, co-author, and read-only user. Assert that contribution_ranking
        is present/absent according to the visibility rules.

        # Feature: per-user-progress-tracking, Property 8: Ranking visibility respects toggle settings
        # **Validates: Requirements 8.2, 8.3, 8.4, 8.5, 10.3**
        """
        owner = _make_user("owner")
        project = Project.objects.create(owner=owner, title="Test Project")

        coauthor = _make_user("coauthor")
        ProjectShare.objects.create(
            project=project, user=coauthor, role="co-author",
        )

        readonly_user = _make_user("readonly")
        ProjectShare.objects.create(
            project=project, user=readonly_user, role="read-only",
        )

        # Owner sets the ranking visibility
        owner_client = _auth_client(owner)
        patch_resp = owner_client.patch(
            f"/api/projects/{project.pk}/progress/",
            data={"ranking_visibility": visibility},
            format="json",
        )
        assert patch_resp.status_code == 200, (
            f"PATCH visibility failed: {patch_resp.status_code}: {patch_resp.data}"
        )

        # --- Owner always sees contribution_ranking ---
        owner_get = owner_client.get(f"/api/projects/{project.pk}/progress/")
        assert owner_get.status_code == 200
        assert "contribution_ranking" in owner_get.data, (
            f"Owner should ALWAYS see contribution_ranking (visibility={visibility})"
        )

        # --- Co-author sees ranking when visibility is "coauthors" or "all" ---
        coauthor_client = _auth_client(coauthor)
        coauthor_get = coauthor_client.get(f"/api/projects/{project.pk}/progress/")
        assert coauthor_get.status_code == 200

        if visibility in ("coauthors", "all"):
            assert "contribution_ranking" in coauthor_get.data, (
                f"Co-author should see ranking when visibility={visibility}"
            )
        else:
            assert "contribution_ranking" not in coauthor_get.data, (
                f"Co-author should NOT see ranking when visibility={visibility}"
            )

        # --- Read-only user sees ranking only when visibility is "all" ---
        readonly_client = _auth_client(readonly_user)
        readonly_get = readonly_client.get(f"/api/projects/{project.pk}/progress/")
        assert readonly_get.status_code == 200

        if visibility == "all":
            assert "contribution_ranking" in readonly_get.data, (
                f"Read-only should see ranking when visibility={visibility}"
            )
        else:
            assert "contribution_ranking" not in readonly_get.data, (
                f"Read-only should NOT see ranking when visibility={visibility}"
            )
