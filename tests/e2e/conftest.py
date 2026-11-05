"""Runs the real app on a local port so a browser can click through it."""
import shutil
import socket
import threading
import time

import mongomock
import pytest
import uvicorn

from app import create_app, db
from app.auth import hash_password
from app.main_config import ROOT

playwright_sync = pytest.importorskip("playwright.sync_api")

if not (ROOT / "frontend" / "dist" / "index.html").exists():
    pytest.skip("build the frontend first (cd frontend && npm run build)", allow_module_level=True)


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def site(tmp_path_factory):
    path = f"sqlite:///{tmp_path_factory.mktemp('e2e') / 'e2e.db'}"
    app = create_app(database=path, secret="e2e", mongo_client=mongomock.MongoClient())
    token = db.use(db.connect(path))
    conn = db.get_db()
    conn.execute("INSERT INTO police_station (name, jurisdiction) VALUES ('Central', 'Centre')")
    for name, email, role in (("Admin", "admin@e2e.test", "admin"), ("Asha", "asha@e2e.test", "citizen")):
        uid = conn.execute(
            "INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)",
            (name, email, hash_password("password123"), role),
        ).lastrowid
        conn.execute(f"INSERT INTO {role} (user_id) VALUES (?)", (uid,))
    conn.commit()
    db.release(token)

    port = free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(5)


@pytest.fixture(scope="session")
def browser():
    with playwright_sync.sync_playwright() as p:
        # use the system Chromium when there is one, so no browser download is needed
        exe = shutil.which("chromium") or shutil.which("chromium-browser") or shutil.which("google-chrome-stable")
        b = p.chromium.launch(executable_path=exe, args=["--no-sandbox"])
        yield b
        b.close()


@pytest.fixture
def page(browser, site):
    context = browser.new_context(viewport={"width": 1200, "height": 800})
    # the map tiles come from the internet; the tests answer with a blank image instead
    context.route("**/tile.openstreetmap.org/**", lambda r: r.fulfill(status=200, body=b"", content_type="image/png"))
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    # a 400 from the API is the app refusing something on purpose, which some tests provoke
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" and "status of 400" not in m.text else None)
    page.base = site
    yield page
    context.close()
    assert not errors, errors
