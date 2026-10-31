# Crime Records Management System

A small web app for a DBMS lab. Citizens file and track complaints; police officers and admins verify them, open cases, and manage criminal records, evidence and reports. The product requirements are in `docs/prd/index.html`.

Built with Flask and SQLite. The schema is plain SQL in `app/schema.sql`.

## Run it

```
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
FLASK_APP=run.py .venv/bin/flask seed     # demo stations, accounts and records
.venv/bin/python run.py                   # http://localhost:5000
```

The seed command creates three demo accounts (`admin@crms.test`, `officer@crms.test`, `citizen@crms.test`) that share the password `password123`. Change or delete them before using the app for anything real.

## Tests

```
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest
```

## Layout

- `app/routes/` one blueprint per area: account, complaints, cases, criminals, admin
- `app/lifecycle.py` the status rules for complaints and cases
- `app/schema.sql` tables, indexes and report views
- `app/templates/`, `app/static/` pages and styles
- `docs/prd/` the product requirements page

## Not built yet

- File attachments on complaints; citizens add written statements and evidence descriptions instead.
- MySQL, PostgreSQL and MongoDB backends. The app runs on SQLite only.
