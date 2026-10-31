-- accounts: one row per login, specialised into citizen / officer / admin by role
CREATE TABLE IF NOT EXISTS users (
    user_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    name     TEXT NOT NULL,
    email    TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    role     TEXT NOT NULL CHECK (role IN ('citizen', 'officer', 'admin')),
    active   INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS police_station (
    station_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL UNIQUE,
    jurisdiction TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS citizen (
    citizen_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL UNIQUE REFERENCES users(user_id) ON DELETE CASCADE,
    address    TEXT,
    phone      TEXT
);

CREATE TABLE IF NOT EXISTS officer (
    officer_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL UNIQUE REFERENCES users(user_id) ON DELETE CASCADE,
    badge_no   TEXT NOT NULL UNIQUE,
    officer_rank TEXT NOT NULL,
    station_id INTEGER NOT NULL REFERENCES police_station(station_id)
);

CREATE TABLE IF NOT EXISTS admin (
    admin_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id  INTEGER NOT NULL UNIQUE REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS complaint (
    complaint_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    citizen_id    INTEGER NOT NULL REFERENCES citizen(citizen_id) ON DELETE CASCADE,
    title         TEXT NOT NULL,
    description   TEXT NOT NULL,
    location      TEXT NOT NULL,
    incident_date TEXT NOT NULL,
    date_filed    TEXT NOT NULL DEFAULT (date('now')),
    status        TEXT NOT NULL DEFAULT 'Filed'
                  CHECK (status IN ('Filed', 'Verified', 'Rejected')),
    reject_reason TEXT
);

-- at most one case per complaint, enforced by the UNIQUE on complaint_id
CREATE TABLE IF NOT EXISTS crime_case (
    case_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    complaint_id INTEGER NOT NULL UNIQUE REFERENCES complaint(complaint_id),
    officer_id   INTEGER REFERENCES officer(officer_id) ON DELETE SET NULL,
    station_id   INTEGER NOT NULL REFERENCES police_station(station_id),
    status       TEXT NOT NULL DEFAULT 'Under Investigation'
                 CHECK (status IN ('Under Investigation', 'Chargesheet Filed',
                                   'Closed (Resolved)', 'Closed (Unresolved)')),
    date_opened  TEXT NOT NULL DEFAULT (date('now'))
);

CREATE TABLE IF NOT EXISTS criminal (
    criminal_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    age           INTEGER CHECK (age BETWEEN 0 AND 120),
    crime_history TEXT,
    wanted        INTEGER NOT NULL DEFAULT 0
);

-- junction table for Case INVOLVES Criminal (many to many)
CREATE TABLE IF NOT EXISTS case_criminal (
    case_id     INTEGER NOT NULL REFERENCES crime_case(case_id) ON DELETE CASCADE,
    criminal_id INTEGER NOT NULL REFERENCES criminal(criminal_id) ON DELETE CASCADE,
    role        TEXT NOT NULL DEFAULT 'suspect',
    PRIMARY KEY (case_id, criminal_id)
);

CREATE TABLE IF NOT EXISTS report (
    report_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id        INTEGER NOT NULL REFERENCES crime_case(case_id) ON DELETE CASCADE,
    officer_id     INTEGER REFERENCES officer(officer_id) ON DELETE SET NULL,
    content        TEXT NOT NULL,
    date_generated TEXT NOT NULL DEFAULT (date('now'))
);

CREATE INDEX IF NOT EXISTS idx_complaint_citizen ON complaint(citizen_id);
CREATE INDEX IF NOT EXISTS idx_complaint_status  ON complaint(status);
CREATE INDEX IF NOT EXISTS idx_case_status       ON crime_case(status);
CREATE INDEX IF NOT EXISTS idx_case_officer      ON crime_case(officer_id);
CREATE INDEX IF NOT EXISTS idx_criminal_name     ON criminal(name);

CREATE VIEW IF NOT EXISTS v_cases_by_status AS
    SELECT status, COUNT(*) AS total FROM crime_case GROUP BY status;

CREATE VIEW IF NOT EXISTS v_cases_by_station AS
    SELECT ps.name AS station, COUNT(c.case_id) AS total
    FROM police_station ps LEFT JOIN crime_case c ON c.station_id = ps.station_id
    GROUP BY ps.station_id, ps.name;
