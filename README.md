# Crime Records Management System

A web app for a DBMS lab. Citizens file and track complaints; police officers and admins verify them, open cases, and manage criminal records, evidence and reports. The product requirements are in `docs/prd/index.html`.

- **Backend:** FastAPI, a JSON API under `/api`.
- **Frontend:** React (Vite), in `frontend/`.
- **Databases:** SQLite holds the relational core (users, complaints, cases, criminals, reports). MongoDB holds the document-shaped data: evidence, citizen notes, notifications and the status audit trail. Rows and documents are linked by id.

## Run it

You need Python 3.11+, Node 20+ and Docker (for MongoDB).

```
docker compose up -d                          # MongoDB on localhost:27017

python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m app.seed                  # demo stations, accounts and records

cd frontend && npm install && npm run build && cd ..
.venv/bin/uvicorn run:app                     # http://localhost:8000
```

For frontend work, run `npm run dev` in `frontend/` (port 5173, it proxies `/api` to port 8000) next to uvicorn.

The seed creates three demo accounts (`admin@crms.test`, `officer@crms.test`, `citizen@crms.test`) that share the password `password123`. Change or delete them before using the app for anything real.

Settings, all optional: `MONGO_URL` (default `mongodb://localhost:27017`), `MONGO_DB` (default `crms`), `CRMS_DATABASE` (SQLite file path), `CRMS_SECRET` (session signing key).

## Tests

```
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest
```

The tests use an in-memory stand-in for MongoDB, so they need no running server.

## Layout

- `app/routes/` one router per area: account, complaints, cases, criminals, admin
- `app/lifecycle.py` the status rules for complaints and cases
- `app/schema.sql` SQLite tables, indexes and report views
- `app/mongo.py` MongoDB collections and helpers
- `frontend/src/` the React app
- `docs/prd/` the product requirements page

## Not built yet

- File attachments on complaints; citizens add written statements and evidence descriptions instead.
- MySQL and PostgreSQL backends.
- SQLite and MongoDB are written separately, so a failure between the two writes can leave them out of step; there is no cross-database transaction.
