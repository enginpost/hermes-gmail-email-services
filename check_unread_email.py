#!/usr/bin/env python3
# Code written by Hermes Agent using muse-glimmer with low effort.
"""Check unread Gmail messages from the last 24 hours and categorize them."""

import imaplib
import email
from email.header import decode_header
from datetime import datetime, timezone, timedelta
import sys
import os
import re
import json
import argparse

# Config
EMAIL = "mchoyt73@gmail.com"
APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
if not APP_PASSWORD:
    env_path = "/home/smcd/.hermes/profiles/default/gateway_email.env"
    for line in open(env_path):
        if line.startswith("GMAIL_APP_PASSWORD="):
            APP_PASSWORD = line.split("=", 1)[1].strip().strip("'\"")
            break

if not APP_PASSWORD:
    print("ERROR: No Gmail app password found.")
    sys.exit(1)

# Load categories config
CONFIG_PATH = "/mnt/data/hermes/scripts/email-services/email-categories-config.json"
try:
    with open(CONFIG_PATH, "r") as f:
        _cfg = json.load(f)
    CATEGORIES = {}
    CATEGORY_KEYWORDS = {}
    for cat in _cfg.get("categories", []):
        cid = cat["id"]
        CATEGORIES[cid] = (cat.get("display", ""), cat.get("label", ""))
        CATEGORY_KEYWORDS[cid] = cat.get("keywords", [])
    UNCATEGORIZED_LABEL = _cfg.get("uncategorized_label", "Other")
except Exception as e:
    print(f"WARNING: Could not load categories config: {e}")
    CATEGORIES = {
        0: ("💼 CAREER / JOB OPPORTUNITIES", "Career"),
        1: ("🧾 DIGITAL RECEIPTS", "Receipt"),
        2: ("📰 NEWSLETTERS / DIGESTS", "Newsletter"),
        3: ("🛒 RETAIL / ADVERTISEMENTS", "Retail"),
        4: ("👥 SOCIAL / FRIENDS & FAMILY", "Social"),
        5: ("⚙️ ACCOUNT / SERVICE UPDATES", "Service"),
    }
    CATEGORY_KEYWORDS = {}
    UNCATEGORIZED_LABEL = "Other"

def decode_header_str(hdr):
    if not hdr:
        return ""
    parts = decode_header(hdr)
    result = []
    for part, charset in parts:
        if isinstance(part, bytes):
            result.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            result.append(part)
    return "".join(result)

def extract_email_addr(raw):
    """Extract just the email address from a From/To header."""
    if "<" in raw:
        return raw.split("<", 1)[1].split(">", 1)[0].strip().lower()
    if "@" in raw:
        return raw.strip().lower()
    return ""

def format_time_received(raw_date):
    try:
        msg_date = email.utils.parsedate_to_datetime(raw_date)
        return msg_date.strftime("%b %d, %H:%M")
    except Exception:
        return raw_date[:30] if raw_date else "unknown"

def escape_html(text):
    """Escape < > & so they don't break Telegram parse_mode=HTML."""
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    return text

def normalize_email(raw_addr):
    """Strip brackets/quotes and lowercase so steve@... and <steve@...> match."""
    # Extract from Name <email> if present, else just clean the raw string
    m = re.search(r'<([^>]+)>', raw_addr)
    if m:
        return m.group(1).strip().lower()
    return raw_addr.strip().lower()

def categorize_email(sender_name, sender_addr, subject):
    combined = f"{sender_name} {sender_addr} {subject}".lower()
    # Iterate categories in order; first match wins
    for cid, keywords in CATEGORY_KEYWORDS.items():
        if any(kw.lower() in combined for kw in keywords):
            return cid
    return -1  # Uncategorized -> "📬 OTHER"


