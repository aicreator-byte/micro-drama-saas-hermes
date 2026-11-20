"""Cek konsistensi karakter antar episode.

Dua lapis:
1. Rule-based (deterministik, tanpa LLM): varian ejaan nama karakter
   yang mirip tapi tidak sama, dan atribut yang bentrok antar episode
   (mis. umur/penampilan disebut berbeda).
2. LLM (opsional, via AIClient): baca bible + outline episode, laporkan
   inkonsistensi sifat/penampilan/relasi/kontinuitas sebagai JSON.

Fungsi murni `rule_based_issues` dan `parse_llm_issues` bisa dites
tanpa LLM sama sekali.
"""
from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from typing import Any, Optional

ISSUE_TYPES = (
    "name_variant", "appearance", "personality", "relationship",
    "continuity", "age", "other",
)
SEVERITIES = ("low", "medium", "high")


def _norm_name(name: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", name.lower()).strip()


def _similar(a: str, b: str) -> float:
    return SequenceMatcher(None, _norm_name(a), _norm_name(b)).ratio()


def rule_based_issues(characters: list[dict], episodes: list[dict]) -> list[dict]:
    """Cari varian nama + atribut bentrok dari data DB saja.

    characters: [{name, physical_appearance, personality, ...}]
    episodes: [{episode_number, title, outline}]
    """
    issues: list[dict] = []
    names = [c.get("name", "") for c in characters if c.get("name")]
    # 1) Nama karakter yang hampir sama tapi tidak identik -> kemungkinan
    #    typo/varian yang lolos di episode berbeda.
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if a != b and _similar(a, b) >= 0.80:
                issues.append({
                    "character": a,
                    "episode_number": None,
                    "type": "name_variant",
                    "severity": "medium",
                    "description": f"Nama karakter mirip tapi tidak sama: '{a}' vs '{b}' — kemungkinan varian ejaan yang sama.",
                    "suggestion": "Samakan ejaan nama di semua episode, pilih satu bentuk kanonis.",
                })
    # 2) Nama yang disebut di outline episode tapi tidak ada di daftar
    #    karakter (karakter hantu / typo nama di narasi).
    known = {_norm_name(n) for n in names}
    for ep in episodes:
        outline = ep.get("outline") or ""
        # Nama berkapital yang muncul setelah "Karakter:" / disebut berulang.
        # Semua nama hantu per episode dilaporkan (dulu: break setelah 1).
        reported: set[str] = set()
        for m in re.finditer(r"\b([A-Z][a-z]{2,}(?:\s[A-Z][a-z]{2,})?)\b", outline):
            cand = m.group(1)
            if _norm_name(cand) in known or cand in reported:
                continue
            # Hanya laporkan bila nama itu muncul >= 2x di episode yang sama
            if outline.count(cand) >= 2:
                reported.add(cand)
                issues.append({
                    "character": cand,
                    "episode_number": ep.get("episode_number"),
                    "type": "continuity",
                    "severity": "low",
                    "description": f"'{cand}' disebut {outline.count(cand)}x di episode {ep.get('episode_number')} tapi tidak ada di daftar karakter proyek.",
                    "suggestion": "Tambahkan sebagai karakter, atau perbaiki ejaan ke nama karakter yang sudah ada.",
                })
    return issues


def parse_llm_issues(raw: str) -> list[dict]:
    """Parse output LLM menjadi list issue tervalidasi. Output diharapkan
    JSON list; toleran terhadap fence ```json dan teks di sekitarnya."""
    if not raw or not raw.strip():
        return []
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    # Ambil blok [...] pertama bila ada teks pengantar.
    m = re.search(r"\[.*\]", text, flags=re.DOTALL)
    if m:
        text = m.group(0)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    out: list[dict] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        itype = str(item.get("type", "other"))
        if itype not in ISSUE_TYPES:
            itype = "other"
        sev = str(item.get("severity", "low"))
        if sev not in SEVERITIES:
            sev = "low"
        out.append({
            "character": str(item.get("character") or ""),
            "episode_number": item.get("episode_number"),
            "type": itype,
            "severity": sev,
            "description": str(item.get("description") or "")[:1000],
            "suggestion": str(item.get("suggestion") or "")[:1000],
        })
    return out


CONSISTENCY_PROMPT = """Kamu editor kontinuitas serial drama. Periksa konsistensi karakter
antar episode. Data karakter (nama, penampilan, sifat, latar) dan ringkasan
episode diberikan di bawah. Laporkan HANYA inkonsistensi nyata: perubahan
penampilan/sifat/usia/relasi tanpa penjelasan, karakter berperilaku
bertentangan dengan sifatnya, atau fakta yang bentrok antar episode.
Jangan laporkan perkembangan karakter yang wajar (mis. belajar dari
pengalaman). Jawab HANYA dengan JSON list, tiap item:
{{"character": "...", "episode_number": <int atau null>, "type": "appearance|personality|relationship|continuity|age|other", "severity": "low|medium|high", "description": "...", "suggestion": "..."}}.
Bila tidak ada masalah, jawab [].
"""


def build_consistency_prompt(characters: list[dict], episodes: list[dict]) -> str:
    lines = [CONSISTENCY_PROMPT, "\n## Karakter\n"]
    for c in characters:
        lines.append(
            f"- {c.get('name')}: peran={c.get('role') or '-'}, "
            f"penampilan={c.get('physical_appearance') or '-'}, "
            f"sifat={c.get('personality') or '-'}, latar={c.get('background') or '-'}"
        )
    lines.append("\n## Episode\n")
    for ep in episodes:
        lines.append(
            f"Episode {ep.get('episode_number')}: {ep.get('title') or ''}\n{ep.get('outline') or ''}"
        )
    return "\n".join(lines)


async def run_llm_check(ai_client, characters: list[dict], episodes: list[dict]) -> list[dict]:
    """Jalankan cek LLM; gagal provider -> list kosong (bukan exception),
    supaya hasil rule-based tetap tersimpan."""
    try:
        result = await ai_client.chat_completion(
            messages=[
                {"role": "system", "content": "Kamu editor kontinuitas serial drama. Jawab hanya JSON."},
                {"role": "user", "content": build_consistency_prompt(characters, episodes)},
            ],
            temperature=0.2,
            max_tokens=4000,
        )
    except Exception:
        return []
    content = result.get("content", "") if isinstance(result, dict) else ""
    return parse_llm_issues(content)


def merge_issues(*groups: list[dict]) -> list[dict]:
    """Gabung + dedup berdasarkan (character, episode, type, description)."""
    seen: set[tuple] = set()
    out: list[dict] = []
    for group in groups:
        for issue in group:
            key = (
                issue.get("character"), issue.get("episode_number"),
                issue.get("type"), issue.get("description"),
            )
            if key in seen:
                continue
            seen.add(key)
            out.append(issue)
    return out
