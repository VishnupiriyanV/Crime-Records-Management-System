"""One small interface over SQLite, PostgreSQL and MySQL.

Queries are written once with ? placeholders; adapt() rewrites them for the driver in use.
"""
import re
import sqlite3
from contextvars import ContextVar
from pathlib import Path
from urllib.parse import unquote, urlparse

from . import migrations

SCHEMAS = Path(__file__).parent / "schemas"

# primary keys that the database numbers itself, needed to read an insert's id back on PostgreSQL
SERIAL_KEYS = {
    "users": "user_id", "police_station": "station_id", "citizen": "citizen_id", "officer": "officer_id",
    "admin": "admin_id", "complaint": "complaint_id", "crime_case": "case_id",
    "criminal": "criminal_id", "report": "report_id",
}

_conn: ContextVar["Conn"] = ContextVar("conn")


def dialect_of(url):
    scheme = urlparse(url).scheme
    if scheme in ("postgres", "postgresql"):
        return "postgresql"
    if scheme in ("mysql", "mysql+pymysql"):
        return "mysql"
    return "sqlite"


def adapt(sql, dialect):
    if dialect == "sqlite":
        return sql
    sql = sql.replace("%", "%%").replace("?", "%s")
    if dialect == "postgresql":
        sql = re.sub(r"\bLIKE\b", "ILIKE", sql)
    return sql


class Cursor:
    def __init__(self, cursor, lastrowid=None):
        self._cursor = cursor
        self.lastrowid = lastrowid

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()


class Conn:
    def __init__(self, raw, dialect):
        self.raw = raw
        self.dialect = dialect

    def execute(self, sql, args=()):
        args = tuple(args)
        returning = None
        if self.dialect == "postgresql":
            match = re.match(r"\s*INSERT INTO (\w+)", sql)
            if match and match.group(1) in SERIAL_KEYS:
                returning = SERIAL_KEYS[match.group(1)]
                sql = f"{sql.rstrip()} RETURNING {returning}"
        sql = adapt(sql, self.dialect)

        if self.dialect == "sqlite":
            cursor = self.raw.execute(sql, args)
            return Cursor(cursor, cursor.lastrowid)
        cursor = self.raw.cursor()
        cursor.execute(sql, args)
        if self.dialect == "postgresql":
            return Cursor(cursor, cursor.fetchone()[returning] if returning else None)
        return Cursor(cursor, cursor.lastrowid)

    def commit(self):
        self.raw.commit()

    def rollback(self):
        self.raw.rollback()

    def close(self):
        self.raw.close()


def connect(url):
    dialect = dialect_of(url)
    if dialect == "postgresql":
        import psycopg
        from psycopg.rows import dict_row

        return Conn(psycopg.connect(url, row_factory=dict_row), dialect)
    if dialect == "mysql":
        import pymysql
        from pymysql.cursors import DictCursor

        parts = urlparse(url)
        raw = pymysql.connect(
            host=parts.hostname, port=parts.port or 3306, user=unquote(parts.username or ""),
            password=unquote(parts.password or ""), database=parts.path.lstrip("/"),
            charset="utf8mb4", cursorclass=DictCursor,
        )
        return Conn(raw, dialect)

    path = url[len("sqlite:///"):] if url.startswith("sqlite:///") else url
    raw = sqlite3.connect(path, check_same_thread=False)
    raw.row_factory = sqlite3.Row
    raw.execute("PRAGMA foreign_keys = ON")
    return Conn(raw, dialect)


def init_db(url):
    """Create the tables the first time; later starts leave an existing database alone."""
    conn = connect(url)
    try:
        if _has_users_table(conn):
            migrations.upgrade(conn)
            return
        script = (SCHEMAS / f"{conn.dialect}.sql").read_text()
        for statement in script.split(";"):
            if statement.strip():
                conn.raw.cursor().execute(statement) if conn.dialect != "sqlite" else conn.raw.execute(statement)
        conn.commit()
    finally:
        conn.close()


def _has_users_table(conn):
    if conn.dialect == "sqlite":
        return bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'users'").fetchone())
    if conn.dialect == "postgresql":
        return conn.execute("SELECT to_regclass('users') AS t").fetchone()["t"] is not None
    return conn.execute(
        "SELECT COUNT(*) AS n FROM information_schema.tables"
        " WHERE table_schema = DATABASE() AND table_name = 'users'"
    ).fetchone()["n"] > 0


def use(conn):
    """Make conn the current connection; returns a token for release()."""
    return _conn.set(conn)


def release(token):
    _conn.get().close()
    _conn.reset(token)


def get_db():
    return _conn.get()


def one(sql, *args):
    return get_db().execute(sql, args).fetchone()


def many(sql, *args):
    return get_db().execute(sql, args).fetchall()


def run(sql, *args):
    return get_db().execute(sql, args).lastrowid
