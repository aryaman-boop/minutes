from django.conf import settings
from django.db import models
from django.db.models import Q


class Team(models.Model):
    name = models.CharField(max_length=120)

    def __str__(self) -> str:
        return self.name


class TeamMembership(models.Model):
    class Role(models.TextChoices):
        MEMBER = "member", "Member"
        ADMIN = "admin", "Admin"

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="team_memberships"
    )
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.MEMBER)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["team", "user"], name="unique_team_member")]

    def __str__(self) -> str:
        return f"{self.user} in {self.team}"


class Meeting(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="meetings")
    title = models.CharField(max_length=200)
    scheduled_at = models.DateTimeField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_meetings"
    )
    attendees = models.ManyToManyField(
        settings.AUTH_USER_MODEL, through="MeetingAttendee", related_name="attending_meetings"
    )

    def __str__(self) -> str:
        return self.title


class MeetingAttendee(models.Model):
    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name="meeting_attendees")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["meeting", "user"], name="unique_meeting_attendee")
        ]


class AgendaItem(models.Model):
    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name="agenda_items")
    position = models.PositiveIntegerField()
    title = models.CharField(max_length=250)

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(fields=["meeting", "position"], name="unique_agenda_position")
        ]


class Note(models.Model):
    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name="notes")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="meeting_notes"
    )
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["meeting", "created_at"], name="meetings_no_meeting_7d7d94_idx")
        ]


class ActionItem(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In progress"
        DONE = "done", "Done"

    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name="action_items")
    source_note = models.ForeignKey(
        Note, on_delete=models.SET_NULL, null=True, blank=True, related_name="action_items"
    )
    title = models.CharField(max_length=250)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="action_items"
    )
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.OPEN)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["owner", "status"], name="meetings_ac_owner_i_18c38f_idx")]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(status="done", completed_at__isnull=False)
                    | (~Q(status="done") & Q(completed_at__isnull=True))
                ),
                name="action_item_completion_matches_status",
            )
        ]
