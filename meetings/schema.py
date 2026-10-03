import base64
from datetime import date
from typing import Annotated

import strawberry
from django.contrib.auth.models import AnonymousUser
from django.db import transaction
from django.db.models import Case, IntegerField, Value, When
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from strawberry import ID
from strawberry.extensions import QueryDepthLimiter
from strawberry.types import Info

from .models import ActionItem, Meeting, Note, TeamMembership


def current_user(info: Info) -> object:
    return getattr(info.context.request, "user", AnonymousUser())


def is_member(user: object, team_id: int) -> bool:
    return (
        bool(getattr(user, "is_authenticated", False))
        and TeamMembership.objects.filter(team_id=team_id, user=user).exists()
    )


def can_access_meeting(user: object, meeting: Meeting) -> bool:
    return is_member(user, meeting.team_id)


@strawberry.type
class UserType:
    id: ID
    username: str


@strawberry.type
class AgendaItemType:
    id: ID
    position: int
    title: str


@strawberry.type
class NoteType:
    id: ID
    body: str
    created_at: str
    author: UserType


@strawberry.type
class ActionItemType:
    id: ID
    title: str
    due_date: date | None
    status: str
    completed_at: str | None
    owner: UserType


@strawberry.type
class MeetingType:
    id: ID
    title: str
    scheduled_at: str
    created_by: UserType
    attendees: list[UserType]
    agenda_items: list[AgendaItemType]
    notes: list[NoteType]
    action_items: list[ActionItemType]


def user_type(user: object) -> UserType:
    return UserType(id=ID(str(user.pk)), username=user.username)  # type: ignore[attr-defined,no-any-return]


def action_item_type(item: ActionItem) -> ActionItemType:
    return ActionItemType(
        id=ID(str(item.pk)),
        title=item.title,
        due_date=item.due_date,
        status=item.status,
        completed_at=item.completed_at.isoformat() if item.completed_at else None,
        owner=user_type(item.owner),
    )


def meeting_type(meeting: Meeting) -> MeetingType:
    return MeetingType(
        id=ID(str(meeting.pk)),
        title=meeting.title,
        scheduled_at=meeting.scheduled_at.isoformat(),
        created_by=user_type(meeting.created_by),
        attendees=[user_type(attendee.user) for attendee in meeting.meeting_attendees.all()],
        agenda_items=[
            AgendaItemType(id=ID(str(item.pk)), position=item.position, title=item.title)
            for item in meeting.agenda_items.all()
        ],
        notes=[
            NoteType(
                id=ID(str(note.pk)),
                body=note.body,
                created_at=note.created_at.isoformat(),
                author=user_type(note.author),
            )
            for note in meeting.notes.all()
        ],
        action_items=[action_item_type(item) for item in meeting.action_items.all()],
    )


def meeting_queryset():
    return Meeting.objects.select_related("created_by").prefetch_related(
        "agenda_items", "meeting_attendees__user", "notes__author", "action_items__owner"
    )


@strawberry.type
class ValidationError:
    field: str
    message: str


@strawberry.type
class PermissionDenied:
    message: str


ActionItemResult = Annotated[
    ActionItemType | ValidationError | PermissionDenied, strawberry.union("ActionItemResult")
]
MeetingResult = Annotated[
    MeetingType | ValidationError | PermissionDenied, strawberry.union("MeetingResult")
]
NoteResult = Annotated[
    NoteType | ValidationError | PermissionDenied, strawberry.union("NoteResult")
]


@strawberry.input
class MeetingFilters:
    team_id: ID | None = None
    scheduled_before: str | None = None


@strawberry.type
class PageInfo:
    has_next_page: bool
    end_cursor: str | None


@strawberry.type
class MeetingConnection:
    nodes: list[MeetingType]
    page_info: PageInfo


def encode_cursor(value: int) -> str:
    return base64.b64encode(str(value).encode()).decode()


def decode_cursor(cursor: str | None) -> int:
    if not cursor:
        return 0
    try:
        return int(base64.b64decode(cursor).decode())
    except (ValueError, UnicodeDecodeError):
        return 0


@strawberry.type
class Query:
    @strawberry.field
    def me(self, info: Info) -> UserType | None:
        user = current_user(info)
        return user_type(user) if getattr(user, "is_authenticated", False) else None

    @strawberry.field
    def meeting(self, info: Info, id: ID) -> MeetingType | None:
        meeting = meeting_queryset().filter(pk=id).first()
        if meeting is None or not can_access_meeting(current_user(info), meeting):
            return None
        return meeting_type(meeting)

    @strawberry.field
    def meetings(
        self,
        info: Info,
        filters: MeetingFilters | None = None,
        first: int = 20,
        after: str | None = None,
    ) -> MeetingConnection:
        user = current_user(info)
        if not getattr(user, "is_authenticated", False):
            return MeetingConnection(
                nodes=[], page_info=PageInfo(has_next_page=False, end_cursor=None)
            )
        queryset = meeting_queryset().filter(team__memberships__user=user).distinct().order_by("pk")
        if filters and filters.team_id:
            queryset = queryset.filter(team_id=filters.team_id)
        if filters and filters.scheduled_before:
            queryset = queryset.filter(scheduled_at__lt=filters.scheduled_before)
        queryset = queryset.filter(pk__gt=decode_cursor(after))
        rows = list(queryset[: min(first, 100) + 1])
        has_next_page = len(rows) > min(first, 100)
        rows = rows[: min(first, 100)]
        return MeetingConnection(
            nodes=[meeting_type(row) for row in rows],
            page_info=PageInfo(
                has_next_page=has_next_page, end_cursor=encode_cursor(rows[-1].pk) if rows else None
            ),
        )

    @strawberry.field
    def my_action_items(
        self, info: Info, status: str | None = None, due_before: date | None = None
    ) -> list[ActionItemType]:
        user = current_user(info)
        if not getattr(user, "is_authenticated", False):
            return []
        queryset = ActionItem.objects.filter(owner=user).select_related("owner")
        if status:
            queryset = queryset.filter(status=status)
        if due_before:
            queryset = queryset.filter(due_date__lt=due_before)
        return [action_item_type(item) for item in queryset.order_by("due_date", "pk")]


