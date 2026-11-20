"""Subtitle otomatis via Whisper (faster-whisper, lokal, tanpa API key).

- Engine terdeteksi saat runtime: `faster_whisper` terpasang -> model
  lokal (default `tiny`, bahasa `id`); TIDAK terpasang -> raise
  SubtitleEngineUnavailable dengan pesan instalasi yang jelas.
- Model diunduh sekali dari Hugging Face saat pertama dipakai (butuh
  internet saat itu); setelahnya offline.
- Formatter SRT/VTT murni (tanpa engine) — bisa dites tanpa model.
- Model size di-whitelist (audit ronde 2, P1-3): model arbitrer bisa
  memicu unduhan model GB-an dari Hugging Face.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

# Model Whisper yang diizinkan (kecil; unduhan sekali, < 500 MB).
# "large-v3" dkk. sengaja ditolak — berat + unduhan GB-an per request.
ALLOWED_MODEL_SIZES = frozenset({"tiny", "base", "small"})


class SubtitleEngineUnavailable(Exception):
    pass


def engine_available() -> bool:
    try:
        import faster_whisper  # noqa: F401
        return True
    except ImportError:
        return False


def _fmt_ts(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    if ms == 1000:
        ms = 0
        s += 1
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def segments_to_srt(segments: list[dict]) -> str:
    """segments: [{start, end, text}] -> teks SRT."""
    out: list[str] = []
    for i, seg in enumerate(segments, start=1):
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        out.append(f"{i}\n{_fmt_ts(seg['start'])} --> {_fmt_ts(seg['end'])}\n{text}\n")
    return "\n".join(out)


def segments_to_vtt(segments: list[dict]) -> str:
    out = ["WEBVTT\n"]
    for seg in segments:
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        start = _fmt_ts(seg["start"]).replace(",", ".")
        end = _fmt_ts(seg["end"]).replace(",", ".")
        out.append(f"{start} --> {end}\n{text}\n")
    return "\n".join(out)


def _load_audio_array(audio_path: Path) -> "np.ndarray":
    """Decode file audio ke array float32 16 kHz mono — via ffmpeg CLI,
    BUKAN via faster-whisper.decode_audio (PyAV 19 yang terpasang
    menolak kwarg `metadata_errors` yang dipakai faster-whisper 1.2.1;
    pin av lama tidak punya wheel Python 3.14)."""
    import subprocess
    import wave

    import numpy as np

    tmp_wav = audio_path.with_suffix(".16k.wav")
    proc = subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(audio_path),
         "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(tmp_wav)],
        capture_output=True, text=True, timeout=600,
    )
    if proc.returncode != 0 or not tmp_wav.exists():
        raise RuntimeError(f"ffmpeg gagal decode audio: {proc.stderr.strip()[:300]}")
    try:
        with wave.open(str(tmp_wav), "rb") as w:
            n_frames = w.getnframes()
            raw = w.readframes(n_frames)
        audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    finally:
        tmp_wav.unlink(missing_ok=True)
    if audio.size == 0:
        raise RuntimeError("Audio kosong setelah decode (tidak ada sampel).")
    return audio


def transcribe_file(
    audio_path: str | Path,
    language: str = "id",
    model_size: str = "tiny",
    device: str = "cpu",
    compute_type: str = "int8",
) -> list[dict]:
    """Transkrip file audio/video lokal -> [{start, end, text}].
    Decode via ffmpeg (lihat _load_audio_array), model Whisper lokal.
    Audio dilewatkan sebagai numpy array supaya faster-whisper tidak
    memanggil decode_audio/PyAV."""
    if model_size not in ALLOWED_MODEL_SIZES:
        raise ValueError(
            f"model_size tidak diizinkan: {model_size!r}. "
            f"Diizinkan: {', '.join(sorted(ALLOWED_MODEL_SIZES))}"
        )
    if not engine_available():
        raise SubtitleEngineUnavailable(
            "faster-whisper belum terpasang di environment ini. "
            "Pasang dengan: pip install faster-whisper "
            "(model Whisper diunduh sekali dari Hugging Face saat pertama dipakai)."
        )
    from faster_whisper import WhisperModel

    path = Path(audio_path)
    if not path.exists():
        raise FileNotFoundError(f"File audio tidak ditemukan: {path}")
    audio = _load_audio_array(path)
    model = WhisperModel(model_size, device=device, compute_type=compute_type)
    segments_iter, _info = model.transcribe(audio, language=language)
    segments: list[dict] = []
    for seg in segments_iter:
        segments.append({
            "start": round(float(seg.start), 3),
            "end": round(float(seg.end), 3),
            "text": seg.text.strip(),
        })
    return segments


def write_subtitle_files(
    segments: list[dict], out_dir: str | Path, base_name: str
) -> dict[str, str]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    srt_path = out_dir / f"{base_name}.srt"
    vtt_path = out_dir / f"{base_name}.vtt"
    srt_path.write_text(segments_to_srt(segments), encoding="utf-8")
    vtt_path.write_text(segments_to_vtt(segments), encoding="utf-8")
    return {"srt_path": str(srt_path), "vtt_path": str(vtt_path)}
