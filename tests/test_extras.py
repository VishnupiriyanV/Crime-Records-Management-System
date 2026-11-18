"""Search, exports, timeline, audit trail, previews and password change."""
from tests.test_endpoints import seed_case


def test_search_is_scoped_to_the_user(make_client):
    asha, admin = seed_case(make_client)
    admin.post("/api/criminals", json={"name": "Shopkeeper Rao"})
    staff = admin.get("/api/search?q=shop").json()
    assert len(staff["complaints"]) == 1 and len(staff["cases"]) == 1 and len(staff["criminals"]) == 1

    own = asha.get("/api/search?q=shop").json()
    assert len(own["complaints"]) == 1 and own["cases"] == [] and own["criminals"] == []
    # another citizen sees nothing of Asha's complaint
    assert make_client("bina@t.test").get("/api/search?q=shop").json()["complaints"] == []
    assert admin.get("/api/search?q=s").json()["complaints"] == []  # too short to search


def test_sorting_ignores_unknown_columns(make_client):
    _, admin = seed_case(make_client)
    assert admin.get("/api/cases?sort=title&dir=asc").status_code == 200
    assert admin.get("/api/complaints?sort=nonsense; DROP TABLE users&dir=up").status_code == 200
    assert admin.get("/api/criminals?sort=cases&dir=desc").status_code == 200


def test_csv_exports(make_client):
    asha, admin = seed_case(make_client)
    admin.post("/api/criminals", json={"name": "=HYPERLINK(1)", "age": 30})
    resp = admin.get("/api/export/complaints.csv")
    assert resp.status_code == 200 and resp.headers["content-type"].startswith("text/csv")
    assert "Shop window broken" in resp.content.decode("utf-8-sig")
    assert "'=HYPERLINK(1)" in admin.get("/api/export/criminals.csv").content.decode("utf-8-sig")
    assert "Shop window broken" in admin.get("/api/export/cases.csv").content.decode("utf-8-sig")
    assert "Shop window broken" in asha.get("/api/export/complaints.csv").content.decode("utf-8-sig")
    assert asha.get("/api/export/cases.csv").status_code == 403


def test_case_pdf(make_client):
    asha, admin = seed_case(make_client)
    resp = admin.get("/api/export/cases/1.pdf")
    assert resp.status_code == 200 and resp.content.startswith(b"%PDF")
    assert asha.get("/api/export/cases/1.pdf").status_code == 403


def test_case_timeline(make_client):
    asha, admin = seed_case(make_client)
    admin.post("/api/cases/1/assign", json={"officer_id": 1})
    admin.post("/api/cases/1/evidence", json={"type": "Photograph", "description": "Window"})
    admin.post("/api/cases/1/reports", json={"content": "Visited the shop."})
    asha.post("/api/complaints/1/notes", json={"kind": "statement", "body": "More detail."})
    texts = [e["text"] for e in admin.get("/api/cases/1").json()["timeline"]]
    assert texts[0] == "Complaint filed"
    for wanted in ("Complaint verified", "Case opened", "Assigned to Officer", "Evidence 1 recorded: Photograph",
                   "Report written", "Citizen added a statement"):
        assert wanted in texts, wanted


def test_dashboard_and_reports_have_chart_data(make_client):
    _, admin = seed_case(make_client)
    for url in ("/api/dashboard", "/api/reports"):
        body = admin.get(url).json()
        assert len(body["monthly"]) == 12
        assert sum(m["total"] for m in body["monthly"]) == 1


def test_audit_log(make_client):
    _, admin = seed_case(make_client)
    admin.post("/api/cases/1/assign", json={"officer_id": 1})
    admin.post("/api/users/5/active")
    body = admin.get("/api/audit").json()
    assert body["total"] >= 4
    assigned = [i for i in body["items"] if i["entity"] == "case assignment"][0]
    assert assigned["new_status"] == "Officer"  # the name, not the id
    assert [i["new_status"] for i in admin.get("/api/audit?entity=user").json()["items"]] == ["Deactivated"]
    assert admin.get("/api/audit?q=nobody-by-this-name").json()["total"] == 0
    assert make_client("asha@t.test").get("/api/audit").status_code == 403


def test_attachment_preview(make_client):
    asha, _ = seed_case(make_client)
    asha.post("/api/complaints/1/attachments", files={"file": ("pic.png", b"\x89PNG data", "image/png")})
    attachment = asha.get("/api/complaints/1").json()["attachments"][0]["attachment_id"]
    plain = asha.get(f"/api/attachments/{attachment}")
    assert plain.headers["content-disposition"].startswith("attachment")
    shown = asha.get(f"/api/attachments/{attachment}?inline=1")
    assert shown.headers["content-disposition"].startswith("inline")
    assert shown.headers["content-security-policy"] == "sandbox"


