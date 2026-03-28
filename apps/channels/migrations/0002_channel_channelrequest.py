import apps.channels.models
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def migrate_telegram_channels(apps, schema_editor):
    TelegramChannel = apps.get_model("channels", "TelegramChannel")
    Channel = apps.get_model("channels", "Channel")
    ChannelRequest = apps.get_model("channels", "ChannelRequest")

    for telegram_channel in TelegramChannel.objects.all():
        request_status = "fulfilled" if telegram_channel.linked_at else "pending"
        fulfilled_at = telegram_channel.linked_at

        channel_request = ChannelRequest.objects.create(
            user_id=telegram_channel.user_id,
            channel_type="telegram",
            join_code=telegram_channel.join_code,
            status=request_status,
            fulfilled_at=fulfilled_at,
        )
        ChannelRequest.objects.filter(pk=channel_request.pk).update(created_at=telegram_channel.created_at)

        if telegram_channel.chat_id:
            channel, _ = Channel.objects.update_or_create(
                user_id=telegram_channel.user_id,
                channel_type="telegram",
                defaults={
                    "telegram_chat_id": telegram_channel.chat_id,
                    "connected_at": telegram_channel.linked_at or telegram_channel.created_at,
                },
            )
            Channel.objects.filter(pk=channel.pk).update(created_at=telegram_channel.created_at)


class Migration(migrations.Migration):

    dependencies = [
        ("channels", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Channel",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("channel_type", models.CharField(choices=[("telegram", "Telegram")], default="telegram", max_length=32)),
                ("telegram_chat_id", models.BigIntegerField(blank=True, null=True, unique=True)),
                ("telegram_username", models.CharField(blank=True, max_length=255, null=True)),
                ("connected_at", models.DateTimeField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="channels", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-created_at"],
                "constraints": [models.UniqueConstraint(fields=("user", "channel_type"), name="unique_channel_per_user_and_type")],
            },
        ),
        migrations.CreateModel(
            name="ChannelRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("channel_type", models.CharField(choices=[("telegram", "Telegram")], default="telegram", max_length=32)),
                ("join_code", models.CharField(default=apps.channels.models._generate_join_code, max_length=64, unique=True)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("fulfilled", "Fulfilled"), ("expired", "Expired")], default="pending", max_length=20)),
                ("fulfilled_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="channel_requests", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.RunPython(migrate_telegram_channels, migrations.RunPython.noop),
        migrations.DeleteModel(
            name="TelegramChannel",
        ),
    ]
