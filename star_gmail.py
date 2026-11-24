#!/usr/bin/env python3
"""
star_gmail.py - Star a Gmail message via IMAP
Usage: python3 star_gmail.py --uid <uid> [--msgid <message-id>]
"""
import argparse
import os
import imaplib

GATEWAY_ENV = "/home/smcd/.hermes/profiles/default/gateway_email.env"
ALT_ENV = "/mnt/data/hermes/profiles/default/gateway_email.env"

def load_env():
    env_path = GATEWAY_ENV if os.path.exists(GATEWAY_ENV) else ALT_ENV
    env = {}
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if "=" in line:
                    k,v = line.strip().split("=",1)
                    env[k]=v
    return env

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--uid", required=False)
    parser.add_argument("--msgid", required=False)
    args = parser.parse_args()
    env = load_env()
    email = env.get("EMAIL","mchoyt73@gmail.com")
    pwd = env.get("GMAIL_APP_PASSWORD","")
    if not pwd:
        raise SystemExit("No app password")
    imap = imaplib.IMAP4_SSL("imap.gmail.com", 993)
    imap.login(email, pwd)
    imap.select("INBOX")
    uid = args.uid
    if args.msgid:
        typ, data = imap.uid('search', None, f'(HEADER Message-ID "{args.msgid}")')
        if typ == "OK" and data[0]:
            uids = data[0].split()
            uid = uids[0].decode()
    if not uid:
        raise SystemExit("UID required")
    imap.uid('store', uid, '+FLAGS', r'(\Flagged)')
    print(f"Starred UID {uid}")
    imap.logout()

if __name__ == "__main__":
    main()
