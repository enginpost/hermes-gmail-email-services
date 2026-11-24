# Hermes Email Services

Gmail queue and sending utilities for Hermes.

## Quick Start

See [DOCS.md](DOCS.md) for full setup, environment variables, Linux/Ubuntu instructions, and security notes.

## Files

- `hermes_gmail.py` – Send/search Gmail via SMTP/IMAP
- `hermes_gmail_queue_processor.py` – Process queued email.md files
- `templates/hermes-gmail-config.example.json` – Config template
- `logs/` – Runtime logs, ignored by git
- `DOCS.md` – Detailed setup and configuration guide
- `email-services/` – Unread monitoring, classification, and search
  - `check_unread_email.py` – Hourly scan, config-driven categorization, label creation, `--since-hours`
  - `search_gmail.py` – IMAP search by label/status/date with JSON output and Gmail links via rfc822msgid
  - `star_gmail.py` – Star messages via IMAP UID STORE +FLAGS \\Flagged
  - `email-categories-config.json` – Category/label/keyword definitions
  - `run_gmail_check.sh` – Wrapper for cron job

## Setup

1. Copy config template:
   ```bash
   cp templates/hermes-gmail-config.example.json hermes-gmail-config.json
   ```
   Edit `hermes-gmail-config.json` with your Gmail address and aliases.

2. The real config must live next to the scripts at:
   `/mnt/data/hermes/scripts/email-services/hermes-gmail-config.json`

3. Do NOT commit the real `hermes-gmail-config.json` — it is ignored by `.gitignore`.

For Gmail App Password setup and environment variable options, see [DOCS.md](DOCS.md).

## Usage

Send email:
```bash
python3 hermes_gmail.py send --to recipient@example.com --subject "Subject" --body "Body" --from sender@example.com
```

Process queue:
```bash
python3 hermes_gmail_queue_processor.py
```

Queue files go in `/mnt/data/obsidian/second_brain/hermes-gmail/mail-queue/`.

## Gmail Unread Monitoring & Search

**Cron**
- `Gmail Unread Check` id `9b11fb9045b1` runs hourly `0 * * * *` via `run_gmail_check.sh` → `check_unread_email.py`
- Config-driven categories in `email-categories-config.json`
- Labels created via IMAP `imap.create`, categorization via keywords, skip already labeled

**On-demand search**
```bash
python3 search_gmail.py --labels Career --status unread --since-hours 168 --limit 200
```
Validates labels against config, uses UID SEARCH/FETCH, returns JSON with uid/subject/sender/date/labels/gmail_link built from Message-ID `rfc822msgid:`.

**Read/Summarize/Stash**
Skill `gmail-read` provides:
- Read email N → accessible description, marks as read, offers to star
- Summarize email N → concise summary + CTAs/links
- Stash email N → writes to `/mnt/data/obsidian/second_brain/hermes-gmail/Email Stash/<Label>/<Subject>/<YYYY-MM-DD>.md`

**Star**
```bash
python3 star_gmail.py --uid <uid>
python3 star_gmail.py --msgid "<Message-ID>"
```


