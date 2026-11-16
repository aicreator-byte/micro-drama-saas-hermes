#!/bin/bash
# Hermes leg — FIX round (perintah Di 16 Nov ~04:23 WIB).
# Log terpisah dari build log supaya watchdog tidak salah baca status DONE.
cd "$HOME/workspace/micro-drama-saas/hermes" || exit 1
"$HOME/workspace/hermes-agent/.venv/bin/hermes" --provider nvidia -m nvidia/nemotron-3-ultra-550b-a55b -z "$(cat FIX-PROMPT.md)" > logs/hermes-fix.log 2>&1
echo "hermes-fix exit: $?" >> logs/hermes-fix.log
