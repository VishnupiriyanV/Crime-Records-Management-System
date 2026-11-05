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
