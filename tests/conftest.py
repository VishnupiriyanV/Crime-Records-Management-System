import pytest
from fastapi.testclient import TestClient

import mongomock

from app import create_app, db
from app.auth import hash_password


@pytest.fixture
def app(tmp_path):
    path = str(tmp_path / "test.db")
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
                "INSERT INTO officer (user_id, badge_no, rank, station_id) VALUES (?, ?, 'Inspector', 1)",
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
