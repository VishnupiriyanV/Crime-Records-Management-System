import os
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def database_url():
    """sqlite:///file.db, postgresql://user:pass@host/db or mysql://user:pass@host/db"""
    return os.environ.get("CRMS_DB_URL") or f"sqlite:///{ROOT / 'data' / 'crms.db'}"


def production():
    return os.environ.get("CRMS_ENV") == "production"


def secret_key():
    if os.environ.get("CRMS_SECRET"):
        return os.environ["CRMS_SECRET"]
    if production():
        raise RuntimeError("Set CRMS_SECRET to a long random string when CRMS_ENV=production.")
    key_file = ROOT / "data" / "secret.key"
    if not key_file.exists():
        key_file.parent.mkdir(exist_ok=True)
        key_file.write_text(secrets.token_hex(32))
    return key_file.read_text().strip()


def mongo_url():
    return os.environ.get("MONGO_URL", "mongodb://localhost:27017")


def mongo_name():
    return os.environ.get("MONGO_DB", "crms")
