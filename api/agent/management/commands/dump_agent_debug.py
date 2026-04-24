from __future__ import annotations

import json
from uuid import UUID

from django.core.management.base import BaseCommand, CommandError

from accounts.models import User
from agent.debug import conversation_debug_bundle, render_debug_markdown
from channels.models import Conversation


class Command(BaseCommand):
    help = "Dump a redacted, user-scoped agent conversation debug snapshot."

    def add_arguments(self, parser):
        parser.add_argument("--user-email", required=True)
        parser.add_argument("--conversation-id", required=True)
        parser.add_argument("--run-id")
        parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
        parser.add_argument("--output")
        parser.add_argument("--limit", type=int, default=500)

    def handle(self, *args, **options):
        email = options["user_email"]
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist as exc:
            raise CommandError(f"User not found: {email}") from exc

        try:
            conversation_id = UUID(options["conversation_id"])
        except ValueError as exc:
            raise CommandError("Invalid --conversation-id UUID") from exc

        run_id = None
        if options.get("run_id"):
            try:
                run_id = UUID(options["run_id"])
            except ValueError as exc:
                raise CommandError("Invalid --run-id UUID") from exc

        try:
            bundle = conversation_debug_bundle(
                user,
                conversation_id,
                run_id=run_id,
                limit=max(1, min(options["limit"], 5000)),
            )
        except Conversation.DoesNotExist as exc:
            raise CommandError("Conversation not found for user.") from exc

        if run_id is not None and not bundle["agent_runs"]:
            raise CommandError("Agent run not found for user conversation.")

        if options["format"] == "json":
            output = json.dumps(bundle, indent=2, ensure_ascii=False)
        else:
            output = render_debug_markdown(bundle)

        output_path = options.get("output")
        if output_path:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(output)
                f.write("\n")
        else:
            self.stdout.write(output)
