# written by hermes agent using muse-glimmer with medium effort
import imaplib
import os
import email
import re
import urllib.parse
from datetime import datetime
from html.parser import HTMLParser
import argparse

ENV_PATH = "/home/smcd/.hermes/profiles/default/gateway_email.env"
EMAIL = "mchoyt73@gmail.com"

def load_password():
    pwd = None
    with open(ENV_PATH) as f:
        for line in f:
            if line.startswith("GMAIL_APP_PASSWORD="):
                pwd = line.split("=",1)[1].strip().strip('"\'')
                break
    return pwd

class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.current_href = None
        self.current_text = []
    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.current_href = dict(attrs).get('href')
            self.current_text = []
    def handle_data(self, data):
        if self.current_href is not None:
            self.current_text.append(data)
    def handle_endtag(self, tag):
        if tag == 'a' and self.current_href:
            text = ''.join(self.current_text).strip()
            if self.current_href and self.current_href.startswith('http'):
                self.links.append((self.current_href, text))
            self.current_href = None
            self.current_text = []

def decode_tracking(url):
    m = re.match(r'https?://tracking\.tldrnewsletter\.com/CL0/(.+)', url)
    if m:
        enc = m.group(1)
        try:
            dec = urllib.parse.unquote(enc)
            return dec
        except:
            return url
    return url

def extract_links(html):
    parser = LinkParser()
    try:
        parser.feed(html)
    except:
        pass
    out = []
    for href, text in parser.links:
        if 'unsubscribe' in href.lower() or 'manage' in href.lower() or 'advertise' in href.lower() or 'jobs.ashbyhq.com' in href.lower() or 'refer.tldr.tech' in href.lower() or 'hub.sparklp.co' in href.lower():
            continue
        real_url = decode_tracking(href)
        if not text or len(text) < 3:
            try:
                parsed = urllib.parse.urlparse(real_url)
                text = parsed.netloc or real_url
            except:
                text = real_url
        text = re.sub(r'\s+', ' ', text).strip()
        if len(text) > 120:
            text = text[:117] + '...'
        out.append((real_url, text))
    seen=set()
    uniq=[]
    for u,t in out:
        if u not in seen:
            seen.add(u)
            uniq.append((u,t))
    return uniq[:30]

def fetch_messages(imap, label, sender):
    imap.select(label)
    typ, data = imap.search(None, f'(FROM "{sender}")')
    if typ != 'OK':
        return []
    ids = data[0].split()
    msgs = []
    for mid in ids:
        typ, data = imap.fetch(mid, '(BODY.PEEK[] FLAGS INTERNALDATE)')
        if typ != 'OK':
            continue
        for part in data:
            if isinstance(part, tuple):
                raw = part[1]
                msg = email.message_from_bytes(raw)
                date_hdr = msg.get('Date')
                try:
                    dt = email.utils.parsedate_to_datetime(date_hdr)
                except:
                    dt = None
                subject_raw = msg.get('Subject','')
                try:
                    subject = email.header.make_header(email.header.decode_header(subject_raw))
                    subject = str(subject)
                except:
                    subject = subject_raw
                subject = re.sub(r'\s+', ' ', subject).strip()
                body_html = ""
                if msg.is_multipart():
                    for p in msg.walk():
                        if p.get_content_type() == 'text/html':
                            try:
                                body_html = p.get_payload(decode=True).decode(errors='ignore')
                            except:
                                pass
                else:
                    try:
                        body_html = msg.get_payload(decode=True).decode(errors='ignore')
                    except:
                        pass
                msg_id = msg.get('Message-ID','')
                msgs.append((dt, subject, body_html, msg_id))
    return msgs

def render_entry(dt, subject):
    # placeholder, links will be added later
    return dt, subject

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sender', default='dan@tldrnewsletter.com')
    parser.add_argument('--label', default='Newsletter')
    parser.add_argument('--output', default='/mnt/data/obsidian/second_brain/hermes-gmail/Newsletters/tldrnews.md')
    args = parser.parse_args()

    pwd = load_password()
    imap = imaplib.IMAP4_SSL("imap.gmail.com", 993)
    imap.login(EMAIL, pwd)
    msgs = fetch_messages(imap, args.label, args.sender)
    imap.logout()

    # sort newest first
    msgs.sort(key=lambda x: x[0] or datetime.min, reverse=True)

    # build entries
    entries = []
    for dt, subject, html, msg_id in msgs:
        date_str = dt.strftime('%Y-%m-%d') if dt else 'unknown'
        subj_short = subject[:120]
        links = extract_links(html)
        lines = [f"## {date_str} - {subj_short}"]
        for href, text in links:
            lines.append(f"- [{text}]({href})")
        lines.append("")
        entry_text = "\n".join(lines)
        entries.append((msg_id, date_str, subj_short, entry_text))

    # load existing file
    existing = ""
    existing_ids = set()
    if os.path.exists(args.output):
        with open(args.output, 'r', encoding='utf-8') as f:
            existing = f.read()
        # simple dedupe by date+subject header
        for msg_id, date_str, subj_short, _ in entries:
            if msg_id and msg_id in existing:
                continue
            header = f"## {date_str} - {subj_short}"
            if header in existing:
                existing_ids.add(header)

    # filter new entries
    new_entries = []
    for msg_id, date_str, subj_short, entry_text in entries:
        header = f"## {date_str} - {subj_short}"
        if header in existing_ids or header in existing:
            continue
        new_entries.append(entry_text)

    # prepend new entries to existing file
    if new_entries:
        new_content = "\n".join(new_entries)
        combined = new_content + "\n" + existing if existing else new_content
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(combined)
        print(f"Added {len(new_entries)} new entries to {args.output}")
    else:
        print("No new entries")

if __name__ == "__main__":
    main()
