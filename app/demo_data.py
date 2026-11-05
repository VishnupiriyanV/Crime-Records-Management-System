"""Sample records for demos: python -m app.seed --bulk 300

Everything here is made up. Names, places and incidents are invented, and the legal sections are
only labels so the chargesheet screens have something to show.
"""
import random
from datetime import date, timedelta

from . import db
from .auth import hash_password
from .constants import CATEGORIES
from .db import many, one, run
from .mongo import mdb

# station name -> (latitude, longitude, phone, areas people file complaints from)
STATIONS = {
    "Central Station": (13.0827, 80.2707, "044 2345 0101", ["Parry's Corner", "Mannady", "Park Town", "Egmore"]),
    "Riverside Station": (13.0067, 80.2570, "044 2345 0102", ["Adyar Bridge", "Besant Nagar", "Indira Nagar", "Kotturpuram"]),
    "North Hills Station": (13.1067, 80.2206, "044 2345 0103", ["Anna Nagar West", "Koyambedu", "Ambattur Road", "Villivakkam"]),
    "T. Nagar Station": (13.0418, 80.2341, "044 2345 0104", ["Pondy Bazaar", "Usman Road", "West Mambalam", "Panagal Park"]),
    "Mylapore Station": (13.0368, 80.2676, "044 2345 0105", ["Luz Corner", "Santhome High Road", "Alwarpet", "Royapettah"]),
}
AREA_NAMES = {
    "T. Nagar Station": "T. Nagar and West Mambalam", "Mylapore Station": "Mylapore and Alwarpet",
}

FIRST = ["Asha", "Bina", "Chitra", "Deepak", "Esha", "Farhan", "Gautam", "Hema", "Imran", "Jaya", "Kiran", "Lata",
         "Manoj", "Nisha", "Omar", "Priya", "Rahul", "Sana", "Tarun", "Uma", "Vikram", "Waseem", "Yamini", "Zoya"]
LAST = ["Nair", "Iyer", "Reddy", "Khan", "Menon", "Pillai", "Sharma", "Das", "Joseph", "Naidu", "Rao", "Banerjee", "Singh", "Kumar"]
RANKS = ["Inspector", "Inspector", "Sub-Inspector", "Sub-Inspector", "Head Constable"]

# category -> (weight, severity weights low/medium/high, section, [(title, description)])
CRIMES = {
    "Theft": (26, (4, 5, 1), "BNS 303", [
        ("Phone snatched near the bus stop", "Two men on a bike took my phone from my hand and rode off towards the main road."),
        ("Bag stolen from a shop counter", "I turned away for a moment and my handbag with cash and cards was gone."),
        ("Bicycle stolen from outside the library", "The lock was cut and the bicycle taken some time between morning and evening."),
    ]),
    "Burglary": (9, (1, 4, 5), "BNS 331", [
        ("House broken into while away", "We came back from a trip to find the back door forced and cupboards emptied."),
        ("Shop shutter broken at night", "The shutter was prised open overnight and stock and the cash box were taken."),
    ]),
    "Assault": (10, (2, 5, 3), "BNS 115", [
        ("Attacked after an argument over parking", "A neighbour hit me during an argument and I needed treatment at the clinic."),
        ("Beaten outside a tea stall", "A group of men started a fight and hurt me and my friend before leaving."),
    ]),
    "Fraud": (13, (2, 5, 3), "BNS 318", [
        ("Paid for goods that never arrived", "I transferred money to an online seller who stopped answering and sent nothing."),
        ("Fake job offer took a deposit", "A person offered me a job, took a registration fee and then disappeared."),
        ("Cheated in a property deal", "I paid an advance for a plot that the seller did not own."),
    ]),
    "Cybercrime": (12, (1, 4, 5), "IT Act 66D", [
        ("Bank account emptied after a fake call", "A caller pretending to be from my bank got an OTP and money left my account."),
        ("Social media account hacked", "Someone took over my account and asked my contacts for money."),
        ("Card used for purchases I did not make", "Several online payments I never made appeared on my card statement."),
    ]),
    "Vandalism": (6, (6, 3, 1), "BNS 324", [
        ("Car windows smashed overnight", "I found my parked car with the windows broken and a mirror torn off in the morning."),
        ("Shop sign and glass damaged", "Our shop front glass and signboard were broken during the night."),
    ]),
    "Missing person": (4, (0, 3, 7), "Missing person inquiry", [
        ("Teenager has not come home", "My son left for school and has not returned, and his phone is switched off."),
        ("Elderly relative wandered away", "My father has memory problems and left the house this morning without telling anyone."),
    ]),
    "Domestic violence": (5, (0, 4, 6), "BNS 85", [
        ("Repeated harassment at home", "I am being threatened and hurt by relatives at home and I need protection."),
    ]),
    "Traffic": (9, (5, 4, 1), "MV Act 184", [
        ("Hit by a speeding vehicle at the crossing", "A vehicle ran the signal, hit my scooter and did not stop."),
        ("Rash driving damaged my parked car", "A driver reversed into my car, left a dent and drove away."),
    ]),
    "Other": (6, (6, 3, 1), "As per FIR", [
        ("Noise and threats from a neighbour", "A neighbour keeps playing loud music late and has threatened us when we asked him to stop."),
        ("Lost documents found misused", "I lost an envelope with my documents and now see them used in an application."),
    ]),
}

