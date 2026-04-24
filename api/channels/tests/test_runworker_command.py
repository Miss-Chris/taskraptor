import sys
from types import SimpleNamespace

import pytest

from channels.management.commands.runworker import API_ROOT, Command


def test_handle_uses_django_autoreloader(monkeypatch):
    command = Command()
    captured = {}

    def fake_run_with_reloader(callback, **options):
        captured["callback"] = callback
        captured["options"] = options

    monkeypatch.setattr(
        "channels.management.commands.runworker.autoreload.run_with_reloader",
        fake_run_with_reloader,
    )

    command.handle(loglevel="debug")

    assert captured == {"callback": command.run_worker, "options": {"loglevel": "debug"}}


def test_build_worker_command_uses_current_python():
    command = Command()

    assert command.build_worker_command(loglevel="warning") == [
        sys.executable,
        "-m",
        "celery",
        "-A",
        "taskraptor",
        "worker",
        "--loglevel=warning",
    ]


def test_run_worker_starts_celery_from_api_root(monkeypatch):
    command = Command()
    popen_calls = {}

    class FakeProcess:
        pid = 123

        def wait(self, timeout=None):
            return 0

        def poll(self):
            return 0

    def fake_popen(command_args, cwd, start_new_session):
        popen_calls["command_args"] = command_args
        popen_calls["cwd"] = cwd
        popen_calls["start_new_session"] = start_new_session
        return FakeProcess()

    monkeypatch.setattr("channels.management.commands.runworker.subprocess.Popen", fake_popen)
    monkeypatch.setattr("channels.management.commands.runworker.atexit.register", lambda *args: None)

    command.run_worker(loglevel="info")

    assert popen_calls == {
        "command_args": command.build_worker_command(loglevel="info"),
        "cwd": API_ROOT,
        "start_new_session": sys.platform != "win32",
    }


@pytest.mark.parametrize("os_name", ["posix", "nt"])
def test_stop_worker_terminates_process(monkeypatch, os_name):
    command = Command()
    calls = []

    process = SimpleNamespace(
        pid=321,
        poll=lambda: None,
        wait=lambda timeout=None: 0,
        terminate=lambda: calls.append(("terminate",)),
        kill=lambda: calls.append(("kill",)),
    )

    monkeypatch.setattr("channels.management.commands.runworker.os.name", os_name)
    monkeypatch.setattr(
        "channels.management.commands.runworker.os.killpg",
        lambda pid, sig: calls.append(("killpg", pid, sig)),
    )

    command.stop_worker(process)

    if os_name == "nt":
        assert calls == [("terminate",)]
    else:
        assert calls == [("killpg", 321, 15)]
