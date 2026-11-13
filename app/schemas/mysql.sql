-- accounts: one row per login, specialised into citizen / officer / admin by role
CREATE TABLE users (
    user_id  INT AUTO_INCREMENT PRIMARY KEY,
    name     VARCHAR(200) NOT NULL,
    email    VARCHAR(200) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    role     VARCHAR(255) NOT NULL CHECK (role IN ('citizen', 'officer', 'admin')),
    active   INT NOT NULL DEFAULT 1,
    email_alerts INT NOT NULL DEFAULT 1
);

CREATE TABLE police_station (
    station_id   INT AUTO_INCREMENT PRIMARY KEY,
    name         VARCHAR(200) NOT NULL UNIQUE,
    jurisdiction VARCHAR(255) NOT NULL,
    phone        VARCHAR(40),
    latitude     DOUBLE PRECISION,
    longitude    DOUBLE PRECISION
);

CREATE TABLE citizen (
    citizen_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id    INT NOT NULL UNIQUE REFERENCES users(user_id) ON DELETE CASCADE,
    address    TEXT,
    phone      TEXT
);

CREATE TABLE officer (
    officer_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id    INT NOT NULL UNIQUE REFERENCES users(user_id) ON DELETE CASCADE,
    badge_no   VARCHAR(200) NOT NULL UNIQUE,
    officer_rank VARCHAR(255) NOT NULL,
    station_id INT NOT NULL REFERENCES police_station(station_id)
);

CREATE TABLE admin (
    admin_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id  INT NOT NULL UNIQUE REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE TABLE complaint (
    complaint_id  INT AUTO_INCREMENT PRIMARY KEY,
    citizen_id    INT NOT NULL REFERENCES citizen(citizen_id) ON DELETE CASCADE,
    title         VARCHAR(255) NOT NULL,
    description   TEXT NOT NULL,
    location      VARCHAR(255) NOT NULL,
    incident_date VARCHAR(255) NOT NULL,
    date_filed    VARCHAR(255) NOT NULL DEFAULT (DATE_FORMAT(CURDATE(), '%Y-%m-%d')),
    status        VARCHAR(255) NOT NULL DEFAULT 'Filed'
                  CHECK (status IN ('Filed', 'Verified', 'Rejected')),
    reject_reason TEXT,
    category      VARCHAR(60) NOT NULL DEFAULT 'Other',
    severity      VARCHAR(20) NOT NULL DEFAULT 'Medium',
    latitude      DOUBLE PRECISION,
    longitude     DOUBLE PRECISION
);

-- at most one case per complaint, enforced by the UNIQUE on complaint_id
CREATE TABLE crime_case (
    case_id      INT AUTO_INCREMENT PRIMARY KEY,
    complaint_id INT NOT NULL UNIQUE REFERENCES complaint(complaint_id),
    officer_id   INT REFERENCES officer(officer_id) ON DELETE SET NULL,
    station_id   INT NOT NULL REFERENCES police_station(station_id),
    status       VARCHAR(255) NOT NULL DEFAULT 'Under Investigation'
                 CHECK (status IN ('Under Investigation', 'Chargesheet Filed',
                                   'Closed (Resolved)', 'Closed (Unresolved)')),
    date_opened  VARCHAR(255) NOT NULL DEFAULT (DATE_FORMAT(CURDATE(), '%Y-%m-%d'))
);

CREATE TABLE criminal (
    criminal_id   INT AUTO_INCREMENT PRIMARY KEY,
    name          VARCHAR(200) NOT NULL,
    age           INT CHECK (age BETWEEN 0 AND 120),
    crime_history TEXT,
    wanted        INT NOT NULL DEFAULT 0
);

-- junction table for Case INVOLVES Criminal (many to many)
CREATE TABLE case_criminal (
    case_id     INT NOT NULL REFERENCES crime_case(case_id) ON DELETE CASCADE,
    criminal_id INT NOT NULL REFERENCES criminal(criminal_id) ON DELETE CASCADE,
    role        VARCHAR(255) NOT NULL DEFAULT 'suspect',
    PRIMARY KEY (case_id, criminal_id)
);

CREATE TABLE report (
    report_id      INT AUTO_INCREMENT PRIMARY KEY,
    case_id        INT NOT NULL REFERENCES crime_case(case_id) ON DELETE CASCADE,
    officer_id     INT REFERENCES officer(officer_id) ON DELETE SET NULL,
    content        TEXT NOT NULL,
    date_generated VARCHAR(255) NOT NULL DEFAULT (DATE_FORMAT(CURDATE(), '%Y-%m-%d'))
);

CREATE INDEX idx_complaint_citizen ON complaint(citizen_id);
CREATE INDEX idx_complaint_status  ON complaint(status);
CREATE INDEX idx_case_status       ON crime_case(status);
CREATE INDEX idx_case_officer      ON crime_case(officer_id);
CREATE INDEX idx_criminal_name     ON criminal(name);

CREATE OR REPLACE VIEW v_cases_by_status AS
    SELECT status, COUNT(*) AS total FROM crime_case GROUP BY status;

CREATE OR REPLACE VIEW v_cases_by_station AS
    SELECT ps.name AS station, COUNT(c.case_id) AS total
    FROM police_station ps LEFT JOIN crime_case c ON c.station_id = ps.station_id
    GROUP BY ps.station_id, ps.name;
