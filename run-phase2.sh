#!/bin/bash
# Hermes leg — Phase 2 (LLM nyata + OAuth Google nyata + Settings UI).
# Mirrors hermes/run.sh (Hermes CLI -z, Nvidia langsung) + audit run-chunk.sh
# (builder jalan di background, log ke logs/, watch yang memantau).
# Dipanggil phase2-watch.sh; JANGAN jalankan builder langsung dari sini tanpa watch.
cd "$HOME/workspace/micro-drama-saas/hermes" || exit 1
mkdir -p logs
# NVIDIA key via surrogate (pola sama seperti start-gateway.sh) — TANPA ini,
# CLI tidak punya kunci Nvidia, provider nvidia gagal, sesi jatuh ke cc-all
# (qwen2.5-coder-32b, context 32K) → context overflow tiap ~15 mnt.
# 413 (payload too large) TIDAK memicu fallback, jadi sesi mati.
_NV_KEY=$(python3 -c "
import sys
sys.path.insert(0, '/opt/muse/skills/custom-connector-setup/bin')
from dynamic_credentials import dynamic_credential_entry
try:
    print(dynamic_credential_entry('custom.nvidia')['surrogate'], end='')
except: pass
" 2>/dev/null)
[ -n "$_NV_KEY" ] && export NVIDIA_API_KEY="$_NV_KEY"
echo "phase2: launching"
setsid nohup "$HOME/workspace/hermes-agent/.venv/bin/hermes" --provider nvidia -m nvidia/nemotron-3-ultra-550b-a55b -z "$(cat PHASE2-PROMPT.md)" > logs/hermes-phase2.log 2>&1 < /dev/null &
echo "phase2: PID $!"
