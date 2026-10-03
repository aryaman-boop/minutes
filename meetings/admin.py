from django.contrib import admin

from .models import ActionItem, AgendaItem, Meeting, MeetingAttendee, Note, Team, TeamMembership


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    search_fields = ("name",)


@admin.register(TeamMembership)
class TeamMembershipAdmin(admin.ModelAdmin):
    list_filter = ("role", "team")
    search_fields = ("user__username", "team__name")


@admin.register(Meeting)
class MeetingAdmin(admin.ModelAdmin):
    list_filter = ("team", "scheduled_at")
    search_fields = ("title", "created_by__username")


@admin.register(MeetingAttendee)
class MeetingAttendeeAdmin(admin.ModelAdmin):
    list_filter = ("meeting",)
    search_fields = ("user__username", "meeting__title")


@admin.register(AgendaItem)
class AgendaItemAdmin(admin.ModelAdmin):
    list_filter = ("meeting",)
    search_fields = ("title",)


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_filter = ("meeting", "created_at")
    search_fields = ("body", "author__username")


@admin.register(ActionItem)
class ActionItemAdmin(admin.ModelAdmin):
    list_filter = ("status", "meeting", "due_date")
    search_fields = ("title", "owner__username")
