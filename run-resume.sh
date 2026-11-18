#!/bin/bash
# Hermes leg — RESUME run (dipakai watchdog saat sesi sebelumnya mati).
cd "$HOME/workspace/micro-drama-saas/hermes" || exit 1
PROMPT="$(cat ../RESUME.md; echo; cat ../PROMPT.md)"
"$HOME/workspace/hermes-agent/.venv/bin/hermes" --provider nvidia -m nvidia/nemotron-3-ultra-550b-a55b -z "$PROMPT" >> logs/hermes-build.log 2>&1
echo "hermes-resume exit: $?" >> logs/hermes-build.log