CRIMINAL_HISTORY = [
    "Earlier conviction for theft.", "Arrested twice for chain snatching.", "Charged in a cheating case in 2023.",
    "Known for vehicle theft in the eastern wards.", "Linked to an online fraud ring, case pending.",
    "Released on bail after an assault charge.", "Two burglary cases, one closed.", "No convictions, named in several complaints.",
]
EVIDENCE = [
    ("CCTV footage", "Footage from the nearby shop camera covering the time of the incident."),
    ("Photograph", "Photographs of the scene taken by the investigating officer."),
    ("Fingerprints", "Prints lifted from the door and the counter."),
    ("Bank statement", "Statement showing the disputed transactions."),
    ("Mobile phone", "Phone seized for examination."),
    ("Weapon", "Object recovered close to the scene."),
]
CUSTODY_PLACES = ["Evidence room, shelf 2", "Forensic lab", "Station locker 4", "Evidence room, shelf 5"]
COURTS = ["Magistrate Court 2", "Metropolitan Magistrate Court 4", "Sessions Court", "Fast Track Court 1"]
PURPOSES = ["First hearing", "Framing of charges", "Evidence of witnesses", "Arguments"]
WITNESS_STATEMENTS = [
    "I was standing nearby and saw what happened. I can identify the person if I see him again.",
    "I heard shouting and came out. The person ran towards the main road.",
    "I have known the accused for some years. He was in the area that evening.",
]
VICTIM_STATEMENTS = [
    "Everything in my complaint is correct. I can show the place if needed.",
    "I did not know the person. I noticed him only when it happened.",
]


# the hour each kind of event happens at, so several events on one day stay in a sensible order
HOUR = {
    "filed": 9, "verified": 10, "opened": 11, "assigned": 12, "evidence": 13, "custody": 14,
    "statement": 15, "arrest": 16, "sheet": 17, "status": 18, "court": 19, "closed": 20,
}


def _when(day, rng, kind):
    return f"{day.isoformat()} {HOUR[kind]:02d}:{rng.randint(0, 59):02d}:{rng.randint(0, 59):02d}"


def _pick_weighted(rng, items, weights):
    return rng.choices(items, weights=weights, k=1)[0]


def _ensure_stations():
    ids = {}
    for name, (lat, lng, phone, areas) in STATIONS.items():
        row = one("SELECT station_id FROM police_station WHERE name = ?", name)
        if row is None:
            ids[name] = run(
                "INSERT INTO police_station (name, jurisdiction, phone, latitude, longitude) VALUES (?, ?, ?, ?, ?)",
                name, AREA_NAMES.get(name, ", ".join(areas[:2])), phone, lat, lng,
            )
        else:
            ids[name] = row["station_id"]
            run("UPDATE police_station SET phone = ?, latitude = ?, longitude = ? WHERE station_id = ?",
                phone, lat, lng, row["station_id"])
    return ids


