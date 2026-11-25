# written by hermes agent using muse-glimmer with medium effort
import imaplib
import os
import email
import re
import urllib.parse
import json
from datetime import datetime
from html.parser import HTMLParser

ENV_PATH = "/home/smcd/.hermes/profiles/default/gateway_email.env"
EMAIL = "mchoyt73@gmail.com"
CONFIG_PATH = "/mnt/data/hermes/scripts/email-services/newsletters.config.json"

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
    mids = []
    for mid in ids:
        mids.append(mid)
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
    return msgs, mids

def process_one(imap, cfg):
    sender = cfg['sender']
    output = cfg['output']
    label = cfg.get('label', 'Newsletter')
    msgs, mids = fetch_messages(imap, label, sender)
    # mark messages as read
    for mid in mids:
        try:
            imap.store(mid, '+FLAGS', '\\Seen')
        except:
            pass
    msgs.sort(key=lambda x: x[0] or datetime.min, reverse=True)
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
    existing = ""
    if os.path.exists(output):
        with open(output, 'r', encoding='utf-8') as f:
            existing = f.read()
    new_entries = []
    for msg_id, date_str, subj_short, entry_text in entries:
        header = f"## {date_str} - {subj_short}"
        if header in existing:
            continue
        new_entries.append(entry_text)
    if new_entries:
        new_content = "\n".join(new_entries)
        combined = new_content + "\n" + existing if existing else new_content
        with open(output, 'w', encoding='utf-8') as f:
            f.write(combined)
        print(f"[{cfg.get('name',sender)}] Added {len(new_entries)} new entries to {output}")
    else:
        print(f"[{cfg.get('name',sender)}] No new entries")

def main():
    with open(CONFIG_PATH) as f:
        configs = json.load(f)
    pwd = load_password()
    imap = imaplib.IMAP4_SSL("imap.gmail.com", 993)
    imap.login(EMAIL, pwd)
    for cfg in configs:
        try:
            process_one(imap, cfg)
        except Exception as e:
            print(f"Error processing {cfg.get('name','?')}: {e}")
    imap.logout()

if __name__ == "__main__":
    main()
