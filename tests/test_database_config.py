import pytest

from taskraptor.settings.base import postgres_database_config


def test_database_config_uses_database_url(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgres://task_user:secret%21@db.example.internal:6543/taskraptor_prod",
    )
    monkeypatch.setenv("PGDATABASE", "ignored")

    config = postgres_database_config(
        default_name="taskraptor",
        default_user="postgres",
        default_password="",
        default_host="localhost",
        default_port="5432",
    )

    assert config == {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "taskraptor_prod",
        "USER": "task_user",
        "PASSWORD": "secret!",
        "HOST": "db.example.internal",
        "PORT": "6543",
    }


def test_database_config_falls_back_to_pg_env_vars(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("PGDATABASE", "taskraptor")
    monkeypatch.setenv("PGUSER", "postgres")
    monkeypatch.setenv("PGPASSWORD", "pw")
    monkeypatch.setenv("PGHOST", "localhost")
    monkeypatch.setenv("PGPORT", "5432")

    config = postgres_database_config(
        default_name="fallback_name",
        default_user="fallback_user",
        default_password="fallback_password",
        default_host="fallback_host",
        default_port="9999",
    )

    assert config == {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "taskraptor",
        "USER": "postgres",
        "PASSWORD": "pw",
        "HOST": "localhost",
        "PORT": "5432",
    }


def test_database_config_rejects_non_postgres_database_url(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "mysql://user:pw@db.example.internal:3306/app")

    with pytest.raises(ValueError, match="DATABASE_URL must use postgres:// or postgresql://"):
        postgres_database_config(
            default_name="taskraptor",
            default_user="postgres",
            default_password="",
            default_host="localhost",
            default_port="5432",
        )