def _add_user(name, email, role):
    return run(
        "INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)",
        name, email, hash_password("password123"), role,
    )


def _ensure_officers(rng, station_ids):
    """Give every station two or three officers; returns {station_id: [officer_id, ...]}."""
    staff = {sid: [] for sid in station_ids.values()}
    for r in many("SELECT officer_id, station_id FROM officer"):
        staff.setdefault(r["station_id"], []).append(r["officer_id"])
    badge = 2000
    for sid in station_ids.values():
        while len(staff[sid]) < rng.choice([2, 3]):
            badge += 1
            name = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
            user_id = _add_user(name, f"officer{badge}@crms.test", "officer")
            officer_id = run(
                "INSERT INTO officer (user_id, badge_no, officer_rank, station_id) VALUES (?, ?, ?, ?)",
                user_id, f"B-{badge}", rng.choice(RANKS), sid,
            )
            staff[sid].append(officer_id)
    return staff


def _ensure_citizens(rng, wanted=40):
    existing = [r["citizen_id"] for r in many("SELECT citizen_id FROM citizen")]
    n = 0
    while len(existing) < wanted:
        n += 1
        first, last = rng.choice(FIRST), rng.choice(LAST)
        user_id = _add_user(f"{first} {last}", f"{first}.{last}.{n}@example.test".lower(), "citizen")
        existing.append(run("INSERT INTO citizen (user_id, address) VALUES (?, ?)", user_id, f"{rng.randint(1, 99)} {rng.choice(LAST)} Street"))
    return existing


def _ensure_criminals(rng, wanted=30):
    ids = [r["criminal_id"] for r in many("SELECT criminal_id FROM criminal")]
    while len(ids) < wanted:
        ids.append(run(
            "INSERT INTO criminal (name, age, crime_history, wanted) VALUES (?, ?, ?, ?)",
            f"{rng.choice(FIRST)} {rng.choice(LAST)}", rng.randint(19, 58), rng.choice(CRIMINAL_HISTORY), int(rng.random() < 0.25),
        ))
    return ids


def _place(rng, station_name):
    lat, lng, _, areas = STATIONS[station_name]
    # most incidents cluster around a few spots near the station, the rest are scattered
    if rng.random() < 0.55:
        spot = random.Random(sum(map(ord, station_name)) + rng.randint(0, 2))
        lat += spot.uniform(-0.012, 0.012)
        lng += spot.uniform(-0.012, 0.012)
        return round(lat + rng.gauss(0, 0.002), 6), round(lng + rng.gauss(0, 0.002), 6), rng.choice(areas)
    return round(lat + rng.gauss(0, 0.012), 6), round(lng + rng.gauss(0, 0.012), 6), rng.choice(areas)


