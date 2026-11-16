#!/bin/bash
# Hermes leg — Micro Drama SaaS independent MVP build.
# Runs Hermes CLI one-shot (-z) with the challenge prompt, in its own workspace.
cd "$HOME/workspace/micro-drama-saas/hermes" || exit 1
# Primer langsung Nvidia (bukan cc-all): rantai cc-all gagal total 2x
# (cf 429 + jendela 24rb), sedangkan Nvidia 128K terverifikasi jalan.
"$HOME/workspace/hermes-agent/.venv/bin/hermes" --provider nvidia -m nvidia/nemotron-3-ultra-550b-a55b -z "$(cat ../PROMPT.md)" > logs/hermes-build.log 2>&1
echo "hermes exit: $?" >> logs/hermes-build.log
