#!/usr/bin/env python3
"""
search_gmail.py
Search Gmail via IMAP by category label and read/unread status.
Returns JSON: total + items with uid, subject, sender, date, label, gmail_link
"""
import imaplib
import json
import os
import re
import email
from email.header import decode_header
from datetime import datetime, timedelta, timezone
from pathlib import Path

CONFIG_PATH = "/mnt/data/hermes/scripts/email-services/email-categories-config.json"
GATEWAY_ENV = "/home/smcd/.hermes/profiles/default/gateway_email.env"

EMAIL = "mchoyt73@gmail.com"
APP_PASSWORD = ""

def load_env():
    global APP_PASSWORD
    paths = [
        "/mnt/data/hermes/profiles/default/gateway_email.env",
        "/home/smcd/.hermes/profiles/default/gateway_email.env"
    ]
    for p in paths:
        if os.path.exists(p):
            for line in open(p):
                if line.startswith("GMAIL_APP_PASSWORD="):
                    APP_PASSWORD = line.split("=",1)[1].strip().strip('"')
                    return
    # fallback to env
    APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD","")

def load_categories():
    with open(CONFIG_PATH) as f:
        cfg = json.load(f)
    categories = {}
    for c in cfg.get("categories", []):
        categories[c["id"]] = c
    return categories

def decode_header_str(s):
    parts = decode_header(s or "")
    return "".join(p[0].decode(p[1] or "utf-8") if isinstance(p[0], bytes) else p[0] for p in parts)

def extract_email_addr(s):
    m = re.search(r'<([^>]+)>', s or "")
    return m.group(1) if m else s.strip()

def imap_connect():
    load_env()
    imap = imaplib.IMAP4_SSL("imap.gmail.com", 993)
    imap.login(EMAIL, APP_PASSWORD)
    imap.select("INBOX")
    return imap

def parse_labels(raw_resp):
    labels = set()
    m = re.search(br'X-GM-LABELS \((.*?)\)', raw_resp)
    if m:
        labels_str = m.group(1).decode('utf-8', errors='ignore')
        for lbl in labels_str.split():
            lbl_clean = lbl.strip('\\')
            labels.add(lbl_clean)
    return labels

def search_gmail(labels, status="unread", since_hours=None, limit=200):
    categories = load_categories()
    # Validate labels
    valid_labels = {c["label"] for c in categories.values()}
    requested = set(labels)
    if not requested.issubset(valid_labels):
        raise ValueError(f"Invalid labels. Valid: {valid_labels}")
    if not requested:
        raise ValueError("Label is required for search")

    imap = imap_connect()
    # Build IMAP search criteria
    criteria = []
    if status == "unread":
        criteria.append("UNSEEN")
    elif status == "read":
        criteria.append("SEEN")
    # Date window
    if since_hours:
        since_date = (datetime.now(timezone.utc) - timedelta(hours=since_hours)).strftime("%d-%b-%Y")
        criteria.append(f"SINCE {since_date}")
    # Search
    search_str = " ".join(criteria)
    status_resp, msg_ids = imap.uid('search', None, search_str)
    if status_resp != "OK":
        imap.logout()
        return {"total":0,"items":[]}
    ids = msg_ids[0].split()
    results = []
    for mid in reversed(ids):
        if len(results) >= limit:
            break
        status_f, data = imap.uid('fetch', mid, '(X-GM-MSGID X-GM-THRID X-GM-LABELS BODY.PEEK[HEADER.FIELDS (SUBJECT FROM DATE MESSAGE-ID)])')
        if status_f != "OK":
            continue
        # Flatten fetch response to bytes
        raw_parts = []
        for part in data:
            if isinstance(part, bytes):
                raw_parts.append(part)
            elif isinstance(part, tuple):
                for sub in part:
                    if isinstance(sub, bytes):
                        raw_parts.append(sub)
        raw = b"".join(raw_parts)
        labels_found = parse_labels(raw)
        if not requested & labels_found:
            continue
        # Parse headers
        try:
            raw_header = data[0][1]
            msg = email.message_from_bytes(raw_header)
        except Exception:
            continue
        subject = decode_header_str(msg.get("Subject",""))
        sender_raw = decode_header_str(msg.get("From",""))
        date_raw = msg.get("Date","")
        sender_name = sender_raw.split("<")[0].strip()
        sender_email = extract_email_addr(sender_raw)
        # Date iso
        try:
            dt = email.utils.parsedate_to_datetime(date_raw)
            date_iso = dt.isoformat()
        except Exception:
            date_iso = date_raw
        # Determine which label matched
        matched_label = next(iter(requested & labels_found), "")
        # Parse X-GM-MSGID / X-GM-THRID for Gmail web link
        msgid_dec = None
        thread_dec = None
        m_msgid = re.search(br'X-GM-MSGID (\d+)', raw)
        if m_msgid:
            msgid_dec = int(m_msgid.group(1))
        m_thrid = re.search(br'X-GM-THRID (\d+)', raw)
        if m_thrid:
            thread_dec = int(m_thrid.group(1))
        # Try to get Message-ID header for rfc822msgid link
        message_id = None
        try:
            raw_header = data[0][1] if isinstance(data[0], tuple) else None
            if raw_header:
                msg = email.message_from_bytes(raw_header)
                message_id = msg.get('Message-ID')
        except Exception:
            message_id = None
        if message_id:
            # Build rfc822msgid search URL – most reliable
            import urllib.parse
            q = f"rfc822msgid:{message_id.strip('<>')}"
            gmail_link = f"https://mail.google.com/mail/u/0/#search/{urllib.parse.quote(q)}"
        elif thread_dec is not None and msgid_dec is not None:
            thread_hex = format(thread_dec, 'x')
            msg_hex = format(msgid_dec, 'x')
            gmail_link = f"https://mail.google.com/mail/u/0/#all/{thread_hex}|{msg_hex}"
        elif thread_dec is not None:
            gmail_link = f"https://mail.google.com/mail/u/0/#thread-f:{thread_dec}"
        elif msgid_dec is not None:
            msgid_hex = format(msgid_dec, 'x')
            gmail_link = f"https://mail.google.com/mail/u/0/#inbox/{msgid_hex}"
        else:
            msgid_hex = mid.decode() if isinstance(mid, bytes) else str(mid)
            gmail_link = f"https://mail.google.com/mail/u/0/#inbox/{msgid_hex}"
        results.append({
            "uid": mid.decode() if isinstance(mid, bytes) else str(mid),
            "subject": subject,
            "sender_name": sender_name,
            "sender_email": sender_email,
            "date_iso": date_iso,
            "labels": sorted(list(labels_found)),
            "matched_label": matched_label,
            "gmail_link": gmail_link
        })
    imap.logout()
    return {"total": len(results), "items": results}

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--labels", required=True, help="comma-separated labels")
    p.add_argument("--status", default="unread", choices=["unread","read","all"])
    p.add_argument("--since-hours", type=int)
    p.add_argument("--limit", type=int, default=200)
    args = p.parse_args()
    labels = [l.strip() for l in args.labels.split(",")]
    out = search_gmail(labels, args.status, args.since_hours, args.limit)
    print(json.dumps(out, indent=2))
