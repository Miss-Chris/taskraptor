from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0002_usertag"),
    ]

    operations = [
        migrations.AddField(
            model_name="task",
            name="reminded_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="taskauditlog",
            name="action",
            field=models.CharField(
                choices=[
                    ("status_changed", "Status changed"),
                    ("name_changed", "Name changed"),
                    ("priority_changed", "Priority changed"),
                    ("tags_changed", "Tags changed"),
                    ("reminder_changed", "Reminder changed"),
                    ("deleted", "Deleted"),
                ],
                max_length=32,
            ),
        ),
    ]
