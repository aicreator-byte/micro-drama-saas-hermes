# FIX-REPORT — Pasca-Audit 3-Arah Ronde 2 (Kaki Hermes)

**Tanggal:** 17 November 2026
**Cakupan:** hanya `~/workspace/micro-drama-saas/hermes/` (kaki lain tidak disentuh)
**Bahan audit:** `../audit-3way-round2/SUMMARY.md` + Action Plan P0/P1 Hermes di
PART-9-10-11 ketiga laporan (`audit-3way-round2-{hermes,opencode,claude}/AUDIT-REPORT.md`)
**Perintah:** fungsional P0/P1 saja; security DITUNDA per perintah Di (lihat § "Tidak diperbaiki").

> Laporan ini menggantikan FIX-REPORT ronde perbaikan sebelumnya di file yang sama.

---

## 1. Yang diperbaiki

### 1. Batas 6 karakter dihapus (F-H1, P0-08)
- `backend/app/api/characters.py` — blok `if count >= 6: raise 400` dihapus.
  Keputusan Di 17 Nov: maks 6 TIDAK ditegakkan.
- `frontend/src/app/dashboard/characters/page.tsx` — `disabled={characters.length >= 6}`,
  banner "Maximum of 6 characters reached", dan subtitle "up to 6 characters" dihapus.
- Tes baru: karakter ke-7 dan ke-10 → 201.

### 2. `POST /prompts/generate` selalu 422 (F-H2, P0-09)
- `backend/app/api/prompts.py` — route `POST /generate` dipindah ke ATAS `POST /{project_id}`
  (sebelumnya "generate" ditelan sebagai `project_id` → 422 `uuid_parsing`).
- Bonus (F-M5): template `.format()` diganti `_safe_format()` — context yang tidak lengkap
  tidak lagi KeyError → 500; placeholder yang hilang dibiarkan utuh di teks.

### 3. `Asset.metadata` 500 (F-H4, P0-09)
- Skema `AssetCreate`/`AssetResponse` (`backend/app/schemas/__init__.py`): field `metadata`
  diganti `asset_metadata` (nama yang sama dengan kolom model; `metadata` bentrok dengan
  objek SQLAlchemy `MetaData`).
- `backend/app/api/assets.py`: `metadata=...` → `asset_metadata=...` (upload + assemble +
  add-subtitles); metadata upload yang tadinya hilang diam-diam (kolom NULL) kini tersimpan.
- `backend/app/api/flow_bridge.py`: export-prompts memakai `a.asset_metadata`;
  import-results memakai `asset_metadata=...`.
- `frontend/src/types/index.ts`: `Asset.metadata` → `Asset.asset_metadata`.
- Bonus (F-L2): upload kini menolak ekstensi di luar allowlist per `asset_type`
  (image/video/audio/subtitle/document) dan metadata JSON tidak valid → 400 (bukan 500).

### 4. Duplikat OAuth `/settings/google/*` rusak (F-H5, P0-17)
- Seluruh endpoint duplikat di `backend/app/api/settings.py` DIHAPUS
  (`/google/auth-url`, `/google/callback`, `/google/{id}/refresh`,
  `/google/{id}/password`, `/google/{id}/password/check`).
  Satu-satunya jalur OAuth adalah `backend/app/api/google_accounts.py`.
  Frontend tidak memanggil jalur settings itu (grep: tidak ada pemakaian).
- `backend/app/api/google_accounts.py`:
  - Semua pemanggilan Google memakai `_google_client()` = konfigurasi httpx yang sama
    dengan `ai_client._get_client_config()` (`trust_env=False` + proxy/CA eksplisit) — F-H6.
    Error transport → 502 dengan pesan jelas, bukan 500.
  - `sync` diperbaiki: semua HTTP kini di dalam satu `async with` (sebelumnya `client.post`
    refresh dipanggil SETELAH context manager ditutup) + helper `_refresh()` bersama.
  - Auth-url memakai `urllib.parse.urlencode` (scope/redirect_uri sebelumnya mentah).
  - `session_data` terdekripsi TIDAK PERNAH lagi dimasukkan ke respons (P0-07):
    blok dekripsi-untuk-respons di list/get/update/sync dihapus. Skema
    `GoogleAccountResponse` memang tidak punya field itu.
  - Redirect URI konfigurabel via env `GOOGLE_OAUTH_REDIRECT_URI`
    (default `http://localhost:3000/dashboard/google-accounts/callback`) — P1-12.
    Ditambah ke `backend/app/core/config.py`.