@strawberry.type
class Mutation:
    @strawberry.mutation
    def create_meeting(
        self, info: Info, team_id: ID, title: str, scheduled_at: str
    ) -> MeetingResult:
        user = current_user(info)
        if not is_member(user, int(team_id)):
            return PermissionDenied(message="You are not a member of this team.")
        if not title.strip():
            return ValidationError(field="title", message="Title cannot be blank.")
        # Parse before touching the ORM: Django reports a malformed datetime with its own
        # ValidationError at save time, which would escape as an untyped GraphQL error.
        try:
            parsed = parse_datetime(scheduled_at)
        except ValueError:
            parsed = None
        if parsed is None:
            return ValidationError(field="scheduledAt", message="Use an ISO-8601 timestamp.")
        if timezone.is_naive(parsed):
            parsed = timezone.make_aware(parsed)
        meeting = Meeting.objects.create(
            team_id=team_id, title=title.strip(), scheduled_at=parsed, created_by=user
        )
        meeting = meeting_queryset().get(pk=meeting.pk)
        return meeting_type(meeting)

    @strawberry.mutation
    def add_note(self, info: Info, meeting_id: ID, body: str) -> NoteResult:
        meeting = Meeting.objects.filter(pk=meeting_id).first()
        user = current_user(info)
        if meeting is None or not can_access_meeting(user, meeting):
            return PermissionDenied(message="Meeting not found.")
        if not body.strip():
            return ValidationError(field="body", message="Note body cannot be blank.")
        note = Note.objects.create(meeting=meeting, author=user, body=body.strip())
        return NoteType(
            id=ID(str(note.pk)),
            body=note.body,
            created_at=note.created_at.isoformat(),
            author=user_type(user),
        )

    @strawberry.mutation
    def create_action_item(
        self,
        info: Info,
        meeting_id: ID,
        title: str,
        owner_id: ID,
        due_date: date | None = None,
        source_note_id: ID | None = None,
    ) -> ActionItemResult:
        meeting = Meeting.objects.filter(pk=meeting_id).first()
        user = current_user(info)
        if meeting is None or not can_access_meeting(user, meeting):
            return PermissionDenied(message="Meeting not found.")
        if not title.strip():
            return ValidationError(field="title", message="Title cannot be blank.")
        if not TeamMembership.objects.filter(team=meeting.team, user_id=owner_id).exists():
            return ValidationError(field="ownerId", message="Owner must be a team member.")
        if source_note_id and not Note.objects.filter(pk=source_note_id, meeting=meeting).exists():
            return ValidationError(
                field="sourceNoteId", message="Note does not belong to this meeting."
            )
        item = ActionItem.objects.create(
            meeting=meeting,
            title=title.strip(),
            owner_id=owner_id,
            due_date=due_date,
            source_note_id=source_note_id,
        )
        item = ActionItem.objects.select_related("owner").get(pk=item.pk)
        return action_item_type(item)

    @strawberry.mutation
    def update_action_item_status(
        self, info: Info, action_item_id: ID, status: str
    ) -> ActionItemResult:
        item = (
            ActionItem.objects.select_related("meeting", "owner").filter(pk=action_item_id).first()
        )
        user = current_user(info)
        if item is None or not can_access_meeting(user, item.meeting):
            return PermissionDenied(message="Action item not found.")
        if user.pk not in {item.owner_id, item.meeting.created_by_id}:
            return PermissionDenied(
                message="Only the owner or meeting creator can change this action item."
            )
        if status not in ActionItem.Status.values:
            return ValidationError(
                field="status", message="Status must be open, in_progress, or done."
            )
        item.status = status
        item.completed_at = timezone.now() if status == ActionItem.Status.DONE else None
        item.save(update_fields=["status", "completed_at"])
        return action_item_type(item)

    @strawberry.mutation
    def reorder_agenda_items(
        self, info: Info, meeting_id: ID, agenda_item_ids: list[ID]
    ) -> MeetingResult:
        meeting = Meeting.objects.filter(pk=meeting_id).first()
        user = current_user(info)
        if meeting is None or not can_access_meeting(user, meeting):
            return PermissionDenied(message="Meeting not found.")
        existing_ids = list(meeting.agenda_items.values_list("pk", flat=True))
        requested_ids = [int(item_id) for item_id in agenda_item_ids]
        if len(requested_ids) != len(set(requested_ids)) or set(existing_ids) != set(requested_ids):
            return ValidationError(
                field="agendaItemIds", message="Provide every agenda item exactly once."
            )
        with transaction.atomic():
            meeting.agenda_items.update(
                position=Case(
                    *[
                        When(pk=item_id, then=Value(10_000 + index))
                        for index, item_id in enumerate(requested_ids)
                    ],
                    output_field=IntegerField(),
                )
            )
            meeting.agenda_items.update(
                position=Case(
                    *[
                        When(pk=item_id, then=Value(index + 1))
                        for index, item_id in enumerate(requested_ids)
                    ],
                    output_field=IntegerField(),
                )
            )
        return meeting_type(meeting_queryset().get(pk=meeting.pk))


schema = strawberry.Schema(
    query=Query, mutation=Mutation, extensions=[lambda: QueryDepthLimiter(max_depth=8)]
)
