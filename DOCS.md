# Hermes Email Services - Documentation

## Overview
Hermes Gmail email services provide sending, searching, and queue processing for Gmail via SMTP/IMAP.

## Environment Assumptions
This setup assumes Linux/Ubuntu on the Hermes VM.

* Python 3.10+
* `git` installed
* Network access to smtp.gmail.com and imap.gmail.com

## Configuration

### Gmail App Password
Gmail requires an App Password for SMTP/IMAP access, not your regular password.

1. Enable 2-Step Verification on your Google account
2. Create an App Password: Google Account → Security → App passwords
3. Use the 16-character app password in config

### Environment Variables

Option A: Config file
Copy `templates/hermes-gmail-config.example.json` to `hermes-gmail-config.json` and edit.

Option B: Environment variables
Set these before running scripts:
* `GMAIL_USER` – Gmail address
* `GMAIL_APP_PASSWORD` – App password
* `GMAIL_SMTP_HOST` – default smtp.gmail.com
* `GMAIL_IMAP_HOST` – default imap.gmail.com

The scripts prefer config file over env vars.

### Linux / Ubuntu Setup

```bash
sudo apt update
sudo apt install python3 python3-pip git
python3 -m pip install --user yagmail
```

Clone repo:
```bash
cd /mnt/data/hermes/scripts
git clone https://github.com/enginpost/hermes-gmail-email-services.git email-services
cd email-services
cp templates/hermes-gmail-config.example.json hermes-gmail-config.json
# edit hermes-gmail-config.json
```

## Security Notes
* Never commit `hermes-gmail-config.json`
* Keep App Passwords secret
* Logs in `logs/` are ignored by git

## Queue Format
See `hermes-gmail-queue-writer` skill for email.md format.

## Cron Jobs
Example cron for unread check:
```cron
*/5 * * * * /usr/bin/python3 /mnt/data/hermes/scripts/email-services/check_unread_email.py
```

## Troubleshooting
* Authentication errors → check App Password and 2FA
* SSL errors → ensure port 465 and use_ssl true
* Queue not processing → validate JSON schema