- OAuth dari UI (F-H7, P0-17):
  - `frontend/src/app/dashboard/google-accounts/page.tsx`: tombol "Connect via Google"
    per akun → `getGoogleAuthUrl` → redirect ke Google (account id disimpan di
    `sessionStorage` untuk callback).
  - Baru: `frontend/src/app/dashboard/google-accounts/callback/page.tsx` — membaca
    `code`/`state` dari URL, memanggil `POST /google-accounts/callback`, tampilkan
    sukses/gagal + tautan kembali. `useSearchParams` dibungkus `<Suspense>` sesuai
    docs Next.js 16.4.6 (tanpa itu build gagal).

### 5. Admin gate Settings (F-C2, P0-06)
- `backend/app/api/settings.py`: `PATCH /settings` kini memakai `get_current_admin_user`
  (user biasa → 403 "Admin access required"). GET tetap terbuka (hanya flag, tanpa secret).
- `backend/app/core/security.py`: dependency baru `get_current_admin_user`
  (cek `role == UserRole.ADMIN`).
- `backend/app/api/settings.py`: `api_key_env` di-whitelist
  (`AI_API_KEY`, `NVIDIA_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`,
  `GOOGLE_API_KEY`, `GEMINI_API_KEY`, `DEEPINFRA_API_KEY`, `GROQ_API_KEY`,
  `OPENROUTER_API_KEY`); nilai lain (mis. `SECRET_KEY`) → 400. Sebelumnya nama env var
  sembarang dibaca lalu dikirim sebagai Bearer ke `base_url` provider (jalur eksfiltrasi).
- Bootstrap admin: `backend/app/api/auth.py` — user PERTAMA yang register menjadi ADMIN,
  agar endpoint Settings tetap terjangkau tanpa edit DB manual (tidak ada mekanisme
  seed/promosi admin sebelumnya).
- `ProviderConfig` (`backend/app/schemas/__init__.py` + `frontend/src/types/index.ts` +
  `frontend/src/app/dashboard/settings/page.tsx`): field opsional baru `id`, `provider`,
  `base_url`, `priority` — provider non-Nvidia kini bisa disimpan lewat Settings dan
  dipertahankan PATCH → GET (sebelumnya field tak dikenal hilang). Form Settings
  mendapat input Base URL; pesan error backend (403/400) kini ditampilkan, bukan
  "Failed to save settings" generik.

### 6. Snapshot sebelum regenerasi (F-M2, P0/P1-05)
- `backend/app/api/story_engine.py`:
  - Helper `_snapshot_episode()` — sebelum regenerasi, outline + semua scene (+ karakter
    scene + dialogue) episode lama ditulis ke `EpisodeRevision` (nomor revisi naik).
  - `generate-series`: output LLM divalidasi per item (`_validate_series_output`:
    nomor episode unik/numerik, title + outline wajib) SEBELUM data lama disentuh;
    output tidak valid → 502, data lama utuh.
  - `breakdown-episode`: output divalidasi (`_validate_breakdown_output`) sebelum hapus;
    `location_id`/`character_id` tidak valid atau bukan milik proyek dibuang (jadi
    `None`/dilewati) alih-alih `UUID(...)` → 500; akses dict memakai `.get()`.
  - Prompt series kini menyertakan karakter + lokasi proyek (sebelumnya diabaikan total).
