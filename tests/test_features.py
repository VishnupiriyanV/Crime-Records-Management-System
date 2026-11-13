"""Taking a case, editing and withdrawing a complaint, password reset, e-mail alerts, saved views and file fingerprints."""
import hashlib

from bson import Binary

from app import mailer
from app.mongo import mdb
from tests.test_flow import file_complaint


def open_case(asha, officer):
    file_complaint(asha)
    officer.post("/api/complaints/1/verify")
    assert officer.post("/api/complaints/1/register-case", json={"station_id": 1}).status_code == 200


# ---- an officer takes a case

def test_an_officer_can_take_an_unassigned_case(make_client):
    asha, officer, other = make_client("asha@t.test"), make_client("officer@t.test"), make_client("other@t.test")
    open_case(asha, officer)
    assert officer.post("/api/cases/1/status", json={"status": "Closed (Unresolved)"}).status_code == 400  # not theirs yet
    assert officer.post("/api/cases/1/take").status_code == 200
    case = officer.get("/api/cases/1").json()
    assert case["editable"] is True and case["case"]["officer_name"] == "Officer"
    assert other.post("/api/cases/1/take").status_code == 400  # someone has it now
    assert officer.post("/api/cases/1/take").status_code == 400  # already theirs
    assert any("Assigned to Officer" in e["text"] for e in case["timeline"])


def test_only_an_officer_can_take_and_not_a_closed_case(make_client):
    asha, officer, admin = make_client("asha@t.test"), make_client("officer@t.test"), make_client("admin@t.test")
    open_case(asha, officer)
    assert asha.post("/api/cases/1/take").status_code == 403
    assert admin.post("/api/cases/1/take").status_code == 403
    admin.post("/api/cases/1/status", json={"status": "Closed (Unresolved)"})
    assert officer.post("/api/cases/1/take").status_code == 400


# ---- edit and withdraw

def test_a_citizen_can_correct_a_complaint_until_it_is_reviewed(make_client):
    asha, bina, officer = make_client("asha@t.test"), make_client("bina@t.test"), make_client("officer@t.test")
    file_complaint(asha)
    fixed = {"title": "Bicycle stolen", "description": "Taken from the rack outside the library.",
             "location": "Lake Road", "incident_date": "2026-10-01", "category": "Theft"}
    assert bina.put("/api/complaints/1", json=fixed).status_code == 404
    assert asha.put("/api/complaints/1", json={**fixed, "title": ""}).status_code == 400
    done = asha.put("/api/complaints/1", json=fixed)
    assert done.status_code == 200 and set(done.json()["changed"]) == {"title", "description", "category"}
    got = asha.get("/api/complaints/1").json()
    assert got["complaint"]["title"] == "Bicycle stolen" and got["can_edit"] is True
    assert asha.put("/api/complaints/1", json=fixed).json()["changed"] == []  # nothing new, nothing logged

    officer.post("/api/complaints/1/verify")
    assert asha.put("/api/complaints/1", json=fixed).status_code == 400
    assert asha.get("/api/complaints/1").json()["can_edit"] is False
    officer.post("/api/complaints/1/register-case", json={"station_id": 1})
    edits = [e for e in officer.get("/api/cases/1").json()["timeline"] if e["text"] == "Citizen edited the complaint"]
    assert len(edits) == 1 and "Bike stolen" in edits[0]["detail"]  # the old title is not lost


def test_a_citizen_can_withdraw_before_review_only(make_client):
    asha, officer = make_client("asha@t.test"), make_client("officer@t.test")
    file_complaint(asha)
    file_complaint(asha, title="Second")
    assert officer.post("/api/complaints/1/withdraw").status_code == 403
    assert asha.post("/api/complaints/1/withdraw").status_code == 200
    got = asha.get("/api/complaints/1").json()
    assert got["complaint"]["status"] == "Rejected" and got["complaint"]["reject_reason"] == "Withdrawn by the citizen."
    assert asha.post("/api/complaints/1/withdraw").status_code == 400
    officer.post("/api/complaints/2/verify")
    assert asha.post("/api/complaints/2/withdraw").status_code == 400


# ---- password reset

