#!/usr/bin/env python3
"""
Hermes Gmail Queue Processor
Reads mail-queue/*.md files containing a JSON codeblock with email spec,
calls hermes_gmail.py send to dispatch the email, and moves processed files
to success/ or failure/ with timestamped filenames.
"""
import os
import re
import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

BASE_DIR = Path('/mnt/data/obsidian/second_brain/hermes-gmail')
MAIL_QUEUE_DIR = BASE_DIR / 'mail-queue'
SUCCESS_DIR = MAIL_QUEUE_DIR / 'success'
FAILURE_DIR = MAIL_QUEUE_DIR / 'failure'
GMAIL_SCRIPT = '/mnt/data/hermes/scripts/email-services/hermes_gmail.py'

os.makedirs(SUCCESS_DIR, exist_ok=True)
os.makedirs(FAILURE_DIR, exist_ok=True)

def extract_json_from_markdown(md_text):
    # Find first ```json ... ``` block
    m = re.search(r'```json\s+(.*?)\s+```', md_text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None

def send_email_via_script(to, subject, body, from_addr):
    # Build command to call hermes_gmail.py send
    # Use list to avoid shell quoting issues; body may contain newlines
    cmd = [
        'python3', GMAIL_SCRIPT, 'send',
        '--to', to,
        '--subject', subject,
        '--body', body,
        '--from', from_addr
    ]
    # Run with env var for password
    env = os.environ.copy()
    env['GMAIL_APP_PASSWORD'] = 'pjcvyoetxvzecgpu'  # TODO: load from config
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    return result.returncode == 0, result.stdout + result.stderr

def process_file(file_path):
    text = file_path.read_text(encoding='utf-8')
    data = extract_json_from_markdown(text)
    if not data:
        return False, 'No JSON found'
    to = data.get('to')
    subject = data.get('subject')
    body = data.get('body')
    from_addr = data.get('from')
    if not to or not subject or not body or not from_addr:
        return False, 'Missing fields'
    success, output = send_email_via_script(to, subject, body, from_addr)
    return success, output

def timestamped_name(original_name):
    ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    stem, ext = os.path.splitext(original_name)
    return f"{stem}_{ts}{ext}"

def process_queue():
    # Walk mail-queue recursively, process .md files only
    processed = 0
    for root, dirs, files in os.walk(MAIL_QUEUE_DIR):
        # Skip success/failure dirs
        if Path(root).name in ('success', 'failure'):
            continue
        for fname in files:
            if not fname.lower().endswith('.md'):
                continue
            file_path = Path(root) / fname
            # Avoid re-processing files already in subdirs
            success, msg = process_file(file_path)
            ts_name = timestamped_name(fname)
            if success:
                dest = SUCCESS_DIR / ts_name
                shutil.move(str(file_path), str(dest))
                print(f"[SUCCESS] {file_path} -> {dest}")
            else:
                dest = FAILURE_DIR / ts_name
                shutil.move(str(file_path), str(dest))
                print(f"[FAIL] {file_path} -> {dest} | {msg[:200]}")
            processed += 1
    print(f"Processed {processed} files")

if __name__ == '__main__':
    process_queue()