def test_changing_password_needs_the_current_one(make_client):
    asha = make_client("asha@t.test")
    body = {"name": "Asha", "password": "newpassword1"}
    assert asha.put("/api/profile", json=body).status_code == 400
    assert asha.put("/api/profile", json={**body, "current_password": "wrong"}).status_code == 400
    assert asha.put("/api/profile", json={**body, "current_password": "password123"}).status_code == 200
    asha.post("/api/auth/logout")
    assert asha.post("/api/auth/login", json={"email": "asha@t.test", "password": "newpassword1"}).status_code == 200


def test_api_docs_are_not_exposed(make_client):
    client = make_client()
    for path in ("/docs", "/redoc", "/openapi.json"):
        text = client.get(path).text.lower()
        assert "swagger" not in text and "openapi" not in text, path


def test_fir_number_category_and_filters(make_client):
    asha, admin = make_client("asha@t.test"), make_client("admin@t.test")
    body = {"title": "Phone stolen", "description": "Snatched.", "location": "Bus stand", "incident_date": "2026-10-02",
            "category": "Theft", "latitude": 13.08, "longitude": 80.27}
    assert asha.post("/api/complaints", json=body).status_code == 200
    assert asha.post("/api/complaints", json={**body, "category": "Nonsense"}).status_code == 400
    assert asha.post("/api/complaints", json={**body, "longitude": None}).status_code == 400
    assert asha.post("/api/complaints", json={**body, "latitude": 999}).status_code == 400

    item = admin.get("/api/complaints").json()["items"][0]
    year = item["date_filed"][:4]
    assert item["fir_no"] == f"FIR/{year}/0001" and item["category"] == "Theft" and item["severity"] == "Medium"
    assert admin.get(f"/api/complaints?q=FIR/{year}/0001").json()["total"] == 1
    assert admin.get(f"/api/complaints?q=FIR/{year}/0099").json()["total"] == 0
    assert admin.get("/api/complaints?category=Theft&severity=Medium").json()["total"] == 1
    assert admin.get("/api/complaints?category=Fraud").json()["total"] == 0
    assert admin.get(f"/api/search?q=FIR/{year}/0001").json()["complaints"][0]["fir_no"] == f"FIR/{year}/0001"

    # staff can reclassify; a citizen cannot, and the change is audited
    assert asha.post("/api/complaints/1/classify", json={"category": "Fraud", "severity": "High"}).status_code == 403
    assert admin.post("/api/complaints/1/classify", json={"category": "Fraud", "severity": "High"}).status_code == 200
    assert admin.get("/api/complaints/1").json()["complaint"]["severity"] == "High"
    assert admin.get("/api/audit?entity=complaint classification").json()["total"] == 1
    assert "FIR/" in admin.get("/api/export/complaints.csv").content.decode("utf-8-sig")


def test_case_file_records(make_client):
    asha, admin = seed_case(make_client)
    admin.post("/api/cases/1/assign", json={"officer_id": 1})
    person = admin.post("/api/criminals", json={"name": "Ravi Menon"}).json()["criminal_id"]
    witness = admin.post("/api/criminals", json={"name": "Shop Neighbour"}).json()["criminal_id"]
    admin.post("/api/cases/1/criminals", json={"criminal_id": person, "role": "suspect"})
    admin.post("/api/cases/1/criminals", json={"criminal_id": witness, "role": "witness"})

    assert admin.post("/api/cases/1/statements", json={"kind": "witness", "person": "Shop Neighbour", "body": "Saw a man."}).status_code == 200
    assert admin.post("/api/cases/1/statements", json={"kind": "bystander", "person": "X", "body": "Y"}).status_code == 400

    arrest = {"criminal_id": person, "arrested_on": "2026-10-05", "place": "Bus depot", "charges": "Theft"}
    assert admin.post("/api/cases/1/arrests", json={**arrest, "criminal_id": witness}).status_code == 400  # a witness is not arrested
    assert admin.post("/api/cases/1/arrests", json={**arrest, "arrested_on": "2999-01-01"}).status_code == 400
    assert admin.post("/api/cases/1/arrests", json=arrest).status_code == 200

    hearing = {"date": "2999-01-10", "court": "Magistrate Court 4", "purpose": "First hearing"}
    assert admin.post("/api/cases/1/court-dates", json=hearing).status_code == 400  # needs the chargesheet first
    assert admin.post("/api/cases/1/chargesheet", json={"sections": "BNS 303", "summary": "Taken from the shop."}).status_code == 200
    assert admin.post("/api/cases/1/chargesheet", json={"sections": "BNS 303", "summary": "Again."}).status_code == 400
    assert admin.post("/api/cases/1/court-dates", json=hearing).status_code == 200
    assert admin.post("/api/cases/1/court-dates", json={**hearing, "date": "not a date"}).status_code == 400
    assert admin.post("/api/cases/1/court-dates/1/outcome", json={"outcome": "Adjourned"}).status_code == 200
    assert any("court date" in n["message"] for n in asha.get("/api/notifications").json()["items"])

    case = admin.get("/api/cases/1").json()
    assert case["chargesheet"]["sections"] == "BNS 303"
    assert len(case["statements"]) == 1 and len(case["arrests"]) == 1 and case["court_dates"][0]["outcome"] == "Adjourned"
    texts = [e["text"] for e in case["timeline"]]
    assert "Statement from witness Shop Neighbour" in texts and any("arrested at Bus depot" in t for t in texts)
    assert any(t.startswith("Chargesheet filed under BNS 303") for t in texts)
    assert admin.get("/api/export/cases/1.pdf").content.startswith(b"%PDF")
    assert asha.get("/api/cases/1").status_code == 403