def test_reset_link_sets_a_new_password_once(make_client, monkeypatch):
    sent = []
    monkeypatch.setattr(mailer, "send", lambda to, subject, text, wait=False, on_fail=None: sent.append((to, text)) or True)
    guest = make_client()
    assert guest.post("/api/auth/forgot", json={"email": "nobody@t.test"}).json() == {"ok": True}
    assert sent == []  # same answer, nothing sent
    assert guest.post("/api/auth/forgot", json={"email": "ASHA@t.test"}).json() == {"ok": True}
    to, text = sent[0]
    token = text.split("token=")[1].split()[0]
    assert to == "asha@t.test" and mdb().password_resets.count_documents({}) == 1
    assert stored_token_is_hashed(token)
    assert guest.post("/api/auth/reset", json={"token": token, "password": "short"}).status_code == 400
    assert guest.post("/api/auth/reset", json={"token": "wrong", "password": "a-new-password"}).status_code == 400
    assert guest.post("/api/auth/reset", json={"token": token, "password": "a-new-password"}).status_code == 200
    assert guest.post("/api/auth/reset", json={"token": token, "password": "another-one-12"}).status_code == 400
    assert guest.post("/api/auth/login", json={"email": "asha@t.test", "password": "password123"}).status_code == 400
    assert guest.post("/api/auth/login", json={"email": "asha@t.test", "password": "a-new-password"}).status_code == 200


def stored_token_is_hashed(token):
    return mdb().password_resets.find_one({"hash": hashlib.sha256(token.encode()).hexdigest()}) is not None and \
        mdb().password_resets.find_one({"hash": token}) is None


def test_an_expired_link_and_the_hourly_limit(make_client, monkeypatch):
    sent = []
    monkeypatch.setattr(mailer, "send", lambda to, subject, text, wait=False, on_fail=None: sent.append(text) or True)
    guest = make_client()
    for _ in range(5):
        guest.post("/api/auth/forgot", json={"email": "asha@t.test"})
    assert len(sent) == 3
    token = sent[0].split("token=")[1].split()[0]
    mdb().password_resets.update_many({}, {"$set": {"expires": 1}})
    assert guest.post("/api/auth/reset", json={"token": token, "password": "a-new-password"}).status_code == 400


def test_an_admin_can_issue_a_temporary_password(make_client):
    admin, asha = make_client("admin@t.test"), make_client("asha@t.test")
    assert asha.post("/api/users/4/reset-password").status_code == 403
    temporary = admin.post("/api/users/4/reset-password").json()["password"]
    assert len(temporary) >= 12
    guest = make_client()
    assert guest.post("/api/auth/login", json={"email": "asha@t.test", "password": "password123"}).status_code == 400
    assert guest.post("/api/auth/login", json={"email": "asha@t.test", "password": temporary}).status_code == 200
    assert admin.post("/api/users/999/reset-password").status_code == 400
    assert any("Password reset by an admin" == e["new_status"] for e in admin.get("/api/audit").json()["items"])


# ---- e-mail alerts

def test_alerts_go_out_by_email_when_a_mail_server_is_set(make_client, monkeypatch):
    sent = []
    monkeypatch.setattr(mailer, "send", lambda to, subject, text, wait=False, on_fail=None: sent.append((to, subject, text)) or True)
    asha, officer = make_client("asha@t.test"), make_client("officer@t.test")
    file_complaint(asha)
    officer.post("/api/complaints/1/verify")
    assert sent == []  # no SMTP_HOST, so alerts stay in the app only
    monkeypatch.setenv("SMTP_HOST", "mail.test")
    monkeypatch.setenv("CRMS_BASE_URL", "https://crms.example")
    file_complaint(asha, title="Second")
    officer.post("/api/complaints/2/verify")
    assert [s[0] for s in sent] == ["asha@t.test"]
    assert "was verified" in sent[0][1] and "https://crms.example/complaints/2" in sent[0][2]


def test_a_person_can_turn_alerts_off(make_client, monkeypatch):
    sent = []
    monkeypatch.setattr(mailer, "send", lambda to, subject, text, wait=False, on_fail=None: sent.append(to) or True)
    monkeypatch.setenv("SMTP_HOST", "mail.test")
    asha, officer = make_client("asha@t.test"), make_client("officer@t.test")
    assert asha.get("/api/profile").json()["email_alerts"] is True
    assert asha.put("/api/profile", json={"name": "Asha", "email_alerts": False}).status_code == 200
    assert asha.get("/api/profile").json()["email_alerts"] is False
    file_complaint(asha)
    officer.post("/api/complaints/1/verify")
    assert sent == []
    assert len(asha.get("/api/notifications").json()["items"]) == 1  # still in the app


