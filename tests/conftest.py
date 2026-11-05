import os

import pytest
from fastapi.testclient import TestClient

import mongomock

from app import create_app, db
from app.auth import hash_password


def reset_database(url):
    """PostgreSQL and MySQL keep their tables between runs, so start each test from nothing."""
    dialect = db.dialect_of(url)
    conn = db.connect(url)
    if dialect == "postgresql":
        conn.execute("DROP SCHEMA public CASCADE")
        conn.execute("CREATE SCHEMA public")
    else:
        conn.execute("SET FOREIGN_KEY_CHECKS = 0")
        for row in conn.execute(
            "SELECT table_name AS t, table_type AS k FROM information_schema.tables WHERE table_schema = DATABASE()"
        ).fetchall():
            conn.execute(f"DROP {'VIEW' if row['k'] == 'VIEW' else 'TABLE'} `{row['t']}`")
        conn.execute("SET FOREIGN_KEY_CHECKS = 1")
    conn.commit()
    conn.close()


@pytest.fixture
def app(tmp_path):
    # CRMS_TEST_DB_URL points the whole suite at PostgreSQL or MySQL instead of a temporary SQLite file
    path = os.environ.get("CRMS_TEST_DB_URL") or f"sqlite:///{tmp_path / 'test.db'}"
    if db.dialect_of(path) != "sqlite":
        reset_database(path)
    app = create_app(database=path, secret="test", mongo_client=mongomock.MongoClient())
    token = db.use(db.connect(path))
    conn = db.get_db()
    conn.execute("INSERT INTO police_station (name, jurisdiction) VALUES ('Central', 'Centre')")
    pw = hash_password("password123")
    for name, email, role in (
        ("Admin", "admin@t.test", "admin"),
        ("Officer", "officer@t.test", "officer"),
        ("Other Officer", "other@t.test", "officer"),
        ("Asha", "asha@t.test", "citizen"),
        ("Bina", "bina@t.test", "citizen"),
    ):
        uid = conn.execute(
            "INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)", (name, email, pw, role)
        ).lastrowid
        if role == "citizen":
            conn.execute("INSERT INTO citizen (user_id) VALUES (?)", (uid,))
        elif role == "admin":
            conn.execute("INSERT INTO admin (user_id) VALUES (?)", (uid,))
        else:
            conn.execute(
                "INSERT INTO officer (user_id, badge_no, officer_rank, station_id) VALUES (?, ?, 'Inspector', 1)",
                (uid, f"B-{uid}"),
            )
    conn.commit()
    db.release(token)
    return app


@pytest.fixture
def make_client(app):
    def make(email=None):
        client = TestClient(app, headers={"X-Requested-With": "crms"})
        if email:
            resp = client.post("/api/auth/login", json={"email": email, "password": "password123"})
            assert resp.status_code == 200
        return client
    return make