def generate(count=300, seed=2026):
    rng = random.Random(seed)
    today = date.today()
    station_ids = _ensure_stations()
    station_names = {v: k for k, v in station_ids.items()}
    staff = _ensure_officers(rng, station_ids)
    citizens = _ensure_citizens(rng)
    criminals = _ensure_criminals(rng)
    chargeable = []
    log = mdb().status_log

    categories = list(CRIMES)
    cat_weights = [CRIMES[c][0] for c in categories]

    for _ in range(count):
        category = _pick_weighted(rng, categories, cat_weights)
        _, sev_weights, section, templates = CRIMES[category]
        severity = _pick_weighted(rng, ["Low", "Medium", "High"], sev_weights)
        title, description = rng.choice(templates)
        station_name = rng.choice(list(STATIONS))
        station_id = station_ids[station_name]
        lat, lng, area = _place(rng, station_name)

        # more recent than old, but a full year is covered, and there are always a few from this week
        age_days = rng.randint(1, 6) if rng.random() < 0.07 else int(rng.triangular(1, 365, 40))
        filed = today - timedelta(days=age_days)
        incident = filed - timedelta(days=rng.randint(0, 4))
        citizen_id = rng.choice(citizens)
        citizen_user = one("SELECT user_id FROM citizen WHERE citizen_id = ?", citizen_id)["user_id"]

        verified_on = filed + timedelta(days=rng.randint(0, 3))
        roll = rng.random()
        if age_days <= 6 and roll < 0.6:
            status = "Filed"
        elif roll > 0.9:
            status = "Rejected"
        else:
            status = "Verified"
        if status != "Filed" and verified_on > today:
            verified_on = today

        reason = "Not enough detail to act on; the complainant was asked to add more." if status == "Rejected" else None
        complaint_id = run(
            "INSERT INTO complaint (citizen_id, title, description, location, incident_date, date_filed, status,"
            " reject_reason, category, severity, latitude, longitude) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            citizen_id, title, description, f"{area}, near {rng.choice([a for a in STATIONS[station_name][3] if a != area])}",
            incident.isoformat(), filed.isoformat(), status, reason, category, severity, lat, lng,
        )
        log.insert_one({"entity": "complaint", "entity_id": complaint_id, "old_status": None, "new_status": "Filed",
                        "user_id": citizen_user, "who": None, "changed_at": _when(filed, rng, "filed")})
        if status != "Filed":
            log.insert_one({"entity": "complaint", "entity_id": complaint_id, "old_status": "Filed", "new_status": status,
                            "user_id": None, "who": "Station staff", "changed_at": _when(verified_on, rng, "verified")})
        if status != "Verified":
            continue
        if age_days <= 8 and rng.random() < 0.5:
            continue  # verified and waiting for a case to be registered

        opened = min(verified_on + timedelta(days=rng.randint(0, 3)), today)
        officer_id = rng.choice(staff[station_id]) if rng.random() < 0.93 else None
        case_status, chargesheet_on, closed_on = _case_outcome(rng, opened, today)
        case_id = run(
            "INSERT INTO crime_case (complaint_id, officer_id, station_id, status, date_opened) VALUES (?, ?, ?, ?, ?)",
            complaint_id, officer_id, station_id, case_status, opened.isoformat(),
        )
        _case_history(rng, log, case_id, officer_id, opened, chargesheet_on, closed_on, case_status)

        people = rng.sample(criminals, rng.randint(1, 3))
        roles = ["accused" if case_status != "Under Investigation" else "suspect"] + ["suspect", "witness"][: len(people) - 1]
        for person, role in zip(people, roles):
            run("INSERT INTO case_criminal (case_id, criminal_id, role) VALUES (?, ?, ?)", case_id, person, role)
            if role in ("suspect", "accused"):
                chargeable.append((case_id, person))
        _case_documents(rng, case_id, people[0], opened, case_status, chargesheet_on, closed_on, section, today)
        run("INSERT INTO report (case_id, officer_id, content, date_generated) VALUES (?, ?, ?, ?)",
            case_id, officer_id, "Visited the location, spoke to those nearby and noted what was found.",
            (opened + timedelta(days=rng.randint(1, 6))).isoformat() if opened + timedelta(days=6) <= today else opened.isoformat())

    db.get_db().commit()
    return count


def _case_outcome(rng, opened, today):
    """Pick how far a case got, based on how long ago it opened."""
    age = (today - opened).days
    if age < 20:
        return "Under Investigation", None, None
    roll = rng.random()
    if age < 90 and roll < 0.6:
        return "Under Investigation", None, None
    if roll < 0.15 and age >= 45:
        return "Closed (Unresolved)", None, opened + timedelta(days=rng.randint(30, min(age, 120)))
    sheet = opened + timedelta(days=rng.randint(10, min(age, 40)))
    if sheet >= today or roll < 0.35:
        return "Chargesheet Filed", min(sheet, today), None
    closed = sheet + timedelta(days=rng.randint(10, 80))
    if closed > today:
        return "Chargesheet Filed", sheet, None
    return "Closed (Resolved)", sheet, closed


