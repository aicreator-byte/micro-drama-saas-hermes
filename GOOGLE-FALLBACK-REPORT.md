# Google-Account Fallback — Flow Bridge (kaki Hermes)

Perintah Di 21:03 WIB 17 Nov 2026. Gap audit ronde 2: fallback LLM sudah jalan,
fallback akun Google belum ada. Scope: fungsionalitas saja, security ditunda.

## Temuan awal (terverifikasi dari kode)

- **Tidak ada eksekusi Flow otomatis** di kaki Hermes. `flow_bridge.py`
  hanya: task tracker (create/list/get/patch/delete) + `export-prompts`
  (paket prompt manual untuk Google Flow) + `import-results` (impor file
  hasil). Jadi fallback diterapkan di **pemilihan akun + retry task**,
  bukan di eksekusi video (yang belum ada).
- Task terikat ke satu `google_account_id` saat dibuat; tidak ada rotasi.
- Pola fallback LLM (`services/ai_client.py:chat_completion`): coba provider
  berurutan berdasar priority, pindah saat gagal, error jujur bila semua
  gagal. Pola ini ditiru untuk akun Google.
- Akun Google: `status` CONNECTED + `session_data` terenkripsi berisi
  `tokens.access_token / refresh_token`. Tidak ada field `enabled` —
  "enabled + token valid" diterjemahkan sebagai `status == CONNECTED` dan
  token bisa di-decrypt (cek lokal) lalu divalidasi ke Google (cek jaringan).

## Yang diubah

| File | Perubahan |
|---|---|
| `backend/app/services/google_account_fallback.py` | **Baru.** Service fallback (lihat Cara kerja). |
| `backend/app/api/flow_bridge.py` | Create: auto-pick akun usable bila `google_account_id` tidak diisi; `active_account_id` di-set. Endpoint baru `POST /flow/{project_id}/tasks/{task_id}/execute` dan `POST .../retry`. PATCH: ganti `google_account_id` harus milik user sendiri (ikut update `active_account_id`). |
| `backend/app/models/__init__.py` | `FlowTask` + `active_account_id` (FK `google_accounts`, SET NULL), `fallback_history` (JSON), `error_message` (Text). Relasi `active_account` (FK eksplisit, agar tidak bentrok dengan `google_account`). |
| `backend/app/schemas/__init__.py` | `FlowTaskResponse` + ketiga field baru; `FlowTaskUpdate.google_account_id`; `FlowTaskRetryRequest` baru (`google_account_id` opsional). |
| `backend/alembic/versions/google_fallback_flow.py` | **Baru.** Revisi `google_fallback_flow` ← `phase2_settings_oauth`; tambah 3 kolom di `flow_tasks` (+ FK `active_account_id` untuk non-SQLite). |
| `backend/tests/test_google_fallback.py` | **Baru.** 7 tes (lihat Verifikasi). |
| `GOOGLE-FALLBACK-REPORT.md` | File ini. |

Tidak disentuh: kaki lain, folder audit, OAuth login, enkripsi, rate limiting,
security headers, `SECRET_KEY`, endpoint lain.

## Cara kerja fallback

1. **Urutan kandidat** — `get_candidate_accounts(db, user_id, preferred_id)`:
   akun yang diminta dulu, lalu akun CONNECTED lain milik user yang sama
   (terlama dulu = urutan stabil, analog priority LLM). Akun user lain
   tidak pernah dicoba (diuji).
2. **Percobaan per akun** — `validate_account_token`: validasi `access_token`
   ke `https://oauth2.googleapis.com/tokeninfo`; bila 400 `invalid_token`
   dan ada `refresh_token`, coba refresh (`/token`); refresh sukses →
   token baru disimpan terenkripsi, akun dipakai. Tanpa kredensial OAuth
   di Settings, refresh mengembalikan gagal (bukan exception).
3. **Alasan yang memicu pindah akun** (account-specific):
   `quota_exceeded` (429 / teks "quota"), `rate_limited` (429),
   `token_invalid` (401/403/`invalid_token`/`invalid_grant`),
   `refresh_failed`, `no_token`. **Tidak memicu fallback** (langsung 502,
   tanpa coba akun lain): Google tidak terjangkau / HTTP 5xx — ganti akun
   tidak bisa memperbaikinya.
4. **Pencatatan** — setiap percobaan masuk `task.fallback_history`
   (append-only): `{account_id, email, result: failed|succeeded,
   reason, at}`. Akun yang berhasil → `active_account_id` dan
   `google_account_id` pindah ke akun itu, `error_message` dibersihkan,
   status task `generating` (akun siap — generasi video tetap via Flow,
   dilacak lewat export/import). Semua gagal → status `failed`,
   `error_message` berisi alasan per akun, endpoint kembalikan **502**
   dengan detail yang sama (error jujur, bukan diam-diam gagal).
5. **Create task** — tanpa `google_account_id`: auto-pick akun pertama
   yang lolos cek lokal (CONNECTED + token ter-decrypt). Tanpa akun usable:
   task tetap dibuat dengan `active_account_id = null`; `execute` akan
   kembalikan 502 jujur "No usable Google account".