# ---- saved views

def test_saved_views_belong_to_one_person(make_client):
    admin, officer = make_client("admin@t.test"), make_client("officer@t.test")
    assert admin.post("/api/views", json={"page": "nowhere", "name": "x", "query": ""}).status_code == 400
    assert admin.post("/api/views", json={"page": "cases", "name": "", "query": ""}).status_code == 400
    made = admin.post("/api/views", json={"page": "cases", "name": "Idle", "query": "?status=Under+Investigation&flag=stale"})
    assert made.status_code == 200
    again = admin.post("/api/views", json={"page": "cases", "name": "Idle", "query": "status=Closed+(Resolved)"})
    mine = admin.get("/api/views?page=cases").json()["items"]
    assert len(mine) == 1 and mine[0]["query"] == "status=Closed+(Resolved)"  # same name replaces
    assert officer.get("/api/views").json()["items"] == []
    assert officer.delete(f"/api/views/{again.json()['view_id']}").status_code == 200
    assert len(admin.get("/api/views").json()["items"]) == 1  # not theirs to delete
    assert admin.delete(f"/api/views/{mine[0]['view_id']}").status_code == 200
    assert admin.get("/api/views").json()["items"] == []


def test_a_list_holds_twenty_views_at_most(make_client):
    admin = make_client("admin@t.test")
    for i in range(20):
        assert admin.post("/api/views", json={"page": "complaints", "name": f"v{i}", "query": "status=Filed"}).status_code == 200
    assert admin.post("/api/views", json={"page": "complaints", "name": "one more", "query": ""}).status_code == 400


# ---- file fingerprints

def test_an_uploaded_file_is_fingerprinted_and_a_swap_is_caught(make_client):
    asha, officer, admin = make_client("asha@t.test"), make_client("officer@t.test"), make_client("admin@t.test")
    open_case(asha, officer)
    admin.post("/api/cases/1/assign", json={"officer_id": 1})
    officer.post("/api/cases/1/evidence", json={"type": "Photo", "description": "Rack"})
    data = b"\x89PNG original photo"
    assert officer.post("/api/cases/1/evidence/1/files", files={"file": ("rack.png", data, "image/png")}).status_code == 200
    asha.post("/api/complaints/1/attachments", files={"file": ("note.txt", b"my note", "text/plain")})
    case = officer.get("/api/cases/1").json()
    assert case["evidence"][0]["files"][0]["sha256"] == hashlib.sha256(data).hexdigest()
    assert any("SHA-256 " + hashlib.sha256(data).hexdigest()[:16] in e["detail"] for e in case["timeline"])
    assert officer.get("/api/cases/1/integrity").json()["ok"] is True

    stored = mdb().attachments.find_one({"filename": "rack.png"})
    mdb().attachment_files.update_one({"attachment_id": stored["attachment_id"]}, {"$set": {"data": Binary(b"\x89PNG swapped")}})
    report = officer.get("/api/cases/1/integrity").json()
    assert report["ok"] is False and any("rack.png" in p and "fingerprint" in p for p in report["problems"])


def test_links_that_could_not_be_sent_do_not_use_up_the_hourly_limit(make_client, monkeypatch):
    class Now:  # run the background send on the spot so the test can look at the result
        def __init__(self, target, args=(), daemon=None):
            self.target, self.args = target, args

        def start(self):
            self.target(*self.args)

    monkeypatch.setattr(mailer.threading, "Thread", Now)
    monkeypatch.setenv("SMTP_HOST", "mail.test")
    monkeypatch.setenv("CRMS_BASE_URL", "https://crms.example")
    tried = []
    guest = make_client()

    monkeypatch.setattr(mailer, "_deliver", lambda message: tried.append(1) or False)  # the mail server cannot be reached
    for _ in range(5):
        guest.post("/api/auth/forgot", json={"email": "asha@t.test"})
    assert len(tried) == 5 and mdb().password_resets.count_documents({}) == 0

    monkeypatch.setattr(mailer, "_deliver", lambda message: tried.append(1) or True)  # it is back
    for _ in range(5):
        guest.post("/api/auth/forgot", json={"email": "asha@t.test"})
    assert len(tried) == 5 + 3  # now the limit of three an hour applies
    assert mdb().password_resets.count_documents({}) == 3
