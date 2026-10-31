import os
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def database_path():
    return os.environ.get("CRMS_DATABASE", str(ROOT / "data" / "crms.db"))


def secret_key():
    if os.environ.get("CRMS_SECRET"):
        return os.environ["CRMS_SECRET"]
    key_file = ROOT / "data" / "secret.key"
    if not key_file.exists():
        key_file.parent.mkdir(exist_ok=True)
        key_file.write_text(secrets.token_hex(32))
    return key_file.read_text().strip()


def mongo_url():
    return os.environ.get("MONGO_URL", "mongodb://localhost:27017")


def mongo_name():
    return os.environ.get("MONGO_DB", "crms")