6. **Retry manual** — `POST .../retry` (body opsional
   `{"google_account_id": ...}` untuk mulai dari akun tertentu). Hanya
   task `failed` (selain itu 409). Riwayat **ditambah**, tidak dihapus.
7. **Extension point** — `run_with_google_fallback(db, task, user_id,
   attempt, ...)` menerima fungsi `attempt(account)` apa pun; saat
   otomasi Flow nyata ada, ganti `validate_account_token` dengan call
   Flow per akun tanpa mengubah loop fallback.

## Verifikasi — pytest (nyata, bukan kutip)

Perintah (dari `backend/`):
`venv/bin/python -m pytest tests/test_google_fallback.py -q` →
**7 passed**. Lalu `venv/bin/python -m pytest -q` (lengkap) →
**70 passed in 63.79s** (63 lama + 7 baru, 0 gagal).

Tes baru memakai fake HTTP client Google (tokeninfo per access_token;
refresh tidak pernah sampai jaringan karena tanpa kredensial OAuth di DB tes):

- akun 1 invalid → pindah akun 2 → berhasil (`generating`,
  `active_account_id` = akun 2, riwayat failed+succeeded);
- semua akun gagal (429 quota + invalid) → 502, task `failed`,
  `error_message` menyebut kedua akun + alasan masing-masing;
- create tanpa akun → auto-pick akun CONNECTED pertama;
- tanpa akun CONNECTED → execute 502 "No usable Google account";
- retry setelah gagal → fallback jalan lagi, riwayat jadi 4 entri
  (tidak dihapus); retry task non-failed → 409;
- akun user lain tidak pernah dicoba.

Migrasi: `DATABASE_URL="sqlite+aiosqlite:////tmp/fb-mig.db" venv/bin/python
-m alembic upgrade head` → head `google_fallback_flow`, kolom
`active_account_id`/`fallback_history`/`error_message` ada di `flow_tasks`;
`downgrade -1` lalu `upgrade head` ulang juga berhasil. (Percobaan pertama
dengan `sqlite:///` gagal karena env Alembic butuh driver async — bukan
cacat migrasi; diulang dengan `sqlite+aiosqlite` dan lolos.)

## Verifikasi — smoke live (nyata)

Server: `DATABASE_URL="sqlite+aiosqlite:////tmp/fb-smoke.db"
SECRET_KEY="smoke-test-secret-key" venv/bin/python -m uvicorn
app.main:app --host 127.0.0.1 --port 8123` (DB segar, port bebas).
Skrip `/tmp/fb-smoke.py` (dihapus setelah selesai): register → login →
buat project → 2 akun Google via API (status `connected`, token palsu) →
buat task tanpa akun → auto-pick akun 1 → `execute` → `retry`.

Hasil aktual — **semua check lolos**:
- `health` 200; register/login/project/2 akun OK.
- Create task auto-pick akun 1 (`active_account_id` = akun 1).
- `execute` → **502** `All Google accounts failed — smoke1@gmail.com:
  refresh_failed; smoke2@gmail.com: refresh_failed` (token palsu →
  tokeninfo nyata ke Google menolak → refresh gagal karena tanpa kredensial
  OAuth di DB smoke; kedua akun benar-benar dicoba, sesuai harapan).
- GET task: `status: failed`, `fallback_history` 2 entri (kedua akun,
  `refresh_failed`), `error_message` menyebut kedua akun.
- `retry` → 502 lagi (token masih palsu), riwayat bertambah jadi 4 entri.
- Server dimatikan setelah selesai (PID dicek via `ss`, `curl /health`
  gagal sesudah kill, 0 proses uvicorn tersisa); DB/file smoke di `/tmp`
  dihapus.

**Yang TIDAK terverifikasi live:** jalur sukses end-to-end dengan token
Google asli (butuh akun + OAuth nyata — tidak dilakukan). Jalur sukses
tertutup oleh pytest dengan fake client (akun 1 gagal → akun 2 berhasil).

## Yang TIDAK dikerjakan + alasan

- **Otomasi eksekusi Flow** (kirim prompt ke Google Flow otomatis):
  belum ada di codebase; fallback diterapkan di level yang ada
  (pemilihan akun + execute/retry). Perlu keputusan Di / spek terpisah.
- **Security** (rate limiting, security headers, SECRET_KEY, enkripsi):
  ditunda atas perintah — tidak diubah apa pun.
- **OAuth login**: tidak diubah.
- **Frontend** (Settings / daftar task menampilkan akun aktif +
  riwayat fallback): tidak dikerjakan — task ini backend saja; field
  sudah ada di `FlowTaskResponse` sehingga frontend bisa membaca
  `active_account_id` / `fallback_history` / `error_message`.
- **Push GitHub**: tidak dilakukan (sesuai perintah).

## Catatan

- Working tree repo Hermes sudah berisi banyak perubahan uncommitted dari
  pekerjaan fase sebelumnya; pekerjaan ini hanya menyentuh file di tabel
  di atas.
- Satu insiden saat smoke: `pkill -f` dengan pola uvicorn sempat mematikan
  shell sendiri (pola muncul di command sendiri — gotcha yang sudah ada
  di AGENTS.md); server di-restart dengan PID eksplisit dan dimatikan
  dengan kill by PID.
