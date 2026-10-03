from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from meetings.models import (
    ActionItem,
    AgendaItem,
    Meeting,
    MeetingAttendee,
    Note,
    Team,
    TeamMembership,
)


class Command(BaseCommand):
    help = "Create a small demo team and meeting."

    def handle(self, *args: object, **options: object) -> None:
        user_model = get_user_model()
        owner, _ = user_model.objects.get_or_create(
            username="demo", defaults={"email": "demo@example.com"}
        )
        owner.set_password("demo")
        owner.save()
        team, _ = Team.objects.get_or_create(name="Demo Team")
        TeamMembership.objects.get_or_create(team=team, user=owner, defaults={"role": "admin"})
        meeting, created = Meeting.objects.get_or_create(
            team=team,
            title="Weekly planning",
            defaults={"scheduled_at": timezone.now(), "created_by": owner},
        )
        MeetingAttendee.objects.get_or_create(meeting=meeting, user=owner)
        if created:
            AgendaItem.objects.bulk_create(
                [
                    AgendaItem(meeting=meeting, position=1, title="Review last week"),
                    AgendaItem(meeting=meeting, position=2, title="Plan next steps"),
                ]
            )
            note = Note.objects.create(
                meeting=meeting, author=owner, body="Agree priorities and assign follow-ups."
            )
            ActionItem.objects.create(
                meeting=meeting,
                source_note=note,
                title="Publish the plan",
                owner=owner,
                due_date=(timezone.now() + timedelta(days=2)).date(),
            )
        self.stdout.write(
            self.style.SUCCESS("Demo ready. Sign in as demo/demo and open /graphql/.")
        )
