"""Exercises the queries that differ most between SQLite, PostgreSQL and MySQL."""


def seed_case(make_client):
    asha, admin = make_client("asha@t.test"), make_client("admin@t.test")
    asha.post("/api/complaints", json={
        "title": "Shop window broken", "description": "Found smashed.",
        "location": "Market Street", "incident_date": "2026-10-02",
    })
    admin.post("/api/complaints/1/verify")
    admin.post("/api/complaints/1/register-case", json={"station_id": 1})
    return asha, admin


def test_every_staff_page_loads(make_client):
    asha, admin = seed_case(make_client)
    for url in (
        "/api/dashboard", "/api/cases", "/api/cases?status=Under Investigation&q=shop&mine=1",
        "/api/complaints?status=Filed&q=window", "/api/criminals", "/api/users",
        "/api/reports", "/api/cases/1", "/api/auth/me", "/api/notifications",
    ):
        resp = admin.get(url)
        assert resp.status_code == 200, url
    assert admin.get("/api/cases?q=SHOP").json()["total"] == 1  # search ignores case on every database


def test_criminal_records(make_client):
    _, admin = seed_case(make_client)
    created = admin.post("/api/criminals", json={"name": "Ravi Menon", "age": 34, "crime_history": "Burglary", "wanted": True})
    cid = created.json()["criminal_id"]
    assert admin.put(f"/api/criminals/{cid}", json={"name": "Ravi Menon", "age": "35", "wanted": False}).status_code == 200
    assert admin.post("/api/criminals", json={"name": "X", "age": 500}).status_code == 400
    assert admin.get("/api/criminals?q=ravi").json()["items"][0]["age"] == 35

    # linking twice replaces the role instead of failing
    admin.post("/api/cases/1/criminals", json={"criminal_id": cid, "role": "suspect"})
    assert admin.post("/api/cases/1/criminals", json={"criminal_id": cid, "role": "accused"}).status_code == 200
    linked = admin.get("/api/cases/1").json()["linked"]
    assert [(p["name"], p["role"]) for p in linked] == [("Ravi Menon", "accused")]
    assert admin.delete(f"/api/cases/1/criminals/{cid}").status_code == 200
    assert admin.get("/api/cases/1").json()["linked"] == []


def test_public_records_hide_case_files(make_client):
    _, admin = seed_case(make_client)
    admin.post("/api/criminals", json={"name": "Wanted Person", "wanted": True})
    admin.post("/api/criminals", json={"name": "Quiet Person", "wanted": False})
    asha = make_client("asha@t.test")
    records = asha.get("/api/records").json()
    assert [w["name"] for w in records["wanted"]] == ["Wanted Person"]
    assert records["stations"][0]["name"] == "Central"


def test_reports(make_client):
    _, admin = seed_case(make_client)
    cid = admin.post("/api/criminals", json={"name": "Ravi Menon"}).json()["criminal_id"]
    admin.post("/api/cases/1/criminals", json={"criminal_id": cid, "role": "suspect"})
    admin.post("/api/cases/1/assign", json={"officer_id": 1})
    admin.post("/api/cases/1/status", json={"status": "Closed (Unresolved)"})

    report = admin.get(f"/api/reports?start=2000-01-01&end=2999-12-31&criminal={cid}").json()
    assert report["by_status"] == [{"status": "Closed (Unresolved)", "total": 1}]
    assert report["by_station"] == [{"station": "Central", "total": 1}]
    assert report["period"] == {"complaints": 1, "cases": 1, "closed": 1}
    assert report["history"]["cases"][0]["role"] == "suspect"


def test_user_management(make_client):
    admin = make_client("admin@t.test")
    created = admin.post("/api/users", json={
        "name": "New Officer", "email": "new@t.test", "password": "longenough",
        "role": "officer", "badge_no": "B-900", "rank": "Constable", "station_id": 1,
    })
    assert created.status_code == 200
    rows = {u["email"]: u for u in admin.get("/api/users").json()["rows"]}
    assert rows["new@t.test"]["officer_rank"] == "Constable"
    assert admin.post("/api/users", json={"name": "Dup", "email": "new@t.test", "password": "longenough", "role": "citizen"}).status_code == 400
    assert admin.post("/api/users", json={
        "name": "Bad", "email": "bad@t.test", "password": "longenough", "role": "officer", "badge_no": "B-900", "rank": "x", "station_id": 1,
    }).status_code == 400
    # the failed officer must not leave a half-created account behind
    assert "bad@t.test" not in {u["email"] for u in admin.get("/api/users").json()["rows"]}

    uid = rows["new@t.test"]["user_id"]
    assert admin.put(f"/api/users/{uid}/role", json={"role": "admin"}).status_code == 200
    assert admin.post(f"/api/users/{uid}/active").status_code == 200
    assert make_client().post("/api/auth/login", json={"email": "new@t.test", "password": "longenough"}).status_code == 400
    assert admin.put("/api/users/1/role", json={"role": "citizen"}).status_code == 400  # cannot demote yourself


