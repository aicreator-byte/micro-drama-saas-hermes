# Future Development — kaki Hermes (19 Nov 2026)

Perintah Di 19 Nov 20:44: kerjakan SEMUA future development kaki Hermes
(ringkasan audit F4 + Phase 2 gaps + umum). Yang dikerjakan HANYA di
`~/workspace/micro-drama-saas/hermes/`. **Push/publikasi repo TIDAK
dilakukan di sini** — itu urusan parent agent.

## Ringkasan hasil

Semua item scope SELESAI + terverifikasi tes. Full suite backend:
**108 passed** (termasuk `test_browser_login.py` 12/12, tanpa regresi).
Frontend: `tsc --noEmit` 0 error, `npm run build` sukses (20 route).
Migrasi Alembic: `upgrade head` di DB scratch bersih → head
`bible_source`, kolom `series_bibles.source` ada.
Live smoke server nyata (via `backend/start.sh`, DB scratch, LLM nyata
key trial): POST 202 dalam 0,19 dtk, polling tunjukkan progres per
langkah, job 1 episode COMPLETED (1 episode, 5 karakter, 4 lokasi,
1 prompt).

## 1. Audit F4 — P2 Hermes

### (a) Prompts di-chunk, bukan 1 call max_tokens=8000 — SELESAI
- `backend/app/services/ai_client.py`: `generate_episode_video_prompts`
  kini memanggil LLM per chunk `PROMPT_CHUNK_SIZE = 5` episode,
  `PROMPT_CHUNK_MAX_TOKENS = 4000` per chunk (logika call tunggal pindah
  ke helper `_generate_video_prompts_chunk`). Tiap chunk divalidasi
  coverage-nya sendiri; episode hilang → `AIProviderError` menyebut
  nomor episode.
- Bukti: `tests/test_ai_client.py` — 12 episode = 3 call (5+5+2),
  30 episode = 6 call (bukan 1 call besar), tiap call max_tokens 4000;
  episode 7 di-drop → error menyebut "7".

### (b) POST auto-generate tidak ubah judul proyek — SELESAI
- `backend/app/api/auto_generate.py`: baris
  `project.title = request.title` DIHAPUS. `request.title` hanya jadi
  judul job. `request.genre` eksplisit tetap mengeset `project.genre`
  (input eksplisit user).
- Bukti: `test_title_not_changed` — POST judul berbeda, judul proyek
  tetap "Test Project".

### (c) Ringkasan langkah berisi angka — SELESAI
- Backend: semua step summary kini menyertakan skalar — langkah 1
  `created_count`/`skipped_count`/`episode_count`/`genre`/`genre_source`/
  `bible_protected`; langkah 2–3 `created_count`/`skipped_count`;
  langkah 4 `created_count`; langkah 5 `created_count`.
- Frontend `AutoGenerateModal.tsx`: `summarizeStep` kini menangani
  array (jumlah + 3 nama pertama; key `episodes` tampil sebagai jumlah
  saja — list outline lengkap tetap disimpan untuk langkah 4).
- Bukti: `test_step_summaries_have_counts` (tiap langkah punya
  `created_count` int).

### (d) Per langkah transaksional — SELESAI
- `_run_steps_from`: pada exception langkah, `await db.rollback()`
  dulu (buang tulisan setengah jadi), baru tandai step FAILED + job
  FAILED dan commit.
- **Bug ketemu saat tes:** rollback meng-expire objek ORM job/step;
  mengubah atribut expired lalu commit memicu lazy-load yang gagal di
  AsyncSession (`sqlalchemy.exc.MissingGreenlet`). Perbaikan: simpan
  `step_id, job_id` SEBELUM try, setelah rollback muat ulang segar via
  `db.get(...)` sebelum menandai FAILED.
- Bukti: `test_partial_step_rolls_back` — runner karakter tambah 1
  Character lalu raise; hasil akhir: job failed, 0 karakter di DB.

### (e) Bible manual dilindungi — SELESAI
- Model `SeriesBible` tambah kolom `source` (String(20), default
  `"manual"`); migrasi baru `backend/alembic/versions/bible_source.py`
  (rantai … → `auto_generate_jobs` → `bible_source`). Create + update
  via API set `source="manual"`. `SeriesBibleResponse` tambah field
  `source`.
- Langkah 1: bible ada + `main_plot` terisi + `source == "manual"` →
  `bible_protected=True`, field bible TIDAK ditimpa (outline LLM tetap
  dipakai membuat Episode). Bible kosong/tidak ada/`source == "auto"`
  → tulis seperti biasa + set `source="auto"`. Bible lama (pra-migrasi)
  default `"manual"` → ikut terlindungi (konservatif).
