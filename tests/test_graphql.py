import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from meetings.models import ActionItem, AgendaItem, Meeting, MeetingAttendee

from .conftest import graphql


@pytest.mark.django_db
def test_non_member_cannot_discover_meeting(client, meeting, users):
    client.login(username="outsider", password="secret")
    result = graphql(
        client, "query($id: ID!) { meeting(id: $id) { id title } }", {"id": str(meeting.pk)}
    )
    assert result == {"data": {"meeting": None}}


@pytest.mark.django_db
def test_action_status_returns_typed_validation_error(client, meeting, users):
    action = ActionItem.objects.create(meeting=meeting, title="Ship", owner=users[1])
    client.login(username="member", password="secret")
    result = graphql(
        client,
        'mutation($id: ID!) { updateActionItemStatus(actionItemId: $id, status: "invalid") '
        "{ __typename ... on ValidationError { field message } } }",
        {"id": str(action.pk)},
    )
    payload = result["data"]["updateActionItemStatus"]
    assert payload == {
        "__typename": "ValidationError",
        "field": "status",
        "message": "Status must be open, in_progress, or done.",
    }


@pytest.mark.django_db
def test_only_owner_or_creator_can_change_status(client, meeting, users):
    action = ActionItem.objects.create(meeting=meeting, title="Ship", owner=users[1])
    client.login(username="owner", password="secret")
    result = graphql(
        client,
        'mutation($id: ID!) { updateActionItemStatus(actionItemId: $id, status: "done") '
        "{ __typename ... on ActionItemType { status completedAt } } }",
        {"id": str(action.pk)},
    )
    payload = result["data"]["updateActionItemStatus"]
    assert payload["__typename"] == "ActionItemType"
    assert payload["status"] == "done"
    assert payload["completedAt"] is not None


@pytest.mark.django_db
def test_reorder_keeps_positions_unique(client, meeting, users):
    first = AgendaItem.objects.create(meeting=meeting, position=1, title="First")
    second = AgendaItem.objects.create(meeting=meeting, position=2, title="Second")
    client.login(username="owner", password="secret")
    result = graphql(
        client,
        "mutation($meeting: ID!, $items: [ID!]!) { reorderAgendaItems("
        "meetingId: $meeting, agendaItemIds: $items) { __typename } }",
        {"meeting": str(meeting.pk), "items": [str(second.pk), str(first.pk)]},
    )
    assert result == {"data": {"reorderAgendaItems": {"__typename": "MeetingType"}}}
    assert list(meeting.agenda_items.values_list("position", flat=True)) == [1, 2]


@pytest.mark.django_db
def test_nested_meeting_query_has_constant_query_count(client, meeting, users):
    owner, member, _ = users
    for number in range(9):
        current = Meeting.objects.create(
            team=meeting.team,
            title=f"Meeting {number}",
            scheduled_at=timezone.now(),
            created_by=owner,
        )
        MeetingAttendee.objects.create(meeting=current, user=member)
        ActionItem.objects.create(meeting=current, title="Follow up", owner=member)
    client.login(username="owner", password="secret")
    query = (
        "{ meetings(first: 100) { nodes { attendees { username } "
        "actionItems { owner { username } } } } }"
    )
    with CaptureQueriesContext(connection) as queries:
        result = graphql(client, query)
    assert "errors" not in result
    ten_meeting_query_count = len(queries)
    for number in range(9, 99):
        current = Meeting.objects.create(
            team=meeting.team,
            title=f"Meeting {number}",
            scheduled_at=timezone.now(),
            created_by=owner,
        )
        MeetingAttendee.objects.create(meeting=current, user=member)
        ActionItem.objects.create(meeting=current, title="Follow up", owner=member)
    with CaptureQueriesContext(connection) as queries:
        result = graphql(client, query)
    assert "errors" not in result
    assert ten_meeting_query_count == len(queries) == 9


@pytest.mark.django_db
def test_anonymous_meetings_query_returns_empty_connection(client, meeting):
    # Regression: the membership filter received AnonymousUser and the response leaked
    # Django's "Field 'id' expected a number" error instead of an empty result.
    result = graphql(client, "{ meetings { nodes { id } pageInfo { hasNextPage endCursor } } }")
    assert result == {
        "data": {"meetings": {"nodes": [], "pageInfo": {"hasNextPage": False, "endCursor": None}}}
    }


@pytest.mark.django_db
def test_create_meeting_rejects_malformed_timestamp_with_typed_error(client, meeting, users):
    # Regression: Django raises django.core.exceptions.ValidationError for a malformed
    # datetime, which escaped as a top-level GraphQL error with an unformatted template.
    client.login(username="owner", password="secret")
    result = graphql(
        client,
        'mutation($team: ID!) { createMeeting(teamId: $team, title: "Sync", '
        'scheduledAt: "not-a-date") { __typename ... on ValidationError { field message } } }',
        {"team": str(meeting.team_id)},
    )
    assert result == {
        "data": {
            "createMeeting": {
                "__typename": "ValidationError",
                "field": "scheduledAt",
                "message": "Use an ISO-8601 timestamp.",
            }
        }
    }
    assert not Meeting.objects.filter(title="Sync").exists()
