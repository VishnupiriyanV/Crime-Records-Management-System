"""Sending e-mail: password resets and alerts. With no SMTP server set up, nothing is sent (and nothing breaks)."""
import logging
import os
import smtplib
import threading
from email.message import EmailMessage

log = logging.getLogger("crms.mail")
# uvicorn only sets up its own loggers; this one writes to the same console so the host's log shows mail results
log.setLevel(logging.INFO)
if not log.handlers:
    _out = logging.StreamHandler()
    _out.setFormatter(logging.Formatter("%(levelname)s:     %(name)s: %(message)s"))
    log.addHandler(_out)


def configured():
    return bool(os.environ.get("SMTP_HOST"))


def base_url():
    """The public address of the site, for links in e-mails. Set CRMS_BASE_URL on a live site."""
    return os.environ.get("CRMS_BASE_URL", "").rstrip("/")


def alerts_enabled():
    return configured() and os.environ.get("CRMS_EMAIL_ALERTS", "1") != "0"


def _deliver(message):
    host = os.environ["SMTP_HOST"]
    port = int(os.environ.get("SMTP_PORT", "587"))
    try:
        if port == 465:
            server = smtplib.SMTP_SSL(host, port, timeout=15)
        else:
            server = smtplib.SMTP(host, port, timeout=15)
            if os.environ.get("SMTP_STARTTLS", "1") != "0":
                server.starttls()
        with server:
            if os.environ.get("SMTP_USER"):
                server.login(os.environ["SMTP_USER"], os.environ.get("SMTP_PASSWORD", ""))
            server.send_message(message)
        log.info("E-mail \u201c%s\u201d handed to %s for %s.", message["Subject"], host, message["To"])
    except Exception as err:  # a mail problem must never break the action that caused it
        log.warning("Could not send e-mail to %s: %s", message["To"], err)


def send(to, subject, text, wait=False):
    """Queue a plain-text e-mail; returns True if one was handed to the mail server."""
    if not configured():
        # on a development machine the message is shown here, which is how a reset link is found without a mail server
        if os.environ.get("CRMS_ENV") != "production":
            log.warning("E-mail not set up (SMTP_HOST). Would send to %s: %s\n%s", to, subject, text)
        else:
            # never the text: it can hold a reset link
            log.warning("Not sending \u201c%s\u201d to %s: SMTP_HOST is not set on this server.", subject, to)
        return False
    message = EmailMessage()
    message["To"] = to
    message["From"] = os.environ.get("SMTP_FROM") or os.environ.get("SMTP_USER") or "crms@localhost"
    message["Subject"] = subject
    message.set_content(text)
    if wait:
        _deliver(message)
    else:
        threading.Thread(target=_deliver, args=(message,), daemon=True).start()
    return True