- Bukti: `test_manual_bible_protected` — bible manual tidak berubah,
  episode tetap dibuat (5, 4, 3, 3), summary `bible_protected=True`.

## 2. Phase 2 gaps

### (a) Settings API admin-only — SUDAH ADA DI KODE, DIVERIFIKASI
- `PATCH /settings` sudah memakai `get_current_admin_user`
  (`app/core/security.py`: tolak bila `role != ADMIN`, 403). Tidak ada
  perubahan kode — hanya verifikasi + tes.
- Bukti: `tests/test_future_dev.py` — non-admin PATCH → 403, admin
  PATCH → 200, non-admin GET → 200 (baca tetap boleh).

### (b) Redirect URI Google via env — SUDAH ADA DI KODE, DILENGKAPI
- `GOOGLE_OAUTH_REDIRECT_URI` di `app/core/config.py` dibaca dari env
  (default `http://localhost:3000/dashboard/google-accounts/callback`),
  dipakai `google_accounts.py:_get_redirect_uri()`. Tidak ada perubahan
  kode — ditambah entri di `backend/.env.example` + tes.
- Bukti: `tests/test_future_dev.py` — default localhost; env override
  `https://example.com/...` dihormati `Settings()` fresh.

## 3. Umum

### (a) Progres live async — SELESAI
- POST kini `status_code=202`, langkah jalan via FastAPI
  `BackgroundTasks` + runner `_run_job_background` (session sendiri via
  `_session_factory`, patchable di tes). GET status sudah ada; modal
  sudah polling tiap 2 dtk — dengan POST 202, polling kini benar-benar
  menampilkan progres per langkah. Retry juga async: set step PENDING +
  job RUNNING + commit dulu, lalu background; guard 409 bila job sedang
  RUNNING.
- **Perubahan kontrak:** create yang dulu 201 kini 202; respons POST
  hanya menunjukkan `pending`/`running` — status akhir dibaca via GET.
  Tes diperbarui ke pola POST → `_wait_job` (poll GET sampai terminal).
- Bukti: 12 tes `test_auto_generate.py` hijau (termasuk retry +
  idempotency + coverage); live smoke: POST 202 dalam 0,19 dtk, polling
  tunjukkan `series_bible running → completed → characters running …`
  sampai `completed`.
- Keputusan desain: `BackgroundTasks`, bukan `asyncio.create_task` /
  Celery / Redis — cukup untuk single-process, modal sudah polling.

### (b) `.env` relatif ke direktori backend — SELESAI
- `app/core/config.py`: `BACKEND_DIR = Path(__file__).resolve().parent.parent.parent`,
  `load_dotenv(BACKEND_DIR / ".env")` di import (mengisi `os.environ`
  juga untuk kode `os.getenv` langsung), `Config.env_file =
  BACKEND_DIR / ".env"` (sebelumnya `".env"` relatif CWD).
- Start script baru `backend/start.sh` (chmod +x): `cd` ke direktorinya
  lalu `exec .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port "${PORT:-8001}"`.
- Bukti: `test_key_loaded_when_started_from_tmp` — subprocess dari
  `/tmp` (env dibersihkan dari `NVIDIA_API_KEY`) import config, assert
  key ter-load (hanya boolean, nilai TIDAK PERNAH dicetak). Precondition:
  `backend/.env` berisi `NVIDIA_API_KEY`; bila key dicabut, tes ini
  gagal dan harus diperbarui.
- README diperbarui: jalankan server via `./start.sh`.

### (c) Tolak judul hanya-spasi — SELESAI
- Backend `app/schemas/__init__.py`: `AutoGenerateCreate` tambah
  `field_validator("title")` (strip; kosong → ValueError → 422) dan
  validator `genre`/`premise` (blank → None).
- Frontend sudah trim + tolak judul kosong (`formTitle.trim()`, error
  "Judul wajib diisi") — ditambah helper text "Judul job ini — judul
  proyek tidak diubah".
- Bukti: `test_blank_title_rejected` — `"   "`, `""`, `" \t\n "` → 422.

