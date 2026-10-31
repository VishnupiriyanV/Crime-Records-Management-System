# Crime Records Management System

A web app for a DBMS lab. Citizens file and track complaints; police officers and admins verify them, open cases, and manage criminal records, evidence and reports. The product requirements are in `docs/prd/index.html`.

- **Backend:** FastAPI, a JSON API under `/api`.
- **Frontend:** React (Vite), in `frontend/`.
- **Relational database:** SQLite (default), PostgreSQL or MySQL, chosen by one setting. It holds users, complaints, cases, criminals and reports.
- **MongoDB:** holds the document-shaped data: evidence, citizen notes, notifications, file records and the status audit trail. Rows and documents are linked by id.
- **Files:** complaint attachments are saved under `data/uploads/`.

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

### Choosing the relational database

SQLite needs nothing. For PostgreSQL or MySQL, start the matching container and point `CRMS_DB_URL` at it before seeding and running:

```
docker compose up -d postgres mysql
export CRMS_DB_URL=postgresql://crms:crms@localhost:5432/crms     # or
export CRMS_DB_URL=mysql://crms:crms@localhost:3306/crms
```

The tables are created on first start from `app/schemas/<database>.sql`. The passwords in `docker-compose.yml` are for local development only.

Other settings, all optional: `MONGO_URL` (default `mongodb://localhost:27017`), `MONGO_DB` (default `crms`), `CRMS_UPLOADS` (upload folder), `CRMS_SECRET` (session signing key).

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

## Layout

- `app/routes/` one router per area: account, complaints, cases, criminals, admin
- `app/lifecycle.py` the status rules for complaints and cases
- `app/db.py` one query interface over SQLite, PostgreSQL and MySQL
- `app/schemas/` the table definitions for each database
- `app/mongo.py` MongoDB collections and helpers
- `frontend/src/` the React app
- `docs/prd/` the product requirements page

## Known limits

- Sign-in is locked for 15 minutes after five wrong passwords for one email from one address. The count is kept in MongoDB, and the address is the one the server sees, so behind a proxy it needs the proxy's forwarded address configured.
- SQLite or PostgreSQL or MySQL, and MongoDB, are written separately, so a failure between the two writes can leave them out of step. There is no cross-database transaction.
- Uploads are limited to images, PDFs and text files of 5 MB or less, five per complaint.
- Each request opens its own database connection; there is no connection pool.
