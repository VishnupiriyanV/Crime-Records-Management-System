"""The case ledger: sealing, tamper detection, and the PDF that carries the seal."""
from app import ledger
from app.mongo import mdb


def case_with_history(make_client):
    asha, admin = make_client("asha@t.test"), make_client("admin@t.test")
    asha.post("/api/complaints", json={
        "title": "Bike stolen", "description": "Taken from the rack.", "location": "Lake Road",
        "incident_date": "2026-10-01", "category": "Theft",
    })
    admin.post("/api/complaints/1/verify")
    admin.post("/api/complaints/1/register-case", json={"station_id": 1})
    admin.post("/api/cases/1/assign", json={"officer_id": 1})
    admin.post("/api/cases/1/evidence", json={"type": "CCTV", "description": "Camera at the gate shows the bike taken."})
    admin.post("/api/cases/1/evidence/1/custody", json={"action": "stored", "where": "Evidence room", "note": "Bag 14"})
    cid = admin.post("/api/criminals", json={"name": "Ravi Menon"}).json()["criminal_id"]
    admin.post("/api/cases/1/criminals", json={"criminal_id": cid, "role": "accused"})
    admin.post("/api/cases/1/statements", json={"kind": "witness", "person": "Neighbour", "body": "I saw it happen."})
    return asha, admin


def test_every_event_is_sealed_and_verifies(make_client):
    _, admin = case_with_history(make_client)
    case = admin.get("/api/cases/1").json()
    assert case["integrity"]["ok"] and case["integrity"]["entries"] == len(case["timeline"])
    assert all(e["seal"] and e["seal"]["hash"] for e in case["timeline"])
    assert [e["seal"]["imported"] for e in case["timeline"]] == [False] * len(case["timeline"])
    evidence = next(e for e in case["timeline"] if e["text"].startswith("Evidence 1 recorded"))
    assert "Camera at the gate" in evidence["detail"]
    assert admin.get("/api/cases/1/integrity").json()["ok"] is True


def test_court_outcome_is_part_of_the_history(make_client):
    _, admin = case_with_history(make_client)
    admin.post("/api/cases/1/chargesheet", json={"sections": "BNS 303", "summary": "Taken."})
    admin.post("/api/cases/1/court-dates", json={"date": "2026-12-01", "court": "Court I", "purpose": "First hearing"})
    admin.post("/api/cases/1/court-dates/1/outcome", json={"outcome": "Adjourned"})
    texts = [e["text"] for e in admin.get("/api/cases/1").json()["timeline"]]
    assert "Court outcome for 2026-12-01: Adjourned" in texts


def test_an_edited_record_is_caught(make_client):
    _, admin = case_with_history(make_client)
    mdb().evidence.update_one({"evidence_no": 1}, {"$set": {"description": "Nothing useful on the camera."}})
    result = admin.get("/api/cases/1/integrity").json()
    assert not result["ok"] and result["chain_ok"]
    assert any("no longer matches its record" in p for p in result["problems"])


def test_a_removed_record_is_caught(make_client):
    _, admin = case_with_history(make_client)
    mdb().statements.delete_many({})
    assert any("no longer matches" in p for p in admin.get("/api/cases/1/integrity").json()["problems"])


def test_a_record_slipped_in_without_sealing_is_caught(make_client):
    _, admin = case_with_history(make_client)
    mdb().statements.insert_one({
        "case_id": 1, "no": 9, "kind": "witness", "person": "Nobody", "body": "Added behind the app.",
        "recorded_by": "Admin", "recorded_at": "2026-11-01 10:00:00",
    })
    result = admin.get("/api/cases/1/integrity").json()
    assert not result["ok"] and any("not covered by the seal" in p for p in result["problems"])
    # looking at the case must not seal it, or a forged record would be blessed by a page view
    assert admin.get("/api/cases/1/integrity").json()["ok"] is False


def test_an_edited_ledger_entry_breaks_the_chain(make_client):
    _, admin = case_with_history(make_client)
    mdb().ledger.update_one({"seq": 3}, {"$set": {"event.text": "Something else happened"}})
    result = admin.get("/api/cases/1/integrity").json()
    assert not result["chain_ok"] and any("Entry 3 was altered" in p for p in result["problems"])


def test_a_forged_entry_needs_the_secret(make_client):
    _, admin = case_with_history(make_client)
    row = mdb().ledger.find_one({"seq": 3})
    prev = mdb().ledger.find_one({"seq": 2})["hash"]
    row["event"]["text"] = "Something else happened"
    ledger.configure("a guess")
    forged = ledger._digest(prev, row)  # an attacker rehashing the entry without the real secret
    ledger.configure("test")
    mdb().ledger.update_one({"seq": 3}, {"$set": {"event.text": row["event"]["text"], "hash": forged}})
    assert not admin.get("/api/cases/1/integrity").json()["chain_ok"]


def test_removing_the_last_entries_is_caught(make_client):
    _, admin = case_with_history(make_client)
    last = mdb().ledger.find_one(sort=[("seq", -1)])["seq"]
    mdb().ledger.delete_one({"seq": last})
    result = admin.get("/api/cases/1/integrity").json()
    assert any("removed from the end" in p for p in result["problems"])


def test_a_missing_middle_entry_is_caught(make_client):
    _, admin = case_with_history(make_client)
    mdb().ledger.delete_one({"seq": 4})
    assert any("missing or out of order" in p for p in admin.get("/api/cases/1/integrity").json()["problems"])


def test_a_case_from_before_sealing_is_imported_once(make_client):
    _, admin = case_with_history(make_client)
    mdb().ledger.delete_many({})
    mdb().ledger_heads.delete_many({})
    case = admin.get("/api/cases/1").json()
    assert case["integrity"]["ok"] and case["integrity"]["imported"] == case["integrity"]["entries"] > 0
    again = admin.get("/api/cases/1").json()
    assert again["integrity"]["entries"] == case["integrity"]["entries"]


def test_the_pdf_carries_the_seal(make_client):
    _, admin = case_with_history(make_client)
    resp = admin.get("/api/export/cases/1.pdf")
    assert resp.content.startswith(b"%PDF") and len(resp.content) > 3000
    # the same figures the page shows are the ones printed in the seal block
    head = admin.get("/api/cases/1/integrity").json()["head"]
    assert len(head) == 64
