"""Back up and restore everything: python -m app.backup create | restore FILE

The archive holds every SQL table as JSON, every MongoDB collection (which includes the uploaded files),
so it also moves data between SQLite, PostgreSQL and MySQL.
"""
import argparse
import io
import json
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path

from bson import json_util

from . import db, mongo
from .main_config import database_url, mongo_name, mongo_url

# parents before children, so every foreign key points at a row that already exists
TABLES = [
    ("police_station", "station_id"), ("users", "user_id"), ("citizen", "citizen_id"),
    ("officer", "officer_id"), ("admin", "admin_id"), ("complaint", "complaint_id"),
    ("crime_case", "case_id"), ("criminal", "criminal_id"), ("case_criminal", None), ("report", "report_id"),
]
COLLECTIONS = [
    "evidence", "notes", "notifications", "status_log", "attachments", "attachment_files",
    "statements", "arrests", "court_dates", "chargesheets", "officer_photos", "api_tokens", "webhooks",
]


def _add(tar, name, text):
    data = text.encode()
    info = tarfile.TarInfo(name)
    info.size = len(data)
    tar.addfile(info, io.BytesIO(data))


def create_backup(url, out_dir, keep=None):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    target = out_dir / f"crms-{stamp}.tar.gz"

    conn = db.connect(url)
    try:
        with tarfile.open(target, "w:gz") as tar:
            for table, _ in TABLES:
                rows = [dict(r) for r in conn.execute(f"SELECT * FROM {table}").fetchall()]
                _add(tar, f"sql/{table}.json", json.dumps(rows))
            for name in COLLECTIONS:
                lines = (json_util.dumps(doc) for doc in mongo.mdb()[name].find())
                _add(tar, f"mongo/{name}.jsonl", "\n".join(lines))
    finally:
        conn.close()

    if keep:
        for old in sorted(out_dir.glob("crms-*.tar.gz"))[:-keep]:
            old.unlink()
    return target


def restore_backup(archive, url):
    """Load an archive into an empty database; refuses to touch one that already has users."""
    db.init_db(url)
    conn = db.connect(url)
    try:
        if conn.execute("SELECT 1 FROM users LIMIT 1").fetchone():
            raise RuntimeError("The database already has users. Restore into an empty database.")
        if any(mongo.mdb()[name].count_documents({}) for name in COLLECTIONS):
            raise RuntimeError("MongoDB already has data. Restore into an empty database.")
        with tarfile.open(archive, "r:gz") as tar:
            for table, key in TABLES:
                rows = json.loads(tar.extractfile(f"sql/{table}.json").read())
                for row in rows:
                    columns = ", ".join(row)
                    marks = ", ".join("?" for _ in row)
                    conn.execute(f"INSERT INTO {table} ({columns}) VALUES ({marks})", tuple(row.values()))
                if key and rows:
                    _sync_counter(conn, table, key)
            for name in COLLECTIONS:
                try:
                    text = tar.extractfile(f"mongo/{name}.jsonl").read().decode()
                except KeyError:
                    continue  # an archive from before this collection existed
                docs = [json_util.loads(line) for line in text.splitlines() if line]
                if docs:
                    mongo.mdb()[name].insert_many(docs)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _sync_counter(conn, table, key):
    """Rows came back with their old ids, so make the next new id continue after the highest."""
    if conn.dialect == "postgresql":
        conn.execute(
            f"SELECT setval(pg_get_serial_sequence('{table}', '{key}'), (SELECT MAX({key}) FROM {table}))"
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    make = sub.add_parser("create", help="write a new backup archive")
    make.add_argument("--out", default="backups", help="folder for archives (default: backups)")
    make.add_argument("--keep", type=int, default=14, help="how many archives to keep (default: 14)")
    back = sub.add_parser("restore", help="load an archive into an empty database")
    back.add_argument("archive")
    args = parser.parse_args()

    url = database_url()
    mongo.configure(mongo_url(), mongo_name())
    try:
        if args.command == "create":
            print(create_backup(url, args.out, args.keep))
        else:
            restore_backup(args.archive, url)
            print("Restored.")
    except RuntimeError as err:
        sys.exit(str(err))


if __name__ == "__main__":
    main()