def _case_history(rng, log, case_id, officer_id, opened, chargesheet_on, closed_on, status):
    log.insert_one({"entity": "case", "entity_id": case_id, "old_status": None, "new_status": "Under Investigation",
                    "user_id": None, "who": "Station staff", "changed_at": _when(opened, rng, "opened")})
    if officer_id:
        log.insert_one({"entity": "case assignment", "entity_id": case_id, "old_status": None, "new_status": officer_id,
                        "user_id": None, "who": "Station staff", "changed_at": _when(opened, rng, "assigned")})
    if chargesheet_on:
        log.insert_one({"entity": "case", "entity_id": case_id, "old_status": "Under Investigation",
                        "new_status": "Chargesheet Filed", "user_id": None, "who": "Station staff",
                        "changed_at": _when(chargesheet_on, rng, "status")})
    if closed_on:
        before = "Chargesheet Filed" if chargesheet_on else "Under Investigation"
        log.insert_one({"entity": "case", "entity_id": case_id, "old_status": before, "new_status": status,
                        "user_id": None, "who": "Station staff", "changed_at": _when(closed_on, rng, "closed")})


def _case_documents(rng, case_id, lead_person, opened, status, chargesheet_on, closed_on, section, today):
    """Evidence, statements, and the later-stage records that go with how far the case has got."""
    mongo = mdb()
    for no, (kind, text) in enumerate(rng.sample(EVIDENCE, rng.randint(0, 3)), start=1):
        collected = opened + timedelta(days=rng.randint(0, 5))
        collected = min(collected, today)
        chain = [{"at": _when(collected, rng, "evidence"), "action": "collected", "by": "Investigating officer", "where": "", "note": ""}]
        for action in rng.sample(["stored", "sent for analysis", "returned from analysis"], rng.randint(0, 3)):
            chain.append({"at": _when(min(collected + timedelta(days=len(chain)), today), rng, "custody"), "action": action,
                          "by": "Investigating officer", "where": rng.choice(CUSTODY_PLACES), "note": ""})
        mongo.evidence.insert_one({
            "case_id": case_id, "evidence_no": no, "type": kind, "description": text,
            "date_collected": collected.isoformat(), "created_at": chain[0]["at"], "custody": chain,
        })
    for no in range(1, rng.randint(0, 2) + 1):
        day = min(opened + timedelta(days=rng.randint(1, 8)), today)
        kind = rng.choice(["witness", "victim"])
        mongo.statements.insert_one({
            "case_id": case_id, "no": no, "kind": kind, "person": f"{rng.choice(FIRST)} {rng.choice(LAST)}",
            "body": rng.choice(WITNESS_STATEMENTS if kind == "witness" else VICTIM_STATEMENTS), "recorded_by": "Investigating officer", "recorded_at": _when(day, rng, "statement"),
        })
    if chargesheet_on:
        person = one("SELECT name FROM criminal WHERE criminal_id = ?", lead_person)["name"]
        arrested = max(opened, chargesheet_on - timedelta(days=rng.randint(3, 12)))
        mongo.arrests.insert_one({
            "case_id": case_id, "no": 1, "criminal_id": lead_person, "person": person, "arrested_on": arrested.isoformat(),
            "place": "Near the incident location", "charges": section, "recorded_by": "Investigating officer",
            "recorded_at": _when(arrested, rng, "arrest"),
        })
        mongo.chargesheets.insert_one({
            "case_id": case_id, "filed_on": chargesheet_on.isoformat(), "sections": section,
            "summary": "The investigation found enough to proceed against the accused on the evidence collected.",
            "filed_by": "Investigating officer", "created_at": _when(chargesheet_on, rng, "sheet"),
        })
        hearing = chargesheet_on + timedelta(days=rng.randint(7, 30))
        outcome = "Adjourned" if hearing < today and status != "Closed (Resolved)" else ("Judgment delivered" if status == "Closed (Resolved)" else "")
        if hearing >= today:
            outcome = ""
        mongo.court_dates.insert_one({
            "case_id": case_id, "no": 1, "date": hearing.isoformat(), "court": rng.choice(COURTS),
            "purpose": rng.choice(PURPOSES), "outcome": outcome, "set_by": "Investigating officer",
            "created_at": _when(chargesheet_on, rng, "court"),
        })
