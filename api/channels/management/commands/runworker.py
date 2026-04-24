import atexit
import os
import signal
import subprocess
import sys
from pathlib import Path

from django.core.management.base import BaseCommand
from django.utils import autoreload


API_ROOT = Path(__file__).resolve().parents[3]


class Command(BaseCommand):
    help = "Run the Celery worker with Django's auto-reloader."

    def add_arguments(self, parser):
        parser.add_argument(
            "--loglevel",
            default="info",
            help="Celery worker log level (default: info).",
        )

    def handle(self, *args, **options):
        autoreload.run_with_reloader(self.run_worker, **options)

    def run_worker(self, **options):
        command = self.build_worker_command(loglevel=options["loglevel"])
        self.stdout.write(
            self.style.SUCCESS(
                f"Starting Celery worker with auto-reload: {' '.join(command)}"
            )
        )

        worker = subprocess.Popen(
            command,
            cwd=API_ROOT,
            start_new_session=os.name != "nt",
        )
        atexit.register(self.stop_worker, worker)

        return_code = worker.wait()
        if return_code:
            raise SystemExit(return_code)

    def build_worker_command(self, *, loglevel):
        return [
            sys.executable,
            "-m",
            "celery",
            "-A",
            "taskraptor",
            "worker",
            f"--loglevel={loglevel}",
        ]

    def stop_worker(self, worker):
        if worker.poll() is not None:
            return

        if os.name != "nt":
            os.killpg(worker.pid, signal.SIGTERM)
        else:
            worker.terminate()

        try:
            worker.wait(timeout=10)
        except subprocess.TimeoutExpired:
            if os.name != "nt":
                os.killpg(worker.pid, signal.SIGKILL)
            else:
                worker.kill()
