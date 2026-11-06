"""Runs before the server starts, for hosts that give no shell.

With CRMS_ADMIN_EMAIL and CRMS_ADMIN_PASSWORD set, an empty database gets its first admin.
With CRMS_SAMPLE_DATA=300 it gets the demo accounts and that many sample complaints instead.
A database that already has users is left alone.
"""
import os

from . import db
from .db import one
from .main_config import database_url
from .seed import seed_admin, seed_bulk


def has_users():
    path = database_url()
    db.init_db(path)
    token = db.use(db.connect(path))
    try:
        return bool(one("SELECT 1 FROM users LIMIT 1"))
    finally:
        db.release(token)


def main():
    if has_users():
        return
    sample = os.environ.get("CRMS_SAMPLE_DATA", "").strip()
    email = os.environ.get("CRMS_ADMIN_EMAIL", "").strip()
    if sample.isdigit() and int(sample) > 0:
        seed_bulk(int(sample))
    elif email:
        seed_admin(email)


if __name__ == "__main__":
    main()
