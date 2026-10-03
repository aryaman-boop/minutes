import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


@pytest.mark.django_db(transaction=True)
def test_status_data_migration_converts_legacy_done_rows():
    executor = MigrationExecutor(connection)
    old_target = [("meetings", "0001_initial")]
    new_target = [("meetings", "0002_action_item_status")]
    executor.migrate(old_target)
    old_apps = executor.loader.project_state(old_target).apps
    Team = old_apps.get_model("meetings", "Team")
    Meeting = old_apps.get_model("meetings", "Meeting")
    ActionItem = old_apps.get_model("meetings", "ActionItem")
    user = get_user_model().objects.create_user(username="legacy")
    team = Team.objects.create(name="Legacy")
    meeting = Meeting.objects.create(
        team=team, title="Migration", scheduled_at="2026-01-01T00:00:00Z", created_by_id=user.pk
    )
    legacy_item = ActionItem.objects.create(
        meeting=meeting, title="Old task", owner_id=user.pk, done=True
    )
    executor = MigrationExecutor(connection)
    executor.migrate(new_target)
    new_apps = executor.loader.project_state(new_target).apps
    MigratedActionItem = new_apps.get_model("meetings", "ActionItem")
    assert MigratedActionItem.objects.get(pk=legacy_item.pk).status == "done"
