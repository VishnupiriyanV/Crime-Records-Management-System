from app.db import one
from app.lifecycle import CASE_TRANSITIONS


def file_complaint(client, title="Bike stolen"):
    return client.post(
        "/complaints/new", title=title, description="Taken from the rack.",
        location="Lake Road", incident_date="2026-10-01",
    )


def test_citizen_sees_only_own_complaints(app, make_client):
    asha, bina = make_client("asha@t.test"), make_client("bina@t.test")
    file_complaint(asha)
    assert b"Bike stolen" in asha.get("/complaints").data
    assert b"Bike stolen" not in bina.get("/complaints").data
    assert bina.get("/complaints/1").status_code == 404


def test_citizen_cannot_open_staff_pages(make_client):
    asha = make_client("asha@t.test")
    for url in ("/cases", "/criminals", "/reports", "/users", "/dashboard"):
        assert asha.get(url).status_code == 403


def test_full_lifecycle(app, make_client):
    asha, officer, admin = make_client("asha@t.test"), make_client("officer@t.test"), make_client("admin@t.test")
    file_complaint(asha)
    officer.post("/complaints/1/verify")
    officer.post("/complaints/1/register-case", station_id="1")
    with app.app_context():
        assert one('SELECT status FROM "case" WHERE case_id = 1')["status"] == "Under Investigation"

    # an unassigned case is editable only by an admin
    officer.post("/cases/1/status", status="Chargesheet Filed")
    with app.app_context():
        assert one('SELECT status FROM "case" WHERE case_id = 1')["status"] == "Under Investigation"

    admin.post("/cases/1/assign", officer_id="1")
    officer.post("/cases/1/status", status="Chargesheet Filed")
    officer.post("/cases/1/status", status="Closed (Resolved)")
    with app.app_context():
        assert one('SELECT status FROM "case" WHERE case_id = 1')["status"] == "Closed (Resolved)"
        logs = one("SELECT COUNT(*) AS n FROM status_log WHERE entity = 'case'")["n"]
        assert logs >= 3
        assert one("SELECT COUNT(*) AS n FROM notification WHERE user_id = 4")["n"] >= 3


def test_invalid_transition_is_refused(app, make_client):
    asha, admin = make_client("asha@t.test"), make_client("admin@t.test")
    file_complaint(asha)
    admin.post("/complaints/1/verify")
    admin.post("/complaints/1/register-case", station_id="1")
    admin.post("/cases/1/status", status="Closed (Resolved)")  # skips the chargesheet
    with app.app_context():
        assert one('SELECT status FROM "case" WHERE case_id = 1')["status"] == "Under Investigation"
    assert CASE_TRANSITIONS["Closed (Resolved)"] == []


def test_reject_needs_reason(app, make_client):
    asha, officer = make_client("asha@t.test"), make_client("officer@t.test")
    file_complaint(asha)
    officer.post("/complaints/1/reject", reason="")
    with app.app_context():
        assert one("SELECT status FROM complaint WHERE complaint_id = 1")["status"] == "Filed"
    officer.post("/complaints/1/reject", reason="Duplicate of complaint 7")
    with app.app_context():
        assert one("SELECT status FROM complaint WHERE complaint_id = 1")["status"] == "Rejected"


def test_one_case_per_complaint(app, make_client):
    asha, admin = make_client("asha@t.test"), make_client("admin@t.test")
    file_complaint(asha)
    admin.post("/complaints/1/verify")
    admin.post("/complaints/1/register-case", station_id="1")
    admin.post("/complaints/1/register-case", station_id="1")
    with app.app_context():
        assert one('SELECT COUNT(*) AS n FROM "case"')["n"] == 1


def test_forms_need_csrf(app):
    client = app.test_client()
    assert client.post("/login", data={"email": "admin@t.test", "password": "password123"}).status_code == 400


def test_register_and_login(app):
    client = app.test_client()
    client.get("/register")
    with client.session_transaction() as s:
        s["csrf"] = "tok"
    resp = client.post(
        "/register", data={"name": "New", "email": "new@t.test", "password": "longenough", "csrf": "tok"},
        follow_redirects=True,
    )
    assert b"My complaints" in resp.data
