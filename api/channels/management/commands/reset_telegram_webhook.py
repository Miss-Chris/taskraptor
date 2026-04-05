from django.core.management.base import BaseCommand

from channels.telegram import set_telegram_webhook


class Command(BaseCommand):
    help = (
        "Register the TaskRaptor Telegram webhook URL with Telegram (setWebhook). "
        "Uses TELEGRAM_BOT_TOKEN and TELEGRAM_WEBHOOK_BASE_URL from settings."
    )

    def handle(self, *args, **options):
        try:
            result = set_telegram_webhook()
        except RuntimeError as exc:
            self.stderr.write(self.style.ERROR(str(exc)))
            raise SystemExit(1) from exc

        self.stdout.write(self.style.SUCCESS("Telegram setWebhook OK."))
        self.stdout.write(str(result))
