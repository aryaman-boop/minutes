import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from meetings.models import ActionItem, AgendaItem


@pytest.mark.django_db
def test_agenda_position_is_unique_per_meeting(meeting):
    AgendaItem.objects.create(meeting=meeting, position=1, title="First")
    with pytest.raises(IntegrityError):
        AgendaItem.objects.create(meeting=meeting, position=1, title="Duplicate")


@pytest.mark.django_db
def test_done_action_item_requires_completion_timestamp(meeting, users):
    with pytest.raises(IntegrityError), transaction.atomic():
        ActionItem.objects.create(meeting=meeting, title="Ship", owner=users[0], status="done")
    action = ActionItem.objects.create(
        meeting=meeting, title="Ship", owner=users[0], status="done", completed_at=timezone.now()
    )
    assert action.status == "done"
