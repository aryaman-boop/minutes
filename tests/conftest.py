import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from meetings.models import Meeting, Team, TeamMembership


@pytest.fixture
def users():
    user_model = get_user_model()
    owner = user_model.objects.create_user(username="owner", password="secret")
    member = user_model.objects.create_user(username="member", password="secret")
    outsider = user_model.objects.create_user(username="outsider", password="secret")
    return owner, member, outsider


@pytest.fixture
def meeting(users):
    owner, member, _ = users
    team = Team.objects.create(name="Product")
    TeamMembership.objects.create(team=team, user=owner, role="admin")
    TeamMembership.objects.create(team=team, user=member)
    return Meeting.objects.create(
        team=team, title="Planning", scheduled_at=timezone.now(), created_by=owner
    )


def graphql(client, query, variables=None):
    response = client.post(
        "/graphql/",
        data={"query": query, "variables": variables or {}},
        content_type="application/json",
    )
    return response.json()
