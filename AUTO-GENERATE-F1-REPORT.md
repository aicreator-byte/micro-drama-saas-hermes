# AUTO-GENERATE Fase 1 — Backend Report (kaki Hermes)

**Tanggal:** 19 Nov 2026. **Spek:** `~/workspace/micro-drama-saas/AUTO-GENERATE-SPEC.md` (Gate 1).
**Status:** SELESAI (backend saja — frontend TIDAK disentuh, kaki lain TIDAK disentuh, TIDAK push GitHub).

## Ringkasan

Satu job auto-generate (judul → bible + karakter + lokasi + episode + prompt video)
jalan berurutan, tiap langkah commit progres sendiri, gagal berhenti di langkah itu,
retry hanya langkah gagal, jalan ulang tidak duplikat. Pakai LLM client + Story Engine
yang sudah ada; key Nvidia dari env saja.

## Endpoint baru (`POST/GET` di bawah `/api/v1/projects/{project_id}`)

| Endpoint | Fungsi |
|---|---|
| `POST /auto-generate` (201) | Buat job + 5 langkah, jalankan berurutan sinkron, kembalikan job + status tiap langkah. Body: `title` (wajib), `genre`, `num_episodes` (default 30, 1–50), `premise` (default = judul). |
| `GET /auto-generate/{job_id}` | Status job + tiap langkah + pesan error. |
| `POST /auto-generate/{job_id}/retry/{step_key}` | Retry satu langkah FAILED, lalu lanjutkan langkah sesudahnya. Langkah COMPLETED/SKIPPED dipertahankan. Retry langkah non-gagal / step tidak dikenal → 400. |

## File yang diubah / dibuat

| File | Perubahan |
|---|---|
| `backend/app/models/__init__.py` | BARU: `AutoGenerateJob`, `AutoGenerateStep`, enum `AutoGenerateJobStatus` / `AutoGenerateStepStatus`, konstanta `AUTO_GENERATE_STEPS`. |
| `backend/app/services/ai_client.py` | BARU: `generate_characters` (5 karakter), `generate_locations` (4 lokasi), `generate_episode_video_prompts` (1 prompt/episode, 1 call LLM). Validasi JSON seperti `generate_series_outline`. |
| `backend/app/api/auto_generate.py` | BARU: router + 5 runner langkah + `_run_steps_from` + 3 endpoint. |
| `backend/app/schemas/__init__.py` | BARU: `AutoGenerateCreate`, `AutoGenerateJobResponse`, `AutoGenerateStepResponse`. |
| `backend/app/main.py` | Daftarkan router `auto_generate` di `/api/v1`. |
| `backend/alembic/versions/auto_generate_jobs.py` | BARU: migrasi `google_fallback_flow` → `auto_generate_jobs` (2 tabel + FK + unique `uq_job_step`). |
| `backend/tests/test_auto_generate.py` | BARU: 5 tes (mock LLM, tanpa network). |

## Cara tiap langkah bekerja (spek §4)

1. **Series Bible** — pakai `generate_series_outline` yang sudah ada (validasi `_validate_series_output` dipakai ulang). Tulis bible + episode (skip nomor yang sudah ada). Skip langkah bila bible + episode sudah ada.
2. **Characters** — BARU: `generate_characters` → tulis ke tabel `Character`. (Apply story engine lama tidak bisa materialisasi karakter — tidak dipakai.) Skip bila ≥4 karakter sudah ada. Default 5 karakter.
3. **Locations** — BARU: `generate_locations` → tulis ke tabel `Location`. Skip bila ≥3 lokasi sudah ada. Default 4 lokasi.
4. **Episodes** — materialisasi episode yang masih hilang dari outline step 1 (outline disimpan di `result_summary` step 1; bila step 1 di-skip, diambil dari job terdahulu). Skip nomor yang sudah ada.
5. **Prompts** — BARU: 1 call `generate_episode_video_prompts` untuk episode yang belum punya prompt `VIDEO_GENERATION`; validasi coverage dulu (episode tanpa prompt → langkah gagal, tanpa insert parsial). Minimal 1 prompt/episode. **Video TIDAK digenerate** (spec §8) — hanya prompt Flow/Veo.

Idempotensi: nama karakter/lokasi dicek case-insensitive; nomor episode di-skip; episode yang sudah punya prompt video di-skip. Jalan ulang job → langkah-langkah berstatus SKIPPED, jumlah baris tidak berubah (dites).

## §7 — perbaikan keanehan (backend)

1. **Akun demo "Test" (test@example.com):** TIDAK BERLAKU di kaki Hermes — tidak ada mekanisme seed di backend, docker, maupun frontend kaki ini (`test@example.com` hanya muncul di `tests/conftest.py` sebagai fixture tes). Akun demo yang Di lihat ada di kaki OpenCode, bukan di sini. Tidak ada yang diubah.
2. **Counter "Active Projects 0" vs badge "Active":** TIDAK ADA endpoint backend yang menghitungnya di kaki ini (grep `active.*project` di `app/` kosong) — counter murni frontend. Dicatat untuk Fase 2, bukan dikerjakan di Fase 1.

## Hasil pytest (angka persis)

- Baseline sebelum perubahan: **81 passed** (120,99 dtk).
- Setelah perubahan: **86 passed** (116,57 dtk) — **81 lama tetap lolos + 5 baru**:
  - `test_full_run_creates_everything` — 5 karakter + 4 lokasi + 3 episode + 3 prompt video, job completed.
  - `test_retry_failed_step` — langkah characters gagal → job failed, langkah sesudahnya pending; retry → completed, tanpa duplikat.
  - `test_rerun_is_idempotent` — run ke-2 semua langkah SKIPPED, jumlah baris tetap (5/4/3/3).
  - `test_prompt_coverage_validation` — prompt LLM tidak lengkap → langkah 5 gagal, 0 prompt tersimpan.
  - `test_auth_and_ownership` — 401 tanpa token, 404 proyek user lain, 400 retry langkah completed / step tidak dikenal, 404 job tidak ada.
- Migrasi Alembic: `upgrade head` + `downgrade -1` terverifikasi di SQLite sementara (kedua tabel dibuat, lalu dihapus bersih).

## Bug yang ketemu saat tes (diperbaiki)

Summary skip langkah 1 memakai key `"episodes"` berisi angka, sehingga `_outline_episodes` mengiranya list episode → `TypeError` di run ke-2. Perbaikan: key count diganti (`episode_count` / `character_count` / `location_count` / `prompt_count`) + guard `isinstance(eps, list)`. Setelah itu 5/5 tes lolos.

## NOT VERIFIED (di luar Fase 1 — untuk Fase 3)

- Generasi LLM nyata (semua tes pakai mock; tidak ada panggilan Nvidia NIM sungguhan).
- Smoke live di server berjalan (endpoint hanya dites via ASGI test client).
- Alur UI (frontend belum dibuat — Fase 2).

## Tidak dikerjakan (sesuai larangan)

Frontend, kaki Hermes/OpenCode/Claude lain, push GitHub, eksekusi video Flow/Veo,
perubahan auth/security, perubahan fallback akun Google, perubahan CRUD manual.
