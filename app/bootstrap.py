"""Runs before the server starts, for hosts that give no shell.

With CRMS_ADMIN_EMAIL and CRMS_ADMIN_PASSWORD set, an empty database gets its first admin.
With CRMS_SAMPLE_DATA=300 it gets the demo accounts and that many sample complaints instead.
A database that already has users is left alone.

The sample data takes minutes on a small host, so it runs with --sample after the server is already listening.
"""
import os
import sys

from . import db
from .db import one
from .main_config import database_url
from .seed import seed_admin, seed_bulk


def count(table):
    path = database_url()
    db.init_db(path)
    token = db.use(db.connect(path))
    try:
        return one(f"SELECT COUNT(*) AS n FROM {table}")["n"]
    finally:
        db.release(token)


def main(sample_only=False):
    sample = os.environ.get("CRMS_SAMPLE_DATA", "").strip()
    email = os.environ.get("CRMS_ADMIN_EMAIL", "").strip()
    if sample.isdigit() and int(sample) > 0:
        # judged by complaints, not users, so a load that was cut off half way is picked up again
        if sample_only and count("complaint") <= 20:
            seed_bulk(int(sample))
    elif email and not sample_only and count("users") == 0:
        seed_admin(email)


if __name__ == "__main__":
    main(sample_only="--sample" in sys.argv)
