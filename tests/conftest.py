import pytest
from werkzeug.security import generate_password_hash

from app import create_app
from app.db import get_db


@pytest.fixture
def app(tmp_path):
    app = create_app({"DATABASE": str(tmp_path / "test.db"), "SECRET_KEY": "test", "TESTING": True})
    with app.app_context():
        db = get_db()
        db.execute("INSERT INTO police_station (name, jurisdiction) VALUES ('Central', 'Centre')")
        pw = generate_password_hash("password123")
        for name, email, role in (
            ("Admin", "admin@t.test", "admin"),
            ("Officer", "officer@t.test", "officer"),
            ("Other Officer", "other@t.test", "officer"),
            ("Asha", "asha@t.test", "citizen"),
            ("Bina", "bina@t.test", "citizen"),
        ):
            uid = db.execute(
                "INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)", (name, email, pw, role)
            ).lastrowid
            if role == "citizen":
                db.execute("INSERT INTO citizen (user_id) VALUES (?)", (uid,))
            elif role == "admin":
                db.execute("INSERT INTO admin (user_id) VALUES (?)", (uid,))
            else:
                db.execute(
                    "INSERT INTO officer (user_id, badge_no, rank, station_id) VALUES (?, ?, 'Inspector', 1)",
                    (uid, f"B-{uid}"),
                )
        db.commit()
    return app


class Client:
    def __init__(self, app):
        self.http = app.test_client()

    def login(self, email):
        self.http.get("/login")
        with self.http.session_transaction() as s:
            s["csrf"] = "tok"
        return self.http.post("/login", data={"email": email, "password": "password123", "csrf": "tok"})

    def post(self, url, **data):
        with self.http.session_transaction() as s:
            s["csrf"] = "tok"
        return self.http.post(url, data={**data, "csrf": "tok"})

    def get(self, url):
        return self.http.get(url)


@pytest.fixture
def make_client(app):
    def make(email=None):
        c = Client(app)
        if email:
            c.login(email)
        return c
    return make
