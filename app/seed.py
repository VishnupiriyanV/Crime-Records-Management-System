"""Load demo stations, accounts and criminal records: python -m app.seed"""
from . import db
from .auth import hash_password
from .db import one, run
from .main_config import database_url

DEMO_PASSWORD = "password123"


def seed():
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


if __name__ == "__main__":
    seed()
