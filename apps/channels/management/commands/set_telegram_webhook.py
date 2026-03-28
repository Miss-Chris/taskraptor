import json

from django.core.management.base import BaseCommand, CommandError

from apps.channels.telegram import (
    TelegramApiError,
    TelegramConfigurationError,
    get_telegram_webhook_url,
    set_telegram_webhook,
)


class Command(BaseCommand):
    help = "Register the Telegram webhook with the configured public base URL."

    def handle(self, *args, **options):
        try:
            webhook_url = get_telegram_webhook_url()
            response = set_telegram_webhook()
        except TelegramConfigurationError as exc:
            raise CommandError(str(exc)) from exc
        except TelegramApiError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(f"Webhook URL: {webhook_url}")
        self.stdout.write(json.dumps(response))