def main():
    parser = argparse.ArgumentParser(description="Check unread Gmail and categorize")
    parser.add_argument("--since-hours", type=int, default=24, help="Hours lookback for unread mail")
    args = parser.parse_args()
    hours = args.since_hours

    now = datetime.now(timezone.utc)
    since_date = (now - timedelta(hours=hours)).strftime("%d-%b-%Y")

    imap = imaplib.IMAP4_SSL("imap.gmail.com", 993)
    imap.login(EMAIL, APP_PASSWORD)
    imap.select("INBOX")

    # Ensure category labels exist as IMAP mailboxes
    for _, label in CATEGORIES.values():
        try:
            imap.create(label)
        except Exception:
            pass
    if UNCATEGORIZED_LABEL:
        try:
            imap.create(UNCATEGORIZED_LABEL)
        except Exception:
            pass

    status, msg_ids = imap.uid('search', None, f'(UNSEEN SINCE {since_date})')
    if status != "OK":
        imap.logout()
        print("❌ IMAP search failed.")
        return

    id_list = msg_ids[0].split() if msg_ids[0] else []
    if not id_list:
        imap.logout()
        return

    # Build set of category label names for quick check
    category_labels = {label for _, label in CATEGORIES.values()}
    # Include uncategorized label if defined
    if UNCATEGORIZED_LABEL:
        category_labels.add(UNCATEGORIZED_LABEL)

    labeled = 0
    skipped = 0

    for mid in reversed(id_list):
        # limit processing
        if len(id_list) - int(mid) > 100:
            continue

        # Fetch X-GM-LABELS and headers
        status, data = imap.uid('fetch', mid, '(X-GM-LABELS BODY.PEEK[HEADER.FIELDS (SUBJECT FROM DATE TO)])')
        if status != "OK":
            continue

        # Parse X-GM-LABELS
        labels = set()
        raw_resp = b"".join([part for part in data if isinstance(part, bytes)])
        m = re.search(br'X-GM-LABELS \((.*?)\)', raw_resp)
        if m:
            labels_str = m.group(1).decode('utf-8', errors='ignore')
            # Labels are like \Inbox, CategoryName
            for lbl in labels_str.split():
                lbl_clean = lbl.strip('\\')
                # Gmail returns labels with backslash prefix for system labels
                labels.add(lbl_clean)

        # If already categorized, skip
        if labels & category_labels:
            skipped += 1
            continue

        # Parse headers
        # Find header part
        try:
            # data[0][1] contains the raw header bytes
            raw_header = data[0][1]
            msg = email.message_from_bytes(raw_header)
        except Exception:
            # Fallback fetch headers only
            status2, data2 = imap.uid('fetch', mid, '(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM DATE TO)])')
            if status2 != "OK":
                continue
            raw_header = data2[0][1]
            msg = email.message_from_bytes(raw_header)

        subject = decode_header_str(msg.get("Subject", ""))
        sender_raw = decode_header_str(msg.get("From", ""))
        date_raw = msg.get("Date", "")
        # Verify within window
        try:
            msg_date = email.utils.parsedate_to_datetime(date_raw)
            if msg_date.tzinfo is None:
                msg_date = msg_date.replace(tzinfo=timezone.utc)
            if msg_date < now - timedelta(hours=hours):
                continue
        except Exception:
            pass

        sender_addr = extract_email_addr(sender_raw)
        sender_name = decode_header_str(sender_raw.split("<")[0].strip()) if "<" in sender_raw else "Unknown"

        cat_idx = categorize_email(sender_name, sender_addr, subject)
        if cat_idx == -1:
            label_name = UNCATEGORIZED_LABEL
        else:
            _, label_name = CATEGORIES.get(cat_idx, ("", UNCATEGORIZED_LABEL))

        if not label_name:
            continue

        # Apply label
        try:
            imap.uid('STORE', mid, '+X-GM-LABELS', f'("{label_name}")')
            labeled += 1
        except Exception:
            pass

    imap.logout()
    # No Telegram output, scan-and-label only
    # Optional quiet confirmation
    # print(f"Scan complete. Labeled: {labeled}, Skipped already labeled: {skipped}")


if __name__ == "__main__":
    main()