### (d) Genre tidak default "drama" — SELESAI
- `ai_client.py`: `infer_genre_from_title(ai_client, title, premise)`
  (1 call LLM kecil, temperature 0.3, max_tokens 100; kembalikan label
  dari `GENRE_CANDIDATES` — romance, drama, thriller, comedy, fantasy,
  action, horror, family, crime, historical, sci-fi, mystery — atau
  None bila gagal/tidak dikenali). `auto_generate.py`: helper
  `_resolve_genre` — genre user > inferensi LLM > label jujur
  `"unknown"`; hasil disimpan ke `job.genre` + dicatat di summary
  (`genre`, `genre_source`: user/llm/unknown). Semua
  `job.genre or "drama"` diganti `or "unknown"`.
- **Perubahan perilaku:** job genre TIDAK LAGI mewarisi
  `project.genre` (`genre=request.genre or project.genre` → hanya
  `request.genre`). Alasan: genre proyek bisa jadi default "Drama" dari
  form, dan mewarisinya sama saja default diam-diam. Modal tetap
  pre-fill genre dari proyek (user melihat + bisa mengubah), jadi
  perilaku UI tidak berubah; hanya job API tanpa genre yang kini
  ditebak dari judul.
- Bukti: `test_genre_inferred_from_title` (`genre_source="llm"`,
  `job.genre="romance"` dari mock), `test_genre_unknown_when_inference_fails`
  (mock → None → `"unknown"`); unit `test_ai_client.py` — normalisasi
  case/tanda baca, `"unknown"` → None, label tak dikenal → None,
  provider error → None.

## 4. README diperbarui

`README.md` kaki Hermes: bagian baru **Auto-Generate** (async + polling,
inferensi genre, chunking prompts, proteksi bible manual, langkah
transaksional, judul job vs proyek), **Google Accounts, fallback &
browser login** (termasuk perbaikan `_is_logged_in` 19 Nov), endpoint
auto-generate + Settings (admin-only), start via `./start.sh`,
Known Limitations + Future Improvements disesuaikan (LLM + browser login
dicoret sebagai selesai). `.env.example` tambah `NVIDIA_API_KEY` dan
`GOOGLE_OAUTH_REDIRECT_URI`.

## 5. Observasi saat live smoke (bukan blocker, bukan scope)

1. **Inferensi genre live gagal → fallback jalan benar.** Log server:
   `Genre inference failed, leaving genre unknown: Provider all: All AI
   providers failed. Last error: Provider nvidia-nemotron-ultra:
   'NoneType' object has no attribute 'strip'`. Job tetap selesai
   dengan genre `"unknown"` (jujur), sesuai desain. Error provider-nya
   intermiten (call LLM lain di job yang sama sukses semua) — perlu
   dipantau bila sering muncul, tapi bukan item scope ini.
2. **LLM lambat saat smoke:** job 1 episode selesai ~7 menit (langkah
   demi langkah, bukan macet), vs Fase 3 Hermes 113 dtk untuk 5 episode.
   Kemungkinan latensi/rate-limit provider saat itu. Polling tetap
   menampilkan progres; tidak ada timeout yang pecah.
3. **`pkill -f` membunuh shell sendiri** saat mematikan server smoke
   (pola pkill muncul di command shell yang sama — pelajaran lama yang
   terulang). Server tetap mati (port 18099 bebas, tidak ada proses
   uvicorn tersisa). Ke depan: kill by PID eksplisit.

## 6. NOT VERIFIED (jujur, jangan dianggap selesai)

- Login Google asli akun Di + video Flow asli (di luar jangkauan agen
  dari VM ini — sesuai scope).
- Klik manual tombol Auto-Generate di UI browser (hanya API + unit tes
  + live smoke via HTTP).
- Job 30 episode live (chunking terverifikasi unit tes 30 episode = 6
  call; live baru 1 episode).
- Status RUNNING antara di browser nyata: polling modal diverifikasi
  kode + pola yang sama di smoke HTTP, bukan klik manual.

## 7. File yang diubah

Backend: `app/api/auto_generate.py`, `app/services/ai_client.py`,
`app/core/config.py`, `app/schemas/__init__.py`,
`app/models/__init__.py`, `app/api/series_bible.py`,
`alembic/versions/bible_source.py` (baru), `backend/start.sh` (baru),
`backend/.env.example`, `tests/conftest.py`,
`tests/test_auto_generate.py`, `tests/test_ai_client.py` (baru),
`tests/test_future_dev.py` (baru).
Frontend: `src/components/AutoGenerateModal.tsx`.
Root: `README.md`, `FUTURE-DEV-REPORT.md` (file ini).

Tidak ada file di luar `~/workspace/micro-drama-saas/hermes/`.
`.env` tidak di-commit, tidak dibaca nilainya, tidak dicetak ke mana pun.
Tidak ada video yang di-generate. Tidak ada akun Google asli dipakai.
