# Crime Records Management System

A web app for a DBMS lab. Citizens file and track complaints; police officers and admins verify them, open cases, and manage criminal records, evidence and reports.

- **Backend:** FastAPI, a JSON API under `/api`.
- **Frontend:** React (Vite), in `frontend/`.
- **Relational database:** SQLite (default), PostgreSQL or MySQL, chosen by one setting. It holds users, complaints, cases, criminals and reports.
- **MongoDB:** holds the document-shaped data: evidence, citizen notes, notifications, uploaded files and the status audit trail. Rows and documents are linked by id.

Beyond the core flow it has charts on the dashboard and reports, a timeline on every case, one search box across complaints, cases and records, CSV exports of the lists and a PDF of each case file, in-page preview of uploaded images, PDFs and text, an admin audit log, live alerts, sortable lists, keyboard shortcuts (press `?`), a dark mode, FIR numbers and crime categories, a map with busiest areas, a full case file (statements, arrests, chargesheet, court dates, evidence chain of custody), station and officer pages, and voice input.

## Run it

You need Python 3.11+, Node 20+ and Docker (for MongoDB).

```
docker compose up -d mongo                    # MongoDB on localhost:27017

python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m app.seed                  # demo stations, accounts and records

cd frontend && npm install && npm run build && cd ..
.venv/bin/uvicorn run:app                     # http://localhost:8000
```

For frontend work, run `npm run dev` in `frontend/` (port 5173, it proxies `/api` to port 8000) next to uvicorn.

The seed creates three demo accounts (`admin@crms.test`, `officer@crms.test`, `citizen@crms.test`) that share the password `password123`. Change or delete them before using the app for anything real.

For a fuller demo, add a year of made-up records on top of the demo accounts (it needs MongoDB running):

```
.venv/bin/python -m app.seed --bulk 300
```

That adds 300 complaints over the last year with their cases, evidence, statements, arrests, chargesheets and court dates, five stations with map coordinates, and a few officers each. It only runs on a database with fewer than 20 complaints.

The map page and the location picker load their background tiles from OpenStreetMap, so they need an internet connection. Everything else works offline.

### Choosing the relational database

SQLite needs nothing. For PostgreSQL or MySQL, start the matching container and point `CRMS_DB_URL` at it before seeding and running:

```
docker compose up -d postgres mysql
export CRMS_DB_URL=postgresql://crms:crms@localhost:5432/crms     # or
export CRMS_DB_URL=mysql://crms:crms@localhost:3306/crms
```

The tables are created on first start from `app/schemas/<database>.sql`. A database made by an older version gets any new columns added automatically on the next start. The passwords in `docker-compose.yml` are for local development only.

Other settings, all optional on a development machine: `MONGO_URL` (default `mongodb://localhost:27017`), `MONGO_DB` (default `crms`), `CRMS_SECRET` (session signing key).

## Voice input

On the complaint form, **Speak your complaint** takes a spoken account and fills the title, description, place, date and category. It only fills boxes that are still empty, and only sets a date when one was spoken ("yesterday", "3 days ago", "5 November"). Officers get a **Dictate** button next to the evidence, statement, report and chargesheet text boxes.

It uses the browser's own speech recognition, so it works in Chrome, Edge and Safari and the buttons are hidden elsewhere (Firefox). Chrome and Edge send the audio to the browser maker's speech service, which matters for sensitive reports; say so to the people using it. The page must be on HTTPS or localhost for the microphone to work. English, Tamil and Hindi can be spoken, but only English is sorted into category, date and place (`app/dictation.py`).

## Backups

```
.venv/bin/python -m app.backup create --out backups --keep 14
.venv/bin/python -m app.backup restore backups/crms-20261105-120000.tar.gz
```

An archive holds every SQL table and every MongoDB collection (which includes the uploaded files), so it also moves data between SQLite, PostgreSQL and MySQL. Restore only loads into an empty database. To run it daily, add a cron line such as `0 2 * * * cd /path/to/app && .venv/bin/python -m app.backup create`. Keep the archives somewhere other than the machine that runs the app: they contain personal data.

## Deploying

Set these on the host:

| Setting | Value |
| --- | --- |
| `CRMS_ENV` | `production`. The app then refuses to start without `CRMS_SECRET`, and the session cookie is sent only over HTTPS. |
| `CRMS_SECRET` | a long random string, for example `python3 -c "import secrets; print(secrets.token_hex(32))"` |
| `CRMS_DB_URL` | a PostgreSQL or MySQL address. SQLite works only where the disk is kept between restarts. |
| `MONGO_URL` | a MongoDB address; `mongodb+srv://` addresses work |

The `Dockerfile` builds the React app and the API into one image that listens on `$PORT`. Serve it over HTTPS. Create the first admin without the demo accounts:

```
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
| `CRMS_DB_URL` | the Neon connection string |
| `MONGO_URL` | the Atlas address |
| `CRMS_ADMIN_EMAIL`, `CRMS_ADMIN_PASSWORD` | the first admin (password of 12 or more characters) |

`CRMS_SECRET` is generated for you. On the first start the app creates the tables and the admin. Sign in, then add police stations on the Users page.

For a demo, set `CRMS_SAMPLE_DATA=300` before the first start instead of the admin values. That loads the demo accounts (`admin@crms.test` and the others, password `password123`) and 300 sample complaints. Change those passwords before sharing the link widely.

Free web services sleep after about 15 minutes idle and take about a minute to wake, so open the site before presenting. Their disks are wiped on restart, which is why files and records live in the databases. Free tiers change, so check each provider's current terms. Koyeb and Hugging Face Spaces also build from the `Dockerfile` if you prefer them.

## Tests

```
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest
```

The tests use an in-memory stand-in for MongoDB and a temporary SQLite file, so they need no running server. To run them against a real database instead:

```
CRMS_TEST_DB_URL=postgresql://crms:crms@localhost:5432/crms .venv/bin/python -m pytest
CRMS_TEST_DB_URL=mysql://crms:crms@localhost:3306/crms .venv/bin/python -m pytest
```

That wipes every table in the database it points at, so use the development containers.

There are also browser tests that click through the app in Chromium. Build the frontend first, and install Playwright (`pip install playwright`); they use the system Chromium if there is one.

```
.venv/bin/python -m pytest tests/e2e
```

## Layout

- `app/routes/` one router per area: account, complaints, cases, criminals, admin
- `app/lifecycle.py` the status rules for complaints and cases
- `app/db.py` one query interface over SQLite, PostgreSQL and MySQL
- `app/schemas/` the table definitions for each database
- `app/mongo.py` MongoDB collections and helpers
- `app/backup.py` backup and restore
- `frontend/src/` the React app

## Known limits

- Sign-in is locked for 15 minutes after five wrong passwords for one email from one address. The count is kept in MongoDB, and the address is the one the server sees, so behind a proxy it needs the proxy's forwarded address configured.
- SQLite or PostgreSQL or MySQL, and MongoDB, are written separately, so a failure between the two writes can leave them out of step. There is no cross-database transaction.
- Uploads are stored in MongoDB and are limited to images, PDFs and text files of 5 MB or less, five per complaint.
- Each request opens its own database connection; there is no connection pool.
