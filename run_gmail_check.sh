#!/bin/bash
# Thin wrapper: set up GMAIL_APP_PASSWORD env then hand off to gmail_deliver.py
source ~/.profile 2>/dev/null
if [ -z "$GMAIL_APP_PASSWORD" ]; then
    for line in /home/smcd/.hermes/profiles/default/gateway_email.env; do
        if echo "$line" | grep -q "^GMAIL_APP_PASSWORD="; then
            export GMAIL_APP_PASSWORD=$(echo "$line" | sed 's/^GMAIL_APP_PASSWORD=//; s/^[[:space:]]*//; s/[[:space:]]*$//; s/^[\x27"][^"]*[\x27"]//')
            break
        fi
    done < /home/smcd/.hermes/profiles/default/gateway_email.env
fi

exec python3 "/mnt/data/hermes/scripts/email-services/gmail_deliver.py"
