"""Overdue flags and duplicate detection."""
from datetime import date, timedelta

from app import db
from app.overdue import case_flags, complaint_flags
from app.similar import compare


def days_ago(n):
    return (date.today() - timedelta(days=n)).isoformat()


def age(app, sql, *args):
    """Move dates into the past, which the app itself never does."""
    token = db.use(db.connect(app.state.database_url))
    try:
        db.run(sql, *args)
        db.get_db().commit()
    finally:
        db.release(token)


def file_one(client, title="Bike stolen", where="Bus stand", day="2026-10-02", text="My bike was stolen near the bus stand."):
    return client.post("/api/complaints", json={
        "title": title, "description": text, "location": where, "incident_date": day, "category": "Theft",
    }).json()["complaint_id"]


def test_complaint_waiting_too_long_is_flagged(app, make_client):
    asha, admin = make_client("asha@t.test"), make_client("admin@t.test")
    file_one(asha)
    assert admin.get("/api/complaints").json()["items"][0]["flags"] == []

    age(app, "UPDATE complaint SET date_filed = ?", days_ago(5))
    flagged = admin.get("/api/complaints").json()["items"][0]["flags"]
    assert flagged[0]["kind"] == "unreviewed" and flagged[0]["days"] == 5
    assert admin.get("/api/complaints/1").json()["flags"][0]["kind"] == "unreviewed"
    assert "flags" not in asha.get("/api/complaints/1").json() or asha.get("/api/complaints/1").json()["flags"] == []
    assert asha.get("/api/complaints").json()["items"][0]["flags"] == []  # citizens are not shown staff deadlines

    admin.post("/api/complaints/1/verify")
    assert admin.get("/api/complaints").json()["items"][0]["flags"] == []


def test_high_severity_waits_half_as_long():
    row = {"complaint_id": 1, "status": "Filed", "date_filed": days_ago(1), "severity": "Medium"}
    assert complaint_flags([row]) == {}
    assert 1 in complaint_flags([{**row, "severity": "High"}])


def test_open_case_flags(app, make_client):
    asha, admin = make_client("asha@t.test"), make_client("admin@t.test")
    file_one(asha)
    admin.post("/api/complaints/1/verify")
    admin.post("/api/complaints/1/register-case", json={"station_id": 1})
    assert admin.get("/api/cases/1").json()["flags"] == []

    age(app, "UPDATE crime_case SET date_opened = ?", days_ago(20))
    from app.mongo import mdb
    mdb().status_log.update_many({}, {"$set": {"changed_at": f"{days_ago(20)} 09:00:00"}})  # the opening was that long ago too
    kinds = {f["kind"] for f in admin.get("/api/cases/1").json()["flags"]}
    assert kinds == {"unassigned", "stale"}
    assert {f["kind"] for f in admin.get("/api/cases").json()["items"][0]["flags"]} == kinds

    # any work on the case resets the quiet period
    admin.post("/api/cases/1/assign", json={"officer_id": 1})
    admin.post("/api/cases/1/evidence", json={"type": "CCTV", "description": "Camera at the stand."})
    assert admin.get("/api/cases/1").json()["flags"] == []


def test_hearing_without_outcome_is_flagged(app, make_client):
    asha, admin = make_client("asha@t.test"), make_client("admin@t.test")
    file_one(asha)
    admin.post("/api/complaints/1/verify")
    admin.post("/api/complaints/1/register-case", json={"station_id": 1})
    admin.post("/api/cases/1/assign", json={"officer_id": 1})
    cid = admin.post("/api/criminals", json={"name": "Ravi Menon"}).json()["criminal_id"]
    admin.post("/api/cases/1/criminals", json={"criminal_id": cid, "role": "accused"})
    admin.post("/api/cases/1/chargesheet", json={"sections": "379 IPC", "summary": "Stolen bike."})
    admin.post("/api/cases/1/court-dates", json={"date": days_ago(-3), "court": "District court", "purpose": "First hearing"})
    assert admin.get("/api/cases/1").json()["flags"] == []

    from app.mongo import mdb
    mdb().court_dates.update_many({}, {"$set": {"date": days_ago(2)}})
    assert [f["kind"] for f in admin.get("/api/cases/1").json()["flags"]] == ["hearing"]


def test_attention_summary(app, make_client):
    asha, admin = make_client("asha@t.test"), make_client("admin@t.test")
    file_one(asha)
    age(app, "UPDATE complaint SET date_filed = ?", days_ago(9))
    got = admin.get("/api/attention").json()
    assert got["counts"]["unreviewed"] == 1 and got["items"][0]["link"] == "/complaints/1"
    assert got["items"][0]["fir"].startswith("FIR/")
    assert asha.get("/api/attention").status_code == 403


def test_similarity_scores():
    a = {"title": "Bike stolen", "description": "My bike was stolen near the bus stand", "location": "bus stand",
         "incident_date": "2026-11-08", "category": "Theft", "latitude": None, "longitude": None}
    same = {**a, "title": "Bicycle theft", "description": "Someone stole my bike at the bus stand", "location": "Bus stand, Pondicherry"}
    other = {**a, "title": "Window smashed", "description": "Shop window broken overnight", "location": "Market Street",
             "incident_date": "2026-09-01", "category": "Vandalism"}
    assert compare(a, same)[0] >= 0.5 and compare(a, other)[0] < 0.3

    near, far = {**a, "latitude": 11.9416, "longitude": 79.8083}, {**a, "latitude": 12.5, "longitude": 80.1}
    assert "same place" in compare(near, {**near, "latitude": 11.9420})[1]
    assert "same place" not in compare(near, far)[1]


def test_duplicate_warning_on_the_form_and_for_staff(make_client):
    asha, bina, admin = make_client("asha@t.test"), make_client("bina@t.test"), make_client("admin@t.test")
    file_one(asha)
    draft = {"title": "Bicycle theft", "description": "Someone stole my bike at the bus stand", "location": "Bus stand",
             "incident_date": "2026-10-02", "category": "Theft"}

    mine = asha.post("/api/complaints/check", json=draft).json()["items"]
    assert len(mine) == 1 and mine[0]["fir_no"].startswith("FIR/") and "reasons" in mine[0]
    assert bina.post("/api/complaints/check", json=draft).json()["items"] == []  # nobody sees another person's complaint

    second = file_one(bina, "Bicycle theft", "Bus stand", "2026-10-02", "Someone stole my bike at the bus stand")
    related = admin.get(f"/api/complaints/{second}/similar").json()["items"]
    assert [r["complaint_id"] for r in related] == [1]
    assert asha.get(f"/api/complaints/{second}/similar").status_code == 403
    assert admin.post("/api/complaints/check", json={"title": "x", "description": "nothing alike", "location": "elsewhere",
                                                      "incident_date": "2026-10-02"}).json()["items"] == []
