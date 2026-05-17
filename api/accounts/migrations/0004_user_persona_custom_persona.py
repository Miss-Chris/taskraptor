from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_user_timezone_nullable"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="custom_persona",
            field=models.TextField(
                blank=True,
                default="",
                help_text="Custom response style instructions used when persona is custom.",
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="persona",
            field=models.CharField(
                choices=[
                    ("helpful", "Helpful"),
                    ("encouraging", "Encouraging"),
                    ("minimal", "Minimal"),
                    ("custom", "Custom"),
                ],
                default="helpful",
                help_text="Response style preset applied to this user's assistant runs.",
                max_length=16,
            ),
        ),
    ]