- `backend/app/services/ai_client.py`: `generate_series_outline()` menerima
  `characters`/`locations` opsional; `_strip_json_fence()` membersihkan pagar
  ```` ```json ```` sebelum `json.loads` (series + breakdown) — H-P1-01.

### 7. Generate-all scene prompts selalu 500 (F-H3, P0-09)
- `backend/app/api/prompts.py`: `SceneCharacter` + `Dialogue` dipindah ke import atas
  (sebelumnya `Dialogue` diimpor di baris terakhir file, `SceneCharacter` tidak diimpor
  sama sekali → `NameError` di `prompts.py:302`). Import bawah file dihapus.

### 8. Item fungsional P0/P1 lain
- **Password Google via body saja (F-M1):** `POST /google-accounts/{id}/password` dan
  `.../password/verify` kini menerima JSON body (`GoogleAccountPasswordUpdate`); varian
  query-string dihapus (password di URL masuk log server/proxy/riwayat browser).
  `frontend/src/lib/api.ts` diubah ke body JSON.
- **Premise Generate Series (F-M3, P1-11):** `StoryGenerationRequest.premise` kini
  `min_length=1` (premise kosong → 422); `frontend/src/app/dashboard/episodes/page.tsx`
  mendapat modal Generate Series (premise wajib + genre + jumlah episode + tone) —
  tombol lama mengirim `premise: ''`.
- **Kontrak import-results (claude P1-7):** `POST /flow/{id}/import-results` kini menerima
  JSON body `{task_id, output_files}` (sesuai yang dikirim frontend; sebelumnya
  mendeklarasikan query param → 422) dan menolak file yang tidak ada di disk → 400 (F-M7).
- **Session DB di-rollback saat exception (H-P1-04/M-01):** `get_db()` di
  `backend/app/db/session.py` rollback sebelum raise, agar satu request 500 tidak
  meracuni request berikutnya di keep-alive yang sama.
- **UUID tidak valid → 400 (P1-09):** handler `ValueError` → 400 di `backend/app/main.py`.
- **DEBUG default False (F-M6, P1-03):** `backend/app/core/config.py` (`DEBUG: bool = False`).
  Catatan: `.env` lokal masih bisa meng-override.
- **Link mati dihapus (H-P1-03):** tombol view `/dashboard/episodes/{id}` dan
  `/dashboard/scenes/{episode}/{scene}` dihapus (tidak ada halaman detailnya);
  direktori kosong `frontend/src/app/projects/` dan `frontend/src/app/settings/` dihapus.

---

## 2. File yang diubah

**Backend** (baru: `backend/tests/test_fix_round2.py` — 23 tes regresi):
- `backend/app/api/characters.py`, `prompts.py`, `assets.py`, `flow_bridge.py`,
  `google_accounts.py`, `settings.py`, `story_engine.py`, `auth.py`
- `backend/app/core/config.py`, `backend/app/core/security.py`
- `backend/app/db/session.py`, `backend/app/main.py`
- `backend/app/schemas/__init__.py`, `backend/app/services/ai_client.py`
- `backend/tests/test_fix_round2.py` (baru)

**Frontend** (baru: `frontend/src/app/dashboard/google-accounts/callback/page.tsx`):
- `frontend/src/app/dashboard/characters/page.tsx`,
  `frontend/src/app/dashboard/episodes/page.tsx`,
  `frontend/src/app/dashboard/google-accounts/page.tsx`,
  `frontend/src/app/dashboard/scenes/page.tsx`,
  `frontend/src/app/dashboard/settings/page.tsx`
- `frontend/src/lib/api.ts`, `frontend/src/types/index.ts`
- Dihapus: `frontend/src/app/projects/`, `frontend/src/app/settings/` (direktori kosong)

Tidak ada file di kaki `opencode`/`claude` atau folder audit yang disentuh.
Tidak ada push ke GitHub. Tidak ada data dikirim ke layanan luar.

---

## 3. Hasil tes ulang (aktual, bukan kutipan laporan)

### 3.1 Pytest — 63/63 lolos
Perintah: `cd backend && ./venv/bin/python -m pytest tests/ -q`
Hasil: `63 passed in 68.76s` — 40 tes lama + 23 tes baru di `tests/test_fix_round2.py`:
karakter ke-7/ke-10 → 201; `/prompts/generate` → 200 (+ context tak lengkap tidak 500);
generate-all → 200; upload aset metadata round-trip + list/get 200; ekstensi ditolak 400;
metadata JSON rusak 400; PATCH /settings user biasa → 403, admin → 200,
`api_key_env=SECRET_KEY` → 400; user pertama register → ADMIN; duplikat
`/settings/google/*` → 404; auth-url tanpa kredensial → 400 (bukan 500); respons akun
Google tanpa `session_data`; password via body 200 + verify benar, via query 422;
snapshot revisi sebelum regenerasi (outline + scene lama tersimpan di `EpisodeRevision`);
output LLM tidak valid → 502 dan episode lama utuh; premise kosong → 422;
import-results body JSON (file ada → 200, file hilang → 400).

### 3.2 Frontend build — exit 0
Perintah: `cd frontend && rm -rf .next && npm run build`
Hasil: `Compiled successfully`, 18 rute (17 halaman + `/_not-found`), termasuk rute baru
`/dashboard/google-accounts/callback`. Next.js 16.4.6 (Turbopack).
Catatan: klaim lama "19 halaman" tidak direproduksi persis — build ini menghasilkan
18 rute; selisihnya adalah cara hitung (halaman `_not-found` ikut terdaftar).

### 3.3 Smoke live — 26/26 checks lolos
Server: `uvicorn app.main:app` port **8101**, SQLite segar (`/tmp/smoke8101.db`),
`SECRET_KEY` khusus smoke, `GOOGLE_OAUTH_REDIRECT_URI` eksplisit. Server dimatikan
lagi setelah tes; file upload smoke di `uploads/` dihapus.

| # | Cek | Hasil |
|---|---|---|
| 1 | register | 201 |
| 2 | login | 200 |
| 3 | create project | 201 |
| 4 | karakter 1–7 | [201 ×7] |
| 5 | POST /prompts/generate | 200 ("A detailed character portrait of Nadia, tall…") |
| 6 | asset upload | 201 |
| 7 | asset_metadata tersimpan | `{"shot": 1}` |
| 8 | GET /assets/{id} | 200 |
| 9 | GET /assets list | 200, total=1 |
| 10 | POST /flow export-prompts | 200 |
| 11 | create google account | 201 |
| 12 | google-accounts auth-url (tanpa creds) | 400 "Google OAuth credentials not configured in settings" |
| 13 | GET google-accounts tanpa session_data | true |
| 14 | duplikat /settings/google/auth-url | 404 |
| 15 | duplikat /settings/google/callback | 404 |
| 16 | PATCH /settings user biasa | 403 "Admin access required" |
| 17 | PATCH /settings admin | 200 (provider Nvidia tersimpan) |
| 18 | PATCH /settings api_key_env SECRET_KEY | 400 "api_key_env 'SECRET_KEY' is not allowed" |
| 19 | create episode | 201 |
| 20 | create scene | 201 |
| 21 | generate-all scene prompts | 200 (scene_image + video_generation) |
| 22 | set google password (body) | 200 |
| 23 | generate-series premise kosong | 422 |
| 24 | create flow task | 201 |
| 25 | import-results file hilang | 400 "Output file(s) not found on disk" |
| 26 | isolasi tenant (user lain GET project) | 404 |

Tambahan (tanpa API key): `POST /story-engine/{id}/generate-series` dengan premise valid
→ **502** jujur ("API key not configured (env var: NVIDIA_API_KEY)"), dan episode lama
tetap ada (total=1 setelah generate gagal) — regenerasi yang gagal tidak menghapus data.

---

## 4. Yang TIDAK diperbaiki + alasan

### 4.1 Security — DITUNDA per perintah Di (dicatat, tidak dikerjakan)
- Rate limiting (login/register, endpoint AI) — tidak ada limiter ditambahkan.
- Revokasi token / refresh token / logout server-side — JWT tetap 30 hari, tanpa `jti`/deny-list.
- `SECRET_KEY` default di `config.py` — tidak diubah, tidak dirotasi; gagal-start bila
  default TIDAK diimplementasikan.
- Enkripsi: salt PBKDF2 tetap statis, kunci enkripsi tetap turunan SECRET_KEY.
- Token tetap di `localStorage` (frontend `api.ts` + zustand persist) — tidak dipindah
  ke cookie httpOnly.
- Security headers (CSP/HSTS/X-Frame-Options/dll), CSRF, audit log — tidak ditambahkan.
- Verifikasi email / gate `is_verified` — tidak diaktifkan.
- Semua item di atas tetap menjadi blocker P0 menuju komersial (sesuai SUMMARY §7–§8).

### 4.2 Fungsional yang sengaja tidak dikerjakan (di luar P0/P1 / butuh keputusan Di)
- **Google OAuth end-to-end — NOT VERIFIED.** Butuh `client_id`/`client_secret` asli Di.
  Yang terverifikasi: auth-url 400-jujur tanpa kredensial, callback state salah → 400
  (jalur kode), halaman callback + tombol Connect ada. Login Google sungguhan belum diuji.
- **Generasi LLM nyata — NOT VERIFIED.** `NVIDIA_API_KEY`/`AI_API_KEY` kosong di
  environment ini (panjang 0, dicek tanpa membaca nilai). Jalur generate dengan LLM
  nyata hanya teruji via mock di pytest + 502-jujur live tanpa key.
- **Flow Bridge otomatisasi nyata** (Playwright/API Flow) — tetap tracker manual/export
  manual; di luar lingkup (P3). `import-results` kini memvalidasi file ada, tapi tidak
  menjalankan otomasi apa pun.
- **Model Shot terpisah** (P2-03) — shot list tetap JSON di Scene; tidak dibuat model baru.
- **Migrasi Alembic saat startup** (P2-05) — app tetap memakai `create_all`; tidak diubah.
- **Upload aset ke S3 / endpoint download terautentikasi, verifikasi magic bytes** (P2-04) —
  hanya allowlist ekstensi + batas ukuran yang diterapkan.
- **Audit logging** (P1-02) — tidak dikerjakan karena masuk ranah security/audit (ditunda).
- **Prompt Studio via LLM** (P3-01) — prompt generate tetap template, bukan LLM.

---

## 5. Catatan verifikasi lain
- Selama smoke, klien HTTP yang membaca proxy env malformed di VM ini crash dengan
  `ValueError: invalid literal for int()...` (F-H6) — script smoke memakai
  `trust_env=False`, sama seperti pola yang kini dipakai semua pemanggilan Google backend.
- `git status` repo menunjukkan perubahan tak ter-commit lain di luar kaki Hermes
  (mis. `opencode/`, plus beberapa file Hermes dari ronde sebelumnya seperti
  `backend/app/models/__init__.py`, `backend/app/utils/encryption.py`,
  `backend/tests/test_api.py`) — itu BUKAN dari pekerjaan ini dan tidak disentuh.
- Tidak ada kredensial yang dibaca nilainya, diubah, atau ditulis di laporan ini.
