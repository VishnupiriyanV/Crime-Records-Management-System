import os
import secrets
from pathlib import Path

from flask import Flask, flash, g, redirect, render_template, request

from . import db
from .auth import check_csrf, csrf_token, load_user
from .db import one
from .lifecycle import RuleError

ROOT = Path(__file__).resolve().parent.parent


def _secret_key():
    if os.environ.get("CRMS_SECRET"):
        return os.environ["CRMS_SECRET"]
    key_file = ROOT / "data" / "secret.key"
    if not key_file.exists():
        key_file.parent.mkdir(exist_ok=True)
        key_file.write_text(secrets.token_hex(32))
    return key_file.read_text().strip()


def create_app(config=None):
    app = Flask(__name__)
    app.config.update(
        DATABASE=str(ROOT / "data" / "crms.db"),
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_HTTPONLY=True,
    )
    if config:
        app.config.update(config)
    if not app.config.get("SECRET_KEY"):
        app.config["SECRET_KEY"] = _secret_key()

    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
    app.teardown_appcontext(db.close_db)
    with app.app_context():
        db.init_db()

    from .routes import account, admin, cases, complaints, criminals

    for module in (account, complaints, cases, criminals, admin):
        app.register_blueprint(module.bp)

    app.before_request(load_user)
    app.before_request(check_csrf)
    app.jinja_env.globals["csrf_token"] = csrf_token

    @app.context_processor
    def inject_user():
        unread = 0
        if g.get("user"):
            unread = one(
                "SELECT COUNT(*) AS n FROM notification WHERE user_id = ? AND seen = 0",
                g.user["user_id"],
            )["n"]
        return {"user": g.get("user"), "unread": unread}

    @app.errorhandler(RuleError)
    def rule_error(err):
        # send the user back to the form they came from with the reason
        if request.referrer:
            flash(str(err), "error")
            return redirect(request.referrer)
        return render_template("error.html", title="Not allowed", message=str(err)), 400

    def show_error(err):
        code = err.code
        messages = {
            403: "Your role cannot open this page.",
            404: "That page does not exist.",
        }
        message = messages.get(code, err.description)
        return render_template("error.html", title=err.name, message=message), code

    for code in (400, 403, 404):
        app.register_error_handler(code, show_error)

    from . import cli
    cli.register(app)
    return app
