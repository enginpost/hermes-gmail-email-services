#!/usr/bin/env python3
"""Check unread Gmail messages from the last 24 hours and categorize them."""

import imaplib
import email
from email.header import decode_header
from datetime import datetime, timezone, timedelta
import sys
import os
import re

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

CATEGORIES = {
    0: ("💼 CAREER / JOB OPPORTUNITIES", "Career"),
    1: ("🧾 DIGITAL RECEIPTS", "Receipt"),
    2: ("📰 NEWSLETTERS / DIGESTS", "Newsletter"),
    3: ("🛒 RETAIL / ADVERTISEMENTS", "Retail"),
    4: ("👥 SOCIAL / FRIENDS & FAMILY", "Social"),
    5: ("⚙️ ACCOUNT / SERVICE UPDATES", "Service"),
}

def categorize_email(sender_name, sender_addr, subject):
    combined = f"{sender_name} {sender_addr} {subject}".lower()

    if any(kw in combined for kw in [
        "hiring", "opportunity", "position", "interview", "career",
        "job", "recruiter", "apply", "employment", "vacancy",
        "open position", "candidate", "role at", "we're hiring"
    ]):
        return 0

    if any(kw in combined for kw in [
        "receipt", "invoice", "paid", "order confirmation",
        "payment received", "transaction", "purchase confirmed",
        "your payment of"
    ]):
        return 1

    if any(kw in combined for kw in [
        "newsletter", "digest", "weekly update", "monthly roundup",
        "this week in", "edition of", "your weekly", "insider",
        "the batch", "today's email"
    ]):
        return 2

    if any(kw in combined for kw in [
        "sale", "discount", "deal", "offer", "promo", "coupons",
        "30% off", "free shipping", "shop now", "big names",
        "special offer", "limited time", "exclusive deal", "deals"
    ]):
        return 3

    if any(kw in combined for kw in [
        "friend", "family", "social", "invit", "birthday",
        "party", "dinner", "hang out", "join us",
    ]):
        return 4

    if any(kw in combined for kw in [
        "pricing", "upgrade", "plan", "subscription",
        "account update", "verification", "security alert"
    ]):
        return 5

    return -1  # Uncategorized -> "📬 OTHER"


