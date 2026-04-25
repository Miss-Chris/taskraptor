from pathlib import Path

from decouple import Config, RepositoryEmpty, RepositoryEnv

ROOT_DIR = Path(__file__).resolve().parents[3]
ENV_FILE = ROOT_DIR / ".env"

config = Config(RepositoryEnv(ENV_FILE) if ENV_FILE.exists() else RepositoryEmpty())
