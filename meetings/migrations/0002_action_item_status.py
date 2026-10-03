from django.db import migrations, models
from django.db.models import Q
from django.utils import timezone


def convert_done_to_status(apps, schema_editor):
    ActionItem = apps.get_model("meetings", "ActionItem")
    ActionItem.objects.filter(done=True).update(status="done", completed_at=timezone.now())


def convert_status_to_done(apps, schema_editor):
    ActionItem = apps.get_model("meetings", "ActionItem")
    ActionItem.objects.filter(status="done").update(done=True)


class Migration(migrations.Migration):
    dependencies = [("meetings", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="actionitem",
            name="status",
            field=models.CharField(
                choices=[("open", "Open"), ("in_progress", "In progress"), ("done", "Done")],
                default="open",
                max_length=15,
            ),
        ),
        migrations.AddField(
            model_name="actionitem",
            name="completed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(convert_done_to_status, convert_status_to_done),
        migrations.RemoveField(model_name="actionitem", name="done"),
        migrations.AddIndex(
            model_name="actionitem",
            index=models.Index(fields=["owner", "status"], name="meetings_ac_owner_i_18c38f_idx"),
        ),
        migrations.AddConstraint(
            model_name="actionitem",
            constraint=models.CheckConstraint(
                condition=(
                    Q(status="done", completed_at__isnull=False)
                    | (~Q(status="done") & Q(completed_at__isnull=True))
                ),
                name="action_item_completion_matches_status",
            ),
        ),
    ]
