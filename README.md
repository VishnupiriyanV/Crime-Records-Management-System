<div align="center">

# Crime Records Management System

**File a complaint, follow it through an investigation, and keep a case history that cannot be quietly rewritten.**

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-API-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![MongoDB](https://img.shields.io/badge/MongoDB-documents-47A248?logo=mongodb&logoColor=white)](https://www.mongodb.com/)
[![SQL](https://img.shields.io/badge/SQL-SQLite%20%7C%20PostgreSQL%20%7C%20MySQL-336791)](#choosing-the-relational-database)
[![Tests](https://img.shields.io/badge/tests-77%20API%20%2B%2012%20browser-brightgreen)](#testing)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[Features](#features) ·
[Quick start](#quick-start) ·
[Configuration](#configuration) ·
[Guides](#guides) ·
[Deployment](#deployment) ·
[Testing](#testing)

<br>

<img src="screenshots/dashboard.png" alt="Dashboard" width="49%"> <img src="screenshots/case.png" alt="A case file" width="49%">

</div>

<br>

CRMS is a web application for a police station. Citizens file and track complaints. Officers verify them, open cases, and record evidence, statements, arrests and court dates. Admins manage accounts and stations and see how the station is doing. It was built for a DBMS lab, so the database design is a first-class part of it: a relational core with keys and constraints, and a document store for the records that grow around a case.

## Table of contents

- [Features](#features)
- [How it fits together](#how-it-fits-together)
- [Quick start](#quick-start)
- [Configuration](#configuration)
- [Guides](#guides)
- [Deployment](#deployment)
- [Testing](#testing)
- [Project structure](#project-structure)
- [Known limitations](#known-limitations)
- [License](#license)

## Features

**For citizens**
- File a complaint with a map pin and up to five attached files, in English, Tamil or Hindi.
- Get a warning before filing a complaint that looks like one already made.
- Follow the complaint through four stages and get a notification (and, if the station has set up e-mail, an e-mail) at each step, with a reason when it is rejected.
- Correct a complaint, or withdraw it, until the station has reviewed it. What it said before stays in the record.

**For officers**
- A review queue, a list of open cases and a **Needs attention** panel for work that has waited too long.
- **Take this case** on any case nobody has yet, and saved views to reopen a filtered list (for example "open cases idle for two weeks") in one click.
- A full case file: evidence with chain of custody, statements, arrests, chargesheet, court dates and outcomes, linked people and reports.
- A register of criminal records with a wanted flag, one search box over everything, and a map of the busiest areas.
- A PDF of the case file with a verification seal, and CSV exports of every list.

**For admins**
- Accounts, roles and stations, an audit log, charts and reports, and a temporary password for anyone who cannot use the e-mail reset link.
- API tokens, a JSON export and signed webhooks for connecting other systems.

**Across the app**
- A tamper-evident ledger: every case event is sealed into a hash chain that can be verified at any time, and every uploaded file is fingerprinted (SHA-256) so a swapped file is caught too.
- Password reset by e-mail link, and e-mail alerts that each person can turn off on their profile.
- English, Tamil and Hindi; light and dark mode; keyboard shortcuts (press `?`); a layout that works on a phone.
- FIR numbers, crime categories, sortable lists, in-page preview of uploaded files, and backups of both databases.

## How it fits together

| Layer | Technology | Holds |
| --- | --- | --- |
| Frontend | React (Vite), in `frontend/` | The citizen, officer and admin screens |
| API | FastAPI, a JSON API under `/api` | Sign-in, role checks and the status rules |
| Relational database | SQLite (default), PostgreSQL or MySQL, chosen by one setting | Users, complaints, cases, criminals, reports |
| Document database | MongoDB | Evidence, statements, arrests, notes, notifications, uploaded files, the status trail and the ledger |

Rows and documents are linked by id. The relational side keeps what needs joins and constraints (one case per complaint, only allowed statuses); MongoDB keeps what varies in shape and grows over time.

## Quick start

You need Python 3.11+, Node 20+ and Docker (for MongoDB).

```bash
docker compose up -d mongo                    # MongoDB on localhost:27017

python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m app.seed                  # demo stations, accounts and records

cd frontend && npm install && npm run build && cd ..
.venv/bin/uvicorn run:app                     # http://localhost:8000
```

The seed creates three demo accounts that share the password `password123`. Change or delete them before using the app for anything real.

| Role | Email |
| --- | --- |
| Admin | `admin@crms.test` |
| Officer | `officer@crms.test` |
| Citizen | `citizen@crms.test` |

For a fuller demo, add a year of made-up records on top (it needs MongoDB running):

```bash
.venv/bin/python -m app.seed --bulk 300
```

That adds 300 complaints with their cases, evidence, statements, arrests, chargesheets and court dates, five stations with map coordinates, and a few officers each. It only runs on a database with fewer than 20 complaints.

For frontend work, run `npm run dev` in `frontend/` (port 5173, it proxies `/api` to port 8000) next to uvicorn. The map page and the location picker load their tiles from OpenStreetMap, so they need an internet connection; everything else works offline.

### Choosing the relational database

SQLite needs nothing. For PostgreSQL or MySQL, start the matching container and point `CRMS_DB_URL` at it before seeding and running:

```bash
docker compose up -d postgres mysql
export CRMS_DB_URL=postgresql://crms:crms@localhost:5432/crms     # or
export CRMS_DB_URL=mysql://crms:crms@localhost:3306/crms
```

The tables are created on first start from `app/schemas/<database>.sql`. A database made by an older version gets any new columns added on the next start. The passwords in `docker-compose.yml` are for local development only.

## Configuration

All settings are environment variables and all are optional on a development machine.

| Variable | Purpose | Default |
| --- | --- | --- |
| `CRMS_DB_URL` | Relational database: `sqlite:///file.db`, `postgresql://…` or `mysql://…` | SQLite file in `data/` |
| `MONGO_URL` | MongoDB address; `mongodb+srv://` works | `mongodb://localhost:27017` |
| `MONGO_DB` | MongoDB database name | `crms` |
| `CRMS_SECRET` | Signs sessions and seals the ledger. Keep it the same across restarts | Generated into `data/secret.key` |
| `CRMS_ENV` | `production` makes `CRMS_SECRET` mandatory and the session cookie HTTPS-only | development |
| `CRMS_ADMIN_EMAIL`, `CRMS_ADMIN_PASSWORD` | Create the first admin on start-up (password of 12 or more characters) | unset |
| `CRMS_SAMPLE_DATA` | Load the demo accounts and this many sample complaints on start-up | unset |
| `SMTP_HOST`, `SMTP_PORT` | Mail server for password resets and alerts. Nothing is sent without `SMTP_HOST` | unset, `587` |
| `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | Mail login and the sender address | unset |
| `SMTP_STARTTLS` | Set to `0` to turn off STARTTLS (port 465 uses SSL automatically) | on |
| `CRMS_BASE_URL` | The public address of the site, for links in e-mails, for example `https://crms.example`. Required in production for reset links | unset |
| `CRMS_EMAIL_ALERTS` | Set to `0` to send only password resets, never alerts | on |

## Guides

<details>
<summary><b>Tamil and Hindi</b></summary>

<br>

The language menu in the top bar switches every screen to Tamil or Hindi and remembers the choice. That covers the citizen screens and the staff screens (dashboard, cases and the case file, criminals, reports, users, audit, integrations, search, map, stations), along with statuses, severities, crime types and custody actions. These stay in English: the case timeline and audit entries the server writes, error messages from the server, anything people typed (titles, descriptions, names, evidence notes), and the browser's own file and date controls.

The words live in `frontend/src/lang/ta.js` and `hi.js`, with the English text as the key. A string with no entry shows in English, so a missing translation never breaks a page. To translate another screen, wrap its text in `t('...')` from `useT()` and add the entry to both files. The translations were written without a native speaker checking them, so have someone who reads Tamil and Hindi review the wording before real use, especially legal terms such as the chargesheet and the case statuses.


</details>

<details>
<summary><b>Overdue flags and duplicate detection</b></summary>

<br>

Staff see red flags where work has waited too long, and the dashboard has a **Needs attention** panel with the counts. The limits are in `app/overdue.py`: a complaint unreviewed for 2 days, an open case with no officer for 3 days, an open case with no activity for 14 days (evidence, statements, arrests, court dates, files, status changes and reports all count as activity), and a court date that has passed with no outcome. High severity waits half as long. Officers see their own cases; admins see everything.

When a citizen files a complaint, the form first checks their own earlier complaints for one that looks the same (similar wording, place and date) and asks before filing. Staff see **Possible duplicates** on a complaint page, with a button to reject one as a duplicate. The matching is plain word, distance and date comparison in `app/similar.py`, so it will miss a duplicate described in very different words. Citizens never see anyone else's complaints.

</details>

<details>
<summary><b>Case ledger and the PDF case file</b></summary>

<br>

Every event on a case is sealed into a ledger: status changes, assignments, evidence and each custody step, files, statements, arrests, the chargesheet, court dates and outcomes, reports and citizen notes. Each entry holds a keyed hash (HMAC-SHA256) of the entry before it, so editing, removing or reordering one breaks every hash after it, and someone who can write to the database but does not know `CRMS_SECRET` cannot repair the chain. The head of the chain is also kept separately, which exposes entries cut off the end.

The case page shows each event with its time, who did it, the detail, and its seal (`#7 3f9a1c2b`), and **Verify integrity** checks everything again: the chain, that no sealed record was edited or deleted, and that no record exists that was never sealed. Looking at a case never seals anything new, so a forged record cannot be blessed by a page view. A case that existed before this feature is sealed once, the first time it is opened, and marked imported; tampering before that moment cannot be detected.

Every uploaded file (on a complaint or on evidence) is fingerprinted with SHA-256 when it is stored. The fingerprint shows beside the file and on the timeline, and **Verify integrity** recomputes it, so a file whose bytes were swapped in the database is reported even though its record looks untouched. Files uploaded before this feature have no fingerprint and are not checked.

Keep `CRMS_SECRET` the same across restarts and restores: a different secret makes every old entry fail verification. A backup includes the ledger.

`GET /api/export/cases/{id}.pdf` is a printable case file with a letterhead, the case summary, tables for people, evidence with its custody chain, arrests and court dates, the ledger with each entry's seal, a verification box with the chain head, and signature lines. Text in Tamil or Hindi cannot be printed with the built-in PDF fonts and shows as `?`; the PDF says so when that happens.

</details>

<details>
<summary><b>Passwords and e-mail</b></summary>

<br>

**Forgot password.** The sign-in page links to a reset form. It always answers the same way, whether or not the address has an account, and sends a one-hour link (three an hour per account at most; a link that could not be sent does not count). Only a hash of the link's token is stored, and it can be used once. The link always points at `CRMS_BASE_URL`, never at the address the request came from; on a development machine without it, the request's own address is used.

**No mail server?** Set `SMTP_HOST` to turn e-mail on. Without it, nothing is sent: on a development machine the message (with the reset link) is written to the server log, and in production it is not logged at all. An admin can open **Users**, choose **Reset password**, and read the temporary password to the person; it is shown once and the person should change it on their profile page.

**Alerts by e-mail.** When a mail server is set up, the notices people see in the app (complaint verified or rejected, case opened or moved, court date set, case assigned) are also e-mailed. Each person can turn that off under **Profile**; the in-app notices stay. E-mail is plain text and is sent in the background, so a mail problem never slows down or breaks the change that caused it. There is no retry queue: a message that the mail server refuses is logged and dropped.

</details>

<details>
<summary><b>Editing, withdrawing and taking cases</b></summary>

<br>

A citizen can edit a complaint (title, description, place, date, category, map pin) or withdraw it while its status is still **Filed**. Each edit keeps the earlier wording: it appears on the timeline once a case exists, and in the audit log. A withdrawn complaint is stored as rejected with the reason "Withdrawn by the citizen." and shown as **Withdrawn**.

Only the assigned officer or an admin can change a case. An officer can open any case that has no officer and press **Take this case**; if two officers press it at once, one of them is told it was just taken. Moving a case from one officer to another is still an admin's job.

**Saved views** keep a filter of the Cases or Complaints list under a name, per person (20 per list). They sit under the filter row.

</details>
<details>
<summary><b>Connecting other systems: tokens, JSON export and webhooks</b></summary>

<br>

Admins open **Integrations** to make API tokens and webhooks.

- **Tokens.** Send `Authorization: Bearer crms_...` with each call. A token acts as the admin who made it. A read token can only fetch, and no token can manage users, tokens or webhooks. Only a hash is stored, so the token is shown once. Revoke it from the same page.
- **JSON export.** `GET /api/export/fir/{id}` returns one complaint with its case, people, chargesheet and court dates. `GET /api/export/firs?since=2026-01-01&page=1` returns them 25 at a time. The layout is ours, named `crms.fir/1` in each record; it is not the national CCTNS format.
- **Webhooks.** CRMS posts JSON to your address when a complaint is filed or changes status, a case is opened or changes status, or a case is assigned. Each call carries `X-CRMS-Event` and `X-CRMS-Signature` (`sha256=` and the HMAC-SHA256 of the raw body, keyed with the secret shown when you added it). It tries three times and the page shows the last result. Only ids, FIR number, status and category go out. When the site is live the address must be `https://` and reachable from the internet.

</details>

<details>
<summary><b>Backups</b></summary>

<br>

```bash
.venv/bin/python -m app.backup create --out backups --keep 14
.venv/bin/python -m app.backup restore backups/crms-20261105-120000.tar.gz
```

An archive holds every SQL table and every MongoDB collection (which includes the uploaded files), so it also moves data between SQLite, PostgreSQL and MySQL. Restore only loads into an empty database. To run it daily, add a cron line such as `0 2 * * * cd /path/to/app && .venv/bin/python -m app.backup create`. Keep the archives somewhere other than the machine that runs the app: they contain personal data.

</details>

## Deployment

Set these on the host:

| Setting | Value |
| --- | --- |
| `CRMS_ENV` | `production`. The app then refuses to start without `CRMS_SECRET`, and the session cookie is sent only over HTTPS. |
| `CRMS_SECRET` | A long random string, for example `python3 -c "import secrets; print(secrets.token_hex(32))"` |
| `CRMS_DB_URL` | A PostgreSQL or MySQL address. SQLite works only where the disk is kept between restarts. |
| `MONGO_URL` | A MongoDB address; `mongodb+srv://` addresses work |

The `Dockerfile` builds the React app and the API into one image that listens on `$PORT`. Serve it over HTTPS. Create the first admin without the demo accounts:

```bash
CRMS_ADMIN_PASSWORD='a-long-password' python -m app.seed --admin you@example.com
```

Then sign in, and add police stations on the Users page before creating officers.

### Hosting for free

The app needs a place to run, a relational database and MongoDB. A combination that costs nothing and needs no shell access:

1. **MongoDB:** create a free cluster on MongoDB Atlas (M0). Add a database user, allow access from anywhere under Network Access, and copy the `mongodb+srv://` address.
2. **PostgreSQL:** create a free project on Neon and copy the connection string. Keep the `?sslmode=require` at the end.
3. **The app:** push this repository to GitHub, then on Render choose New, Blueprint, and pick the repository. `render.yaml` sets up a free Docker web service. Render asks for these values:

| Setting | Value |
| --- | --- |
| `CRMS_DB_URL` | The Neon connection string |
| `MONGO_URL` | The Atlas address |
| `CRMS_ADMIN_EMAIL`, `CRMS_ADMIN_PASSWORD` | The first admin (password of 12 or more characters) |
| `CRMS_BASE_URL`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | Optional. Needed for password-reset e-mails and alerts. `CRMS_BASE_URL` is the site's own address, for example `https://crms.onrender.com` |

`CRMS_SECRET` is generated for you. On the first start the app creates the tables and the admin. Sign in, then add police stations on the Users page.

For a demo, set `CRMS_SAMPLE_DATA=300` before the first start instead of the admin values. That loads the demo accounts (`admin@crms.test` and the others, password `password123`) and 300 sample complaints. Change those passwords before sharing the link widely.

Free web services sleep after about 15 minutes idle and take about a minute to wake, so open the site before presenting. Their disks are wiped on restart, which is why files and records live in the databases. Free tiers change, so check each provider's current terms. Koyeb and Hugging Face Spaces also build from the `Dockerfile` if you prefer them.

## Testing

```bash
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest
```

The tests use an in-memory stand-in for MongoDB and a temporary SQLite file, so they need no running server. To run them against a real database instead:

```bash
CRMS_TEST_DB_URL=postgresql://crms:crms@localhost:5432/crms .venv/bin/python -m pytest
CRMS_TEST_DB_URL=mysql://crms:crms@localhost:3306/crms .venv/bin/python -m pytest
```

That wipes every table in the database it points at, so use the development containers.

There are also browser tests that click through the app in Chromium. Build the frontend first and install Playwright (`pip install playwright`); they use the system Chromium if there is one.

```bash
.venv/bin/python -m pytest tests/e2e
```

## Project structure

```
app/
  routes/        one router per area: account, complaints, cases, criminals, admin, exports ...
  lifecycle.py   the status rules for complaints and cases
  ledger.py      the hash-chained case ledger
  db.py          one query interface over SQLite, PostgreSQL and MySQL
  mongo.py       MongoDB collections and helpers
  schemas/       the table definitions for each database
  backup.py      backup and restore
frontend/src/    the React app (pages, language files, styles)
tests/           API tests; tests/e2e holds the browser tests
```

## Known limitations

- Sign-in is locked for 15 minutes after five wrong passwords for one email from one address. The count is kept in MongoDB, and the address is the one the server sees, so behind a proxy it needs the proxy's forwarded address configured.
- The relational database and MongoDB are written separately, so a failure between the two writes can leave them out of step. There is no cross-database transaction.
- Reset links and alerts need a mail server that you provide; with none, only the in-app notices work.
- Uploads are stored in MongoDB and are limited to images, PDFs and text files of 5 MB or less, five per complaint.
- Database connections are reused in a small pool per process; a very busy deployment would need a larger one.
- This is a lab project and has not had a security audit. Do not use it for real police records as it stands.

## License

Released under the [MIT License](LICENSE).
