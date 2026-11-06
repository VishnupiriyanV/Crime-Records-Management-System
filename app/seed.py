"""Load demo data (python -m app.seed), a year of sample records on top (--bulk 300), or only a first admin (--admin EMAIL)."""
import argparse
import os
import sys

from . import db
from .auth import hash_password
from .db import one, run
from .main_config import database_url

DEMO_PASSWORD = "password123"


def seed_demo():
    path = database_url()
    db.init_db(path)
    token = db.use(db.connect(path))
    try:
        if one("SELECT 1 FROM users LIMIT 1"):
            print("The database already has users; nothing seeded.")
            return
        for name, area in (
            ("Central Station", "City centre and old town"),
            ("Riverside Station", "Riverside and the eastern wards"),
            ("North Hills Station", "North Hills and the airport road"),
        ):
            run("INSERT INTO police_station (name, jurisdiction) VALUES (?, ?)", name, area)

        def add_user(name, email, role):
            return run(
                "INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)",
                name, email, hash_password(DEMO_PASSWORD), role,
            )

        run("INSERT INTO admin (user_id) VALUES (?)", add_user("Station Admin", "admin@crms.test", "admin"))
        run(
            "INSERT INTO officer (user_id, badge_no, officer_rank, station_id) VALUES (?, ?, ?, ?)",
            add_user("Officer Rao", "officer@crms.test", "officer"), "B-1001", "Inspector", 1,
        )
        run(
            "INSERT INTO citizen (user_id, address) VALUES (?, ?)",
            add_user("Asha Nair", "citizen@crms.test", "citizen"), "12 Lake Road",
        )
        for name, age, history, wanted in (
            ("Ravi Menon", 34, "Two earlier burglary convictions.", 1),
            ("Dev Kapoor", 28, "Charged once with vehicle theft.", 0),
            ("Karan Shah", 41, "Fraud case closed in 2022.", 1),
        ):
            run(
                "INSERT INTO criminal (name, age, crime_history, wanted) VALUES (?, ?, ?, ?)",
                name, age, history, wanted,
            )
        db.get_db().commit()
        print(f"Seeded. Sign in with admin@crms.test, officer@crms.test or citizen@crms.test ({DEMO_PASSWORD}).")
    finally:
        db.release(token)


def seed_admin(email):
    password = os.environ.get("CRMS_ADMIN_PASSWORD", "")
    if len(password) < 12:
        sys.exit("Set CRMS_ADMIN_PASSWORD to at least 12 characters.")
    path = database_url()
    db.init_db(path)
    token = db.use(db.connect(path))
    try:
        if one("SELECT 1 FROM users LIMIT 1"):
            sys.exit("The database already has users; nothing created.")
        user_id = run(
            "INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, 'admin')",
            "Administrator", email.strip().lower(), hash_password(password),
        )
        run("INSERT INTO admin (user_id) VALUES (?)", user_id)
        db.get_db().commit()
        print(f"Admin {email} created. Add police stations from the Users page after signing in.")
    finally:
        db.release(token)


def seed_bulk(count):
    from . import demo_data, mongo
    from .main_config import mongo_name, mongo_url

    path = database_url()
    db.init_db(path)
    mongo.configure(mongo_url(), mongo_name())
    token = db.use(db.connect(path))
    try:
        if not one("SELECT 1 FROM users LIMIT 1"):
            db.release(token)
            seed_demo()
            token = db.use(db.connect(path))
        if one("SELECT COUNT(*) AS n FROM complaint")["n"] > 20:
            sys.exit("This database already has plenty of complaints; sample records not added.")
        if one("SELECT COUNT(*) AS n FROM complaint")["n"] == 0:
            # a load that died half way leaves case-file records with no complaint; they would clash with the new ones
            for name in ("evidence", "statements", "arrests", "court_dates", "chargesheets",
                         "status_log", "notes", "notifications", "attachments", "attachment_files"):
                mongo.mdb()[name].delete_many({})
        made = demo_data.generate(count)
        print(f"Added {made} sample complaints with their cases, evidence and records.")
    finally:
        db.release(token)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bulk", type=int, metavar="N", help="also add N sample complaints over the last year")
    parser.add_argument("--admin", metavar="EMAIL", help="create only this admin; the password comes from CRMS_ADMIN_PASSWORD")
    args = parser.parse_args()
    if args.admin:
        seed_admin(args.admin)
    elif args.bulk:
        seed_bulk(args.bulk)
    else:
        seed_demo()