def test_evidence_custody_and_files(make_client):
    asha, admin = seed_case(make_client)
    admin.post("/api/cases/1/evidence", json={"type": "Hammer", "description": "Found near the shop"})
    item = admin.get("/api/cases/1").json()["evidence"][0]
    assert [c["action"] for c in item["custody"]] == ["collected"]

    custody = {"action": "stored", "where": "Evidence room, shelf 3"}
    assert admin.post("/api/cases/1/evidence/1/custody", json=custody).status_code == 200
    assert admin.post("/api/cases/1/evidence/1/custody", json={"action": "lost", "where": "x"}).status_code == 400
    assert admin.post("/api/cases/1/evidence/1/custody", json={"action": "stored"}).status_code == 400
    assert admin.post("/api/cases/1/evidence/9/custody", json=custody).status_code == 404
    admin.post("/api/cases/1/evidence/1/custody", json={"action": "released", "where": "Returned to owner"})
    assert admin.post("/api/cases/1/evidence/1/custody", json=custody).status_code == 400  # already left custody

    sent = admin.post("/api/cases/1/evidence/1/files", files={"file": ("hammer.png", b"\x89PNG data", "image/png")})
    assert sent.status_code == 200
    files = admin.get("/api/cases/1").json()["evidence"][0]["files"]
    assert len(files) == 1
    # a file on evidence is for staff only, and does not show up on the citizen's complaint
    assert admin.get(f"/api/attachments/{files[0]['attachment_id']}").status_code == 200
    assert asha.get(f"/api/attachments/{files[0]['attachment_id']}").status_code == 404
    assert asha.get("/api/complaints/1").json()["attachments"] == []


def test_hotspots_stations_and_officers(make_client):
    asha, admin = make_client("asha@t.test"), make_client("admin@t.test")
    for i in range(3):
        asha.post("/api/complaints", json={
            "title": f"Theft {i}", "description": "x", "location": "Market", "incident_date": "2026-10-02",
            "category": "Theft", "latitude": 13.081 + i / 10000, "longitude": 80.271,
        })
    asha.post("/api/complaints", json={"title": "Far away", "description": "x", "location": "Elsewhere",
                                       "incident_date": "2026-10-02", "category": "Fraud", "latitude": 13.2, "longitude": 80.4})
    asha.post("/api/complaints", json={"title": "No pin", "description": "x", "location": "Somewhere",
                                       "incident_date": "2026-10-02", "category": "Other"})
    data = admin.get("/api/map").json()
    assert len(data["points"]) == 4 and data["hotspots"][0]["total"] == 3 and data["hotspots"][0]["top_category"] == "Theft"
    assert len(admin.get("/api/map?category=Fraud").json()["points"]) == 1
    assert asha.get("/api/map").status_code == 403

    listing = admin.get("/api/stations").json()["items"]
    assert listing[0]["name"] == "Central" and listing[0]["officers"] == 2
    page = admin.get("/api/stations/1").json()
    assert [o["name"] for o in page["officers"]] == ["Officer", "Other Officer"]
    assert admin.get("/api/stations/99").status_code == 404
    profile = admin.get("/api/officers/1").json()
    assert profile["officer"]["officer_rank"] == "Inspector" and profile["can_edit_photo"] is True

    # photos: the officer themself or an admin may set one, nobody else, and only small images
    mine = make_client("officer@t.test")
    png = ("me.png", b"\x89PNG data", "image/png")
    assert mine.post("/api/officers/1/photo", files={"file": png}).status_code == 200
    assert mine.post("/api/officers/2/photo", files={"file": png}).status_code == 400
    assert mine.post("/api/officers/1/photo", files={"file": ("me.gif", b"GIF89a", "image/gif")}).status_code == 400
    assert mine.post("/api/officers/1/photo", files={"file": ("big.png", b"0" * (1024 * 1024 + 1), "image/png")}).status_code == 400
    assert admin.get("/api/officers/1/photo").content == b"\x89PNG data"
    assert admin.get("/api/officers/2/photo").status_code == 404
    assert admin.get("/api/officers/1").json()["officer"]["has_photo"] is True
    assert asha.get("/api/officers/1/photo").status_code == 403