def test_profile(make_client):
    asha = make_client("asha@t.test")
    assert asha.put("/api/profile", json={"name": "Asha N", "address": "12 Lake Road", "phone": "123"}).json()["user"]["name"] == "Asha N"
    assert asha.get("/api/profile").json()["extra"]["address"] == "12 Lake Road"
    assert asha.put("/api/profile", json={"name": "Asha N", "password": "short"}).status_code == 400


def test_login_locks_after_five_failures(make_client):
    client = make_client()
    for _ in range(5):
        assert client.post("/api/auth/login", json={"email": "asha@t.test", "password": "wrong"}).status_code == 400
    locked = client.post("/api/auth/login", json={"email": "asha@t.test", "password": "password123"})
    assert locked.status_code == 429
    assert "Try again in" in locked.json()["detail"]
    # another account is not affected
    assert client.post("/api/auth/login", json={"email": "bina@t.test", "password": "password123"}).status_code == 200


def test_success_clears_earlier_failures(make_client):
    client = make_client()
    for _ in range(4):
        client.post("/api/auth/login", json={"email": "asha@t.test", "password": "wrong"})
    assert client.post("/api/auth/login", json={"email": "asha@t.test", "password": "password123"}).status_code == 200
    client.post("/api/auth/logout")
    for _ in range(4):
        assert client.post("/api/auth/login", json={"email": "asha@t.test", "password": "wrong"}).status_code == 400


def test_officers_are_told_about_assignments(make_client):
    asha, admin = make_client("asha@t.test"), make_client("admin@t.test")
    asha.post("/api/complaints", json={
        "title": "Bike stolen", "description": "Taken.", "location": "Lake Road", "incident_date": "2026-10-01",
    })
    admin.post("/api/complaints/1/verify")
    admin.post("/api/complaints/1/register-case", json={"station_id": 1})
    first, second = make_client("officer@t.test"), make_client("other@t.test")

    admin.post("/api/cases/1/assign", json={"officer_id": 1})
    assert "was assigned to you" in first.get("/api/notifications").json()["items"][0]["message"]

    admin.post("/api/cases/1/assign", json={"officer_id": 2})
    assert "was assigned to you" in second.get("/api/notifications").json()["items"][0]["message"]
    assert "reassigned" in first.get("/api/notifications").json()["items"][0]["message"]

    # assigning the same officer again is not news
    before = len(second.get("/api/notifications").json()["items"])
    admin.post("/api/cases/1/assign", json={"officer_id": 2})
    assert len(second.get("/api/notifications").json()["items"]) == before


def test_backup_and_restore_round_trip(app, tmp_path, make_client):
    import mongomock
    from tests.conftest import reset_database

    from app import backup, create_app, db

    asha, admin = seed_case(make_client)
    asha.post("/api/complaints/1/attachments", files={"file": ("note.txt", b"hello", "text/plain")})
    admin.post("/api/cases/1/assign", json={"officer_id": 1})
    admin.post("/api/cases/1/evidence", json={"type": "CCTV", "description": "Camera at the gate."})
    url = app.state.database_url
    archive = backup.create_backup(url, tmp_path / "backups")

    # a fresh, empty installation gets everything back
    if db.dialect_of(url) == "sqlite":
        fresh_url = f"sqlite:///{tmp_path / 'fresh.db'}"
    else:
        reset_database(url)
        fresh_url = url
    app = create_app(database=fresh_url, secret="test", mongo_client=mongomock.MongoClient())
    backup.restore_backup(archive, fresh_url)

    from fastapi.testclient import TestClient
    client = TestClient(app, headers={"X-Requested-With": "crms"})
    assert client.post("/api/auth/login", json={"email": "admin@t.test", "password": "password123"}).status_code == 200
    case = client.get("/api/cases/1").json()
    assert case["case"]["officer_name"] == "Officer"
    assert case["evidence"][0]["type"] == "CCTV"
    attachment_id = case["attachments"][0]["attachment_id"]
    assert client.get(f"/api/attachments/{attachment_id}").content == b"hello"

    # restoring over existing data is refused
    import pytest
    with pytest.raises(RuntimeError):
        backup.restore_backup(archive, fresh_url)


def test_backup_keeps_only_the_newest(app, tmp_path, make_client):
    import time
    from app import backup

    url = app.state.database_url
    for _ in range(3):
        backup.create_backup(url, tmp_path / "b", keep=2)
        time.sleep(1.1)
    assert len(list((tmp_path / "b").glob("crms-*.tar.gz"))) == 2


def test_accounts_can_be_sorted(make_client):
    admin = make_client("admin@t.test")

    def names(query=""):
        return [r["name"] for r in admin.get(f"/api/users{query}").json()["rows"]]

    assert names("?sort=name&dir=asc") == sorted(names("?sort=name&dir=asc"))
    assert names("?sort=name&dir=desc") == names("?sort=name&dir=asc")[::-1]
    emails = [r["email"] for r in admin.get("/api/users?sort=email&dir=asc").json()["rows"]]
    assert emails == sorted(emails)
    roles = [r["role"] for r in admin.get("/api/users?sort=role&dir=desc").json()["rows"]]
    assert roles == sorted(roles, reverse=True)
    # an unknown column falls back to the default instead of reaching the SQL
    assert admin.get("/api/users?sort=password; DROP TABLE users").status_code == 200
    assert len(names("?sort=nope")) == 5
