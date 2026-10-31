import sqlite3
from contextvars import ContextVar
from pathlib import Path

SCHEMA = Path(__file__).with_name("schema.sql")

# one connection per request, opened by the middleware in app/__init__.py
_conn: ContextVar[sqlite3.Connection] = ContextVar("conn")


def connect(path):
    # requests run in a thread pool, so the connection may change threads
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def use(conn):
    """Make conn the current connection; returns a token for release()."""
    return _conn.set(conn)


def release(token):
    _conn.get().close()
    _conn.reset(token)


def get_db():
    return _conn.get()


def init_db(path):
    conn = connect(path)
    conn.executescript(SCHEMA.read_text())
    conn.commit()
    conn.close()


def one(sql, *args):
    return get_db().execute(sql, args).fetchone()


def many(sql, *args):
    return get_db().execute(sql, args).fetchall()


def run(sql, *args):
    return get_db().execute(sql, args).lastrowid
