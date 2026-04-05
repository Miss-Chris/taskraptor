from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("automations", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="automation",
            name="last_run_at",
            field=models.DateTimeField(
                blank=True,
                help_text="Most recent successful run timestamp in UTC.",
                null=True,
            ),
        ),
    ]
