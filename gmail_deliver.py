#!/usr/bin/env python3
"""Run check_unread_email.py, validate/fix HTML in each output block, print validated blocks."""

import subprocess
import os
import re
import requests
import html


# ── Telegram Bot API helpers ──────────────────────────────────────────────
def get_telegram_creds():
    """Return (bot_token, chat_id) or (None, None)."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip().strip("'\"")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip().strip("'\"")
    if token and chat_id:
        return token, chat_id
    return None, None


def send_telegram_block(token, chat_id, message, parse_mode="HTML"):
    """POST a single block to Telegram Bot API. Returns True on success."""
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": message[:4096],  # hard safety cap
            "parse_mode": parse_mode,
        }
        r = requests.post(url, json=data, timeout=15)
        return r.ok
    except Exception:
        return False


# ── Box-drawing Unicode range (U+2500–U+257F) ──────────────────────────── ────────────────────────────
def is_box_char(c):
    return '\u2500' <= c <= '\u257f'

def line_is_divider(line):
    """True if the line is mostly box-drawing / dash chars (a visual divider, not content)."""
    stripped = line.strip()
    if not stripped:
        return False
    # Strip HTML tags first to get just visible characters
    cleaned = re.sub(r'<[^>]+>', '', stripped)
    if not cleaned:
        return False
    box_and_dash = sum(1 for c in cleaned if is_box_char(c) or c == '-')
    return (box_and_dash / len(cleaned)) > 0.7


def balance_tags(text):
    """Ensure every opened HTML tag has a matching close tag at block end."""
    NON_CLOSING = {'br', 'hr', 'img', 'input', 'meta', 'link'}
    stack = []

    for match in re.finditer(r'<(/?)(\w+)', text):
        is_closing = bool(match.group(1))       # '/' present → closing tag
        tag = match.group(2).lower()            # tag name without slash

        if is_closing:
            if stack and stack[-1] == tag:
                stack.pop()                      # matched — pop it
        else:
            if tag not in NON_CLOSING:
                stack.append(tag)                # opening — push to stack

    # Close remaining unclosed tags (outermost first = bottom of stack)
    while stack:
        text += f'</{stack.pop()}>'

    return text


def escape_raw_ampersands(text):
    """Fix bare & that aren't already part of a known HTML entity."""
    return re.sub(r'&(?!amp;|lt;|gt;|quot;|nbsp;|#\d+;|#x[0-9a-fA-F]+;)', '&amp;', text)


def strip_tags_from_box_lines(text):
    """Remove HTML tags from lines dominated by box-drawing chars."""
    fixed = []
    for line in text.split('\n'):
        if line_is_divider(line):
            fixed.append(re.sub(r'<[^>]+>', '', line).strip())
        else:
            fixed.append(line)
    return '\n'.join(fixed)


def truncate_block(text, max_len=3800):
    """Guard against Telegram's 4096 char limit per message."""
    if len(text) <= max_len:
        return text
    trimmed = text[:max_len - 40].rstrip()
    trimmed = re.sub(r'<[^>]?$', '', trimmed)  # kill incomplete trailing tag
    trimmed += '\n<i>(truncated — more unread emails in inbox)</i>'
    return trimmed


def validate_block(block_text, block_num):
    """Validate and fix a single HTML block. Returns (fixed_text, list_of_issues)."""
    issues = []
    original = block_text

    # 1. Strip tags around box/divider lines — primary cause of silent parse failure
    fixed = strip_tags_from_box_lines(block_text)
    if fixed != original:
        issues.append("box-char dividers stripped")

    # 2. Escape any bare ampersands that slipped through
    fixed = escape_raw_ampersands(fixed)

    # 3. Balance unclosed HTML tags at end of block
    balanced = balance_tags(fixed)
    if balanced != fixed:
        extra = balanced[len(fixed):]
        issues.append(f"closed {extra.strip()}")
    fixed = balanced

    # 4. Length guard
    before_trim = len(fixed)
    fixed = truncate_block(fixed)
    if len(fixed) < before_trim:
        issues.append(f"truncated {before_trim}→{len(fixed)}")

    return fixed, issues


# ── Main execution ────────────────────────────────────────────────────────
def main():
    env_path = "/home/smcd/.hermes/profiles/default/gateway_email.env"
    env = dict(os.environ)

    if not env.get('GMAIL_APP_PASSWORD'):
        try:
            for line in open(env_path):
                if line.startswith("GMAIL_APP_PASSWORD="):
                    env['GMAIL_APP_PASSWORD'] = line.split("=", 1)[1].strip().strip("'\"")
                    break
        except FileNotFoundError:
            pass

    result = subprocess.run(
        ['python3', '/mnt/data/hermes/scripts/email-services/check_unread_email.py'],
        capture_output=True, text=True, timeout=120, env=env
    )

    raw = result.stdout.strip()

    if result.stderr:
        try:
            with open('/tmp/gmail_check_stderr.log', 'w') as f:
                f.write(result.stderr)
        except OSError:
            pass

    # Quiet or single-line output (no block delimiters)
    if not raw or '---BLOCK---' not in raw:
        print(raw.strip() if raw else "📭 Inbox is quiet — no new unread emails.")
        return

    blocks = [b.strip() for b in raw.split('---BLOCK---') if b.strip()]
    all_issues = []

    # Validate every block up-front
    validated = []
    for i, block in enumerate(blocks):
        fixed, issues = validate_block(block, i)
        if issues:
            all_issues.extend([f"Block {i}: " + iss for iss in issues])
        validated.append(fixed)

    # Try direct Telegram delivery (bypasses Hermes stdout bundling)
    token, chat_id = get_telegram_creds()
    if token and chat_id:
        sent_ok = 0
        for block_text in validated:
            if send_telegram_block(token, chat_id, block_text):
                sent_ok += 1
            # else silently skipped per user preference
        # Only log fixes to stderr; no stdout needed when Telegram worked
        if all_issues:
            import sys as _sys
            for iss in all_issues:
                print(f"[FIX] {iss}", file=_sys.stderr)
        return

    # ── Fallback: stdout with ---BLOCK--- (when Telegram creds unavailable) ──
    for i, block_text in enumerate(validated):
        print(block_text)
        if i < len(validated) - 1:
            print("---BLOCK---")

    if all_issues:
        import sys
        for iss in all_issues:
            print(f"[FIX] {iss}", file=sys.stderr)


if __name__ == '__main__':
    main()