def test_old_database_gets_the_new_columns(tmp_path):
    import sqlite3
    from app import db
    path = tmp_path / "old.db"
    raw = sqlite3.connect(path)
    raw.execute("CREATE TABLE users (user_id INTEGER PRIMARY KEY)")
    raw.execute("CREATE TABLE complaint (complaint_id INTEGER PRIMARY KEY, title TEXT)")
    raw.execute("CREATE TABLE police_station (station_id INTEGER PRIMARY KEY, name TEXT)")
    raw.execute("INSERT INTO complaint (title) VALUES ('old one')")
    raw.commit()
    raw.close()
    db.init_db(f"sqlite:///{path}")
    db.init_db(f"sqlite:///{path}")  # running it twice is harmless
    check = sqlite3.connect(path)
    assert check.execute("SELECT category, severity, latitude FROM complaint").fetchone() == ("Other", "Medium", None)
    check.execute("SELECT phone, latitude, longitude FROM police_station")


def test_sample_data_generator(app, make_client):
    from app import db, demo_data
    token = db.use(db.connect(app.state.database_url))
    try:
        assert demo_data.generate(80, seed=1) == 80
    finally:
        db.release(token)

    admin = make_client("admin@t.test")
    assert admin.get("/api/complaints").json()["total"] == 80
    reports = admin.get("/api/reports").json()
    assert sum(m["total"] for m in reports["monthly"]) >= 40  # spread across the year, not all in one month
    assert len(reports["by_category"]) >= 4
    assert len(admin.get("/api/map").json()["points"]) == 80
    stations = admin.get("/api/stations").json()["items"]
    assert len(stations) == 6  # the five sample stations plus the one the fixture made
    assert sum(1 for s in stations if s["latitude"]) == 5
    for case in admin.get("/api/cases").json()["items"]:
        detail = admin.get(f"/api/cases/{case['case_id']}").json()
        # the rule the app enforces must also hold for generated data
        if case["status"] in ("Chargesheet Filed", "Closed (Resolved)"):
            assert detail["chargesheet"] and detail["arrests"]
        assert all(e["at"] <= "9999" for e in detail["timeline"])


def test_bootstrap_creates_first_admin_once(tmp_path, monkeypatch):
    from app import bootstrap, db

    url = f"sqlite:///{tmp_path / 'boot.db'}"
    monkeypatch.setenv("CRMS_DB_URL", url)
    monkeypatch.setenv("CRMS_ADMIN_EMAIL", "boss@example.com")
    monkeypatch.setenv("CRMS_ADMIN_PASSWORD", "a-long-password-1")
    bootstrap.main()
    bootstrap.main()
    token = db.use(db.connect(url))
    try:
        rows = db.many("SELECT email, role FROM users")
    finally:
        db.release(token)
    assert [(r["email"], r["role"]) for r in rows] == [("boss@example.com", "admin")]


def test_double_submit_files_one_complaint(make_client):
    asha = make_client("asha@t.test")
    form = {
        "title": "Bag stolen", "description": "Taken from the bench.", "location": "Park gate",
        "incident_date": "2026-10-02", "category": "Theft",
    }
    first = asha.post("/api/complaints", json=form).json()["complaint_id"]
    again = asha.post("/api/complaints", json=form).json()["complaint_id"]
    assert first == again
    assert asha.get("/api/complaints").json()["total"] == 1
    form["description"] = "Taken from the bench, near the fountain."
    assert asha.post("/api/complaints", json=form).json()["complaint_id"] != first


