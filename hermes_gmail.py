#!/usr/bin/env python3
# Code written by Hermes Agent using muse-glimmer with low effort.
"""
hermes_gmail.py - Send and search Gmail via IMAP/SMTP
Phase 1: send email
Phase 2: search email
"""
import argparse
import os
import json
import smtplib
from email.message import EmailMessage
from datetime import datetime
from pathlib import Path

CONFIG_PATH = Path("/mnt/data/hermes/scripts/email-services/hermes-gmail-config.json")
LOG_DIR = Path("/mnt/data/hermes/scripts/email-services/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)

def get_app_password():
    env_path = "/home/smcd/.hermes/profiles/default/gateway_email.env"
    try:
        for line in open(env_path):
            if line.startswith("GMAIL_APP_PASSWORD="):
                return line.split("=",1)[1].strip().strip('"\'')
    except FileNotFoundError:
        pass
    return os.environ.get("GMAIL_APP_PASSWORD","")

def log_event(event_type, data):
    ts = datetime.utcnow().isoformat()
    log_file = LOG_DIR / f"{event_type}.log"
    with open(log_file, "a") as f:
        f.write(f"{ts} | {data}\n")

def send_email(to, subject, body, from_addr=None, cc=None, bcc=None, dry_run=False):
    cfg = load_config()
    primary_email = cfg["email"]["default_sender"]
    sender = from_addr or primary_email
    password = get_app_password()
    if not password:
        raise RuntimeError("GMAIL_APP_PASSWORD not found")

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = ", ".join(to)
    msg["Subject"] = subject
    if cc:
        msg["Cc"] = ", ".join(cc)
    # Send as HTML going forward
    msg.set_content(body, subtype='html')

    if dry_run:
        print("[DRY RUN] Would send:")
        print(msg)
        log_event("send", f"DRY_RUN to={to} subject={subject}")
        return True

    smtp_host = cfg["smtp"]["host"]
    smtp_port = cfg["smtp"]["port"]
    with smtplib.SMTP_SSL(smtp_host, smtp_port) as smtp:
        smtp.login(primary_email, password)
        recipients = to + (cc or []) + (bcc or [])
        smtp.send_message(msg)
    log_event("send", f"SENT from={sender} to={to} subject={subject}")
    print("Sent")
    return True

def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd")
    send_p = sub.add_parser("send")
    send_p.add_argument("--to", nargs="+", required=True)
    send_p.add_argument("--subject", required=True)
    send_p.add_argument("--body", required=True)
    send_p.add_argument("--from", dest="from_addr")
    send_p.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.cmd == "send":
        send_email(args.to, args.subject, args.body, args.from_addr, dry_run=args.dry_run)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
