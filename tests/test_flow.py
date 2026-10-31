from app.lifecycle import CASE_TRANSITIONS




def file_complaint(client, title="Bike stolen"):
    return client.post("/api/complaints", json={
        "title": title, "description": "Taken from the rack.",
        "location": "Lake Road", "incident_date": "2026-10-01",
    })


def test_citizen_sees_only_own_complaints(make_client):
    asha, bina = make_client("asha@t.test"), make_client("bina@t.test")
    file_complaint(asha)
    assert len(asha.get("/api/complaints").json()["items"]) == 1
    assert bina.get("/api/complaints").json()["items"] == []
    assert bina.get("/api/complaints/1").status_code == 404


def test_citizen_cannot_use_staff_endpoints(make_client):
    asha = make_client("asha@t.test")
    for url in ("/api/cases", "/api/criminals", "/api/reports", "/api/users", "/api/dashboard"):
        assert asha.get(url).status_code == 403


def test_signed_out_gets_401(make_client):
    assert make_client().get("/api/complaints").status_code == 401


def test_full_lifecycle(app, make_client):
    asha, officer, admin = make_client("asha@t.test"), make_client("officer@t.test"), make_client("admin@t.test")
    file_complaint(asha)
    assert officer.post("/api/complaints/1/verify").status_code == 200
    assert officer.post("/api/complaints/1/register-case", json={"station_id": 1}).status_code == 200

    # an unassigned case is editable only by an admin
    assert officer.post("/api/cases/1/status", json={"status": "Chargesheet Filed"}).status_code == 400

    admin.post("/api/cases/1/assign", json={"officer_id": 1})
    assert officer.post("/api/cases/1/status", json={"status": "Chargesheet Filed"}).status_code == 200
    assert officer.post("/api/cases/1/status", json={"status": "Closed (Resolved)"}).status_code == 200
    case = officer.get("/api/cases/1").json()
    assert case["case"]["status"] == "Closed (Resolved)"
    assert case["editable"] is False
    assert len(case["history"]) >= 3
    assert len(asha.get("/api/notifications").json()["items"]) >= 3


def test_invalid_transition_is_refused(make_client):
    asha, admin = make_client("asha@t.test"), make_client("admin@t.test")
    file_complaint(asha)
    admin.post("/api/complaints/1/verify")
    admin.post("/api/complaints/1/register-case", json={"station_id": 1})
    resp = admin.post("/api/cases/1/status", json={"status": "Closed (Resolved)"})  # skips the chargesheet
    assert resp.status_code == 400
    assert admin.get("/api/cases/1").json()["case"]["status"] == "Under Investigation"
    assert CASE_TRANSITIONS["Closed (Resolved)"] == []


def test_reject_needs_reason(make_client):
    asha, officer = make_client("asha@t.test"), make_client("officer@t.test")
    file_complaint(asha)
    assert officer.post("/api/complaints/1/reject", json={"reason": ""}).status_code == 400
    assert officer.post("/api/complaints/1/reject", json={"reason": "Duplicate of complaint 7"}).status_code == 200
    assert officer.get("/api/complaints/1").json()["complaint"]["status"] == "Rejected"


def test_one_case_per_complaint(make_client):
    asha, admin = make_client("asha@t.test"), make_client("admin@t.test")
    file_complaint(asha)
    admin.post("/api/complaints/1/verify")
    assert admin.post("/api/complaints/1/register-case", json={"station_id": 1}).status_code == 200
    assert admin.post("/api/complaints/1/register-case", json={"station_id": 1}).status_code == 400
    assert admin.get("/api/cases").json()["total"] == 1


def test_writes_need_the_request_header(app):
    from fastapi.testclient import TestClient
    bare = TestClient(app)
    resp = bare.post("/api/auth/login", json={"email": "admin@t.test", "password": "password123"})
    assert resp.status_code == 400


def test_register_and_login(app):
    from fastapi.testclient import TestClient
    client = TestClient(app, headers={"X-Requested-With": "crms"})
    resp = client.post("/api/auth/register", json={"name": "New", "email": "new@t.test", "password": "longenough"})
    assert resp.status_code == 200
    assert client.get("/api/auth/me").json()["user"]["role"] == "citizen"
    assert client.post("/api/auth/register", json={"name": "New", "email": "new@t.test", "password": "longenough"}).status_code == 400


def test_evidence_and_notes_are_stored_in_mongo(app, make_client):
    asha, admin = make_client("asha@t.test"), make_client("admin@t.test")
    file_complaint(asha)
    asha.post("/api/complaints/1/notes", json={"kind": "statement", "body": "I saw it happen."})
    admin.post("/api/complaints/1/verify")
    admin.post("/api/complaints/1/register-case", json={"station_id": 1})
    admin.post("/api/cases/1/evidence", json={"type": "CCTV", "description": "Camera at the gate."})
    admin.post("/api/cases/1/evidence", json={"type": "Photo", "description": "Broken lock."})

    case = admin.get("/api/cases/1").json()
    assert [e["evidence_no"] for e in case["evidence"]] == [1, 2]
    assert case["notes"][0]["body"] == "I saw it happen."
    assert [h["new_status"] for h in case["history"]] == ["Under Investigation"]
