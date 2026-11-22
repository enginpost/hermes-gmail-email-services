# Hermes Email Services

Gmail queue and sending utilities for Hermes.

## Files

- `hermes_gmail.py` – Send/search Gmail via SMTP/IMAP
- `hermes_gmail_queue_processor.py` – Process queued email.md files
- `templates/hermes-gmail-config.example.json` – Config template
- `logs/` – Runtime logs, ignored by git

## Setup

1. Copy config template:
   ```bash
   cp templates/hermes-gmail-config.example.json hermes-gmail-config.json
   ```
   Edit `hermes-gmail-config.json` with your Gmail address and aliases.

2. The real config must live next to the scripts at:
   `/mnt/data/hermes/scripts/email-services/hermes-gmail-config.json`

3. Do NOT commit the real `hermes-gmail-config.json` — it is ignored by `.gitignore`.

## Config Template Notes

Copy `templates/hermes-gmail-config.example.json` to `hermes-gmail-config.json` in this folder and fill in your Gmail address and aliases.

Do NOT commit the real `hermes-gmail-config.json` — it is ignored by .gitignore.

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