def main():
    now = datetime.now(timezone.utc)

    # Gmail IMAP SINCE uses format DD-Mon-YYYY (UTC)
    since_date = (now - timedelta(hours=24)).strftime("%d-%b-%Y")

    imap = imaplib.IMAP4_SSL("imap.gmail.com", 993)
    imap.login(EMAIL, APP_PASSWORD)
    imap.select("INBOX")

    # Search: unseen emails received since yesterday at the same time
    status, msg_ids = imap.search(None, f'(UNSEEN SINCE {since_date})')
    if status != "OK":
        imap.logout()
        print("❌ IMAP search failed.")
        return

    id_list = msg_ids[0].split() if msg_ids[0] else []

    # Structure: categories -> {cat_index -> [ (to_addr, sender_addr, subject, time_str) ] }
    categories = {}
    uncategorized = []

    for mid in reversed(id_list):
        # Only fetch headers for recent emails (limit to first 100)
        if len(id_list) - int(mid) > 100:
            continue

        status, data = imap.fetch(mid, "(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM DATE TO)])")
        if status != "OK":
            continue

        raw_header = data[0][1]
        msg = email.message_from_bytes(raw_header)

        subject = decode_header_str(msg["Subject"])
        sender_raw = decode_header_str(msg["From"])
        to_raw = decode_header_str(msg["To"])
        date_raw = msg.get("Date", "")
        time_str = format_time_received(date_raw)

        # Parse and verify within 24h window
        try:
            msg_date = email.utils.parsedate_to_datetime(date_raw)
            if msg_date.tzinfo is None:
                msg_date = msg_date.replace(tzinfo=timezone.utc)
            if msg_date < now - timedelta(hours=24):
                continue
        except Exception:
            pass

        sender_addr = extract_email_addr(sender_raw)
        sender_name = decode_header_str(sender_raw.split("<")[0].strip()) if "<" in sender_raw else "Unknown"

        # Collect all To addresses, normalize so <steve@...> and steve@... group together
        to_addrs = [normalize_email(a) for a in to_raw.split(",") if "@" in a]
        primary_to = to_addrs[0] if to_addrs else EMAIL

        cat_idx = categorize_email(sender_name, sender_addr, subject)
        target_list = uncategorized if cat_idx == -1 else categories.setdefault(cat_idx, [])
        # Escape early — all user content goes in HTML-safe
        target_list.append((primary_to, escape_html(sender_addr), escape_html(subject), escape_html(time_str)))

    imap.logout()

    # Check total
    total_count = sum(len(v) for v in categories.values()) + len(uncategorized)
    if total_count == 0:
        print("📭 Inbox is quiet — no new unread messages in the last 24 hours.")
        return

    html_blocks = {
        "title": "",
        "inbox_summary": "",
        "category_details": []
    }

    # ── Block 1: Title ─────────────────────────────────────────────
    today_str = now.strftime("%Y-%m-%d")
    title_block = "<b>Your Inbox as of {}</b>\n<b>━━━━━━━━━━━━━━━━━━━━</b>".format(today_str)
    html_blocks["title"] = title_block

    # ── Block 2: Summary ───────────────────────────────────────────
    sorted_cats = sorted(categories.items(), key=lambda x: -len(x[1]))
    summary_lines = ["<i>- SUMMARY -</i>"]
    for cat_idx, emails in sorted_cats:
        cat_display = CATEGORIES[cat_idx][0].replace("💼", "").replace("🧾", "") \
            .replace("📰", "").replace("🛒", "").replace("👥", "").replace("⚙️", "").strip()
        summary_lines.append("• {} ({})".format(escape_html(cat_display), len(emails)))
    if uncategorized:
        summary_lines.append("• OTHER ({})".format(len(uncategorized)))
    summary_lines.append("<b>━━━━━━━━━━━━━━━━━━━━</b>")
    html_blocks["inbox_summary"] = "\n".join(summary_lines)

    # ── Block 3+: Category details (one block per category) ────────
    divider = "- - - - - - - -"
    for cat_idx, emails in sorted_cats:
        cat_display = CATEGORIES[cat_idx][0].replace("💼", "").replace("🧾", "") \
            .replace("📰", "").replace("🛒", "").replace("👥", "").replace("⚙️", "").strip()
        cat_name_escaped = escape_html(cat_display.upper())

        groups = {}
        for to_addr, sender_addr, subj, t in emails:
            groups.setdefault(to_addr, []).append((sender_addr, subj, t))

        detail_lines = ["<b>- {} -</b>".format(cat_name_escaped)]
        for to_addr, items in sorted(groups.items(), key=lambda x: -len(x[1])):
            detail_lines.append("<i>To {}:</i>".format(to_addr))
            for sender_addr, subj, t in items:
                detail_lines.append("<blockquote>")
                detail_lines.append("Subj: {}".format(subj))
                detail_lines.append("• <i>From {} on {}</i>".format(sender_addr, t))
                detail_lines.append("</blockquote>")
            detail_lines.append(divider)

        html_blocks["category_details"].append("\n".join(detail_lines))

    # Uncategorized as last category detail block
    if uncategorized:
        groups = {}
        for to_addr, sender_addr, subj, t in uncategorized:
            groups.setdefault(to_addr, []).append((sender_addr, subj, t))

        detail_lines = ["<b>- OTHER -</b>"]
        for to_addr, items in sorted(groups.items(), key=lambda x: -len(x[1])):
            detail_lines.append("<i>To {}:</i>".format(to_addr))
            for sender_addr, subj, t in items:
                detail_lines.append("<blockquote>")
                detail_lines.append("Subj: {}".format(subj))
                detail_lines.append("• <i>From {} on {}</i>".format(sender_addr, t))
                detail_lines.append("</blockquote>")
            detail_lines.append(divider)

        html_blocks["category_details"].append("\n".join(detail_lines))

    # Print blocks separated by a delimiter for multi-message delivery
    print(html_blocks["title"])
    print("---BLOCK---")
    print(html_blocks["inbox_summary"])
    print("---BLOCK---")
    for block in html_blocks["category_details"]:
        print(block)
        print("---BLOCK---")


if __name__ == "__main__":
    main()
