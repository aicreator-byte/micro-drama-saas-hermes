#!/bin/bash
# Fix round 2 (frontend only) — Hermes leg. Log terpisah supaya tidak
# mengganggu deteksi DONE watchdog di build log.
cd /home/hatch/workspace/micro-drama-saas/hermes || exit 1
exec /home/hatch/workspace/hermes-agent/.venv/bin/hermes --provider nvidia -m nvidia/nemotron-3-ultra-550b-a55b -z "$(cat FIX2-PROMPT.md)" > logs/hermes-fix2.log 2>&1
echo "hermes-fix2 exit: $?" >> logs/hermes-fix2.log
