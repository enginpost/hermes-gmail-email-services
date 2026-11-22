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

