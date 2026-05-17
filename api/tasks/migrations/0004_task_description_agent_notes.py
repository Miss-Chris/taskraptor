from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("tasks", "0003_task_reminded_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="task",
            name="agent_notes",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="task",
            name="description",
            field=models.TextField(blank=True, null=True),
        ),
    ]
