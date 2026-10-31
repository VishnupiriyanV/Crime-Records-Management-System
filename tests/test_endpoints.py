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
