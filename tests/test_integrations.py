"""API tokens, webhooks and the JSON export that other systems use."""
import hashlib
import hmac
import json

from fastapi.testclient import TestClient

from app import webhooks


def file_complaint(asha):
    return asha.post("/api/complaints", json={
        "title": "Shop window broken", "description": "Found smashed.", "location": "Market Street",
        "incident_date": "2026-10-02", "category": "Vandalism",
    }).json()["complaint_id"]


def bearer(app, token):
    # no cookie and no X-Requested-With header: this is how another system calls
    return TestClient(app, headers={"Authorization": f"Bearer {token}"})


def test_token_lets_a_script_in_without_a_browser(app, make_client):
    admin, asha = make_client("admin@t.test"), make_client("asha@t.test")
    file_complaint(asha)
    token = admin.post("/api/tokens", json={"name": "Court feed", "scope": "read"}).json()["token"]

    listed = admin.get("/api/tokens").json()["items"]
    assert listed[0]["name"] == "Court feed" and "hash" not in listed[0] and token not in json.dumps(listed)

    script = bearer(app, token)
    assert script.get("/api/complaints").json()["total"] == 1
    assert script.post("/api/complaints/1/verify").status_code == 403  # read-only
    assert script.get("/api/users").status_code == 403  # tokens never manage people
    assert script.get("/api/tokens").status_code == 403
    assert bearer(app, "crms_wrong").get("/api/complaints").status_code == 401

    # a cookie alone still needs the request header
    cookie_only = TestClient(app)
    cookie_only.post("/api/auth/login", json={"email": "admin@t.test", "password": "password123"}, headers={"X-Requested-With": "crms"})
    assert cookie_only.post("/api/complaints/1/verify").status_code == 400


def test_write_token_and_revoking(app, make_client):
    admin, asha = make_client("admin@t.test"), make_client("asha@t.test")
    file_complaint(asha)
    token = admin.post("/api/tokens", json={"name": "Importer", "scope": "write"}).json()["token"]
    assert bearer(app, token).post("/api/complaints/1/verify").status_code == 200

    token_id = admin.get("/api/tokens").json()["items"][0]["token_id"]
    assert admin.delete(f"/api/tokens/{token_id}").status_code == 200
    assert bearer(app, token).get("/api/complaints").status_code == 401
    assert make_client("asha@t.test").post("/api/tokens", json={"name": "x", "scope": "read"}).status_code == 403
    assert admin.post("/api/tokens", json={"name": "x", "scope": "root"}).status_code == 400


def test_webhooks_are_signed_and_filtered(app, make_client, monkeypatch):
    sent = []

    class Reply:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *a): return False

    monkeypatch.setattr(webhooks, "ASYNC", False)
    monkeypatch.setattr(webhooks.urllib.request, "urlopen", lambda req, timeout=0: sent.append(req) or Reply())
    webhooks.forget()

    admin, asha = make_client("admin@t.test"), make_client("asha@t.test")
    made = admin.post("/api/webhooks", json={"url": "https://example.test/hook", "events": ["complaint.filed", "case.opened"]}).json()
    assert admin.get("/api/webhooks").json()["items"][0]["url"] == "https://example.test/hook"
    assert "secret" not in admin.get("/api/webhooks").json()["items"][0]

    file_complaint(asha)
    admin.post("/api/complaints/1/verify")  # complaint.status_changed is not subscribed
    admin.post("/api/complaints/1/register-case", json={"station_id": 1})
    events = [r.get_header("X-crms-event") for r in sent]
    assert events == ["complaint.filed", "case.opened"]

    first = sent[0]
    expected = hmac.new(made["secret"].encode(), first.data, hashlib.sha256).hexdigest()
    assert first.get_header("X-crms-signature") == f"sha256={expected}"
    body = json.loads(first.data)
    assert body["fir"].startswith("FIR/") and body["to"] == "Filed" and body["category"] == "Vandalism"
    assert "description" not in body and "title" not in body  # nothing personal goes out

    assert admin.post("/api/webhooks", json={"url": "ftp://x", "events": []}).status_code == 400
    assert admin.post("/api/webhooks", json={"url": "https://example.test", "events": ["nope"]}).status_code == 400
    assert admin.delete(f"/api/webhooks/{made['webhook_id']}").status_code == 200
    sent.clear()
    admin.post("/api/complaints/1/classify", json={"category": "Theft", "severity": "High"})
    assert sent == []


def test_fir_export(app, make_client):
    admin, asha = make_client("admin@t.test"), make_client("asha@t.test")
    file_complaint(asha)
    admin.post("/api/complaints/1/verify")
    admin.post("/api/complaints/1/register-case", json={"station_id": 1})
    cid = admin.post("/api/criminals", json={"name": "Ravi Menon"}).json()["criminal_id"]
    admin.post("/api/cases/1/criminals", json={"criminal_id": cid, "role": "suspect"})

    one = admin.get("/api/export/fir/1").json()
    assert one["schema"] == "crms.fir/1" and one["fir_number"].startswith("FIR/")
    assert one["case"]["station"] == "Central" and one["case"]["persons"] == [{"name": "Ravi Menon", "role": "suspect"}]
    assert one["case"]["chargesheet"] is None and one["complainant"] == "Asha"

    page = admin.get("/api/export/firs?since=2000-01-01").json()
    assert page["total"] == 1 and page["items"][0]["fir_number"] == one["fir_number"]
    assert admin.get("/api/export/firs?since=yesterday").status_code == 400
    assert admin.get("/api/export/fir/99").status_code == 404
    assert asha.get("/api/export/fir/1").status_code == 403
