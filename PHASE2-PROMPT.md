MARKER: PHASE2-HERMES
# Phase 2 — Kaki Hermes: LLM nyata + OAuth Google nyata + Settings UI

Baca dulu `../PHASE2-PROMPT.md` (spec bersama + desain settings/env + larangan) —
itu mengikat. Prompt ini hanya tugas spesifik kaki Hermes.

KONTEKS (terverifikasi dari kode + audit, jangan diperdebatkan):
- Kerja HANYA di `/home/hatch/workspace/micro-drama-saas/hermes/`. Jangan sentuh
  kaki lain atau file di luar direktori ini.
- Backend: `backend/app/` — router di `backend/app/api/` (`story_engine.py`,
  `google_accounts.py`, `auth.py`, `projects.py`, `series_bible.py`,
  `characters.py`, `locations.py`, `episodes.py`, `scenes.py`, `prompts.py`,
  `flow_bridge.py`, `assets.py`); prefix API `settings.API_V1_PREFIX`
  (`backend/app/main.py`); config `backend/app/core/config.py` (SUDAH punya
  `AI_PROVIDER` / `AI_MODEL` / `AI_API_KEY` dari env — pakai dan kembangkan itu,
  jangan buat config baru); enkripsi di `backend/app/utils/encryption.py`.
- Frontend: Next.js di `frontend/src/app/` (login, register, dashboard: projects,
  series-bible, characters, locations, episodes, scenes, prompts, flow, assets,
  google-accounts, dialogues). TIDAK ADA halaman Settings — itu bagian tugas.
- Baseline: pytest 40/40, smoke 20/20, build 18/18 halaman. Jangan turunkan.

TUGAS (hanya ini):
1. **LLM nyata ganti mock Story Engine** (`backend/app/api/story_engine.py`):
   mock ada di generate episode outlines dan scene breakdown (komentar "mock
   implementation" di kode). Buat satu modul klien AI kecil (mis.
   `backend/app/services/ai_client.py`, pakai `httpx` yang sudah terpasang):
   baca daftar provider + urutan fallback dari setting (lihat spec bersama),
   kunci dari env var, panggil chat completions, fallback ke provider berikut
   bila gagal/kuota/kosong. Ganti KEDUA mock dengan panggilan LLM nyata.
   Provider yang terverifikasi jalan: Nvidia NIM ultra-550b — jadikan entri
   pertama/aktif. Jangan klaim provider lain jalan.
2. **Settings API + model** (baru, ikuti pola router/model yang ada):
   tabel/model `AppSettings` (satu baris): `ai_providers` (JSON, lihat spec),
   `google_oauth_client_id` + `google_oauth_client_secret` (enkripsi pakai
   `backend/app/utils/encryption.py`). Endpoint `GET /settings` (tanpa nilai
   rahasia — hanya flag `configured`) dan `PATCH /settings` (ubah urutan/
   enabled provider, isi kredensial OAuth). Satu-satunya tempat kredensial
   OAuth disimpan. Jangan simpan kunci AI di DB — kunci tetap env var.
3. **OAuth Google nyata** (`backend/app/api/google_accounts.py`): ganti asumsi
   mock — implementasikan authorize URL Google asli (state acak per request,
   simpan + validasi di callback), callback tukar `code` → token (httpx POST
   ke token endpoint Google), simpan token terenkripsi, refresh saat
   kedaluwarsa. Perbaiki endpoint `/sync`: coba validasi sesi nyata
   (tokeninfo/refresh); bila tidak bisa divalidasi, kembalikan status jujur
   "unverified", jangan tandai terhubung. Tambah field `password_encrypted`
   pada record akun Google (enkripsi yang sama) untuk Flow Bridge.
   BATAS: kredensial OAuth client asli dari Di belum ada — verifikasi alur
   + URL + callback + refresh; login end-to-end = NOT VERIFIED di laporan.
4. **Halaman Settings** (baru, `frontend/src/app/dashboard/settings/page.tsx`,
   ikuti pola halaman dashboard yang ada): edit daftar provider AI + urutan
   fallback (drag/naik-turun atau tombol), isi kredensial OAuth client
   (field password, tidak pernah tampil nilainya), simpan via `PATCH /settings`.
   Wire halaman Story Engine yang ada ke hasil LLM nyata (tampilkan konten
   hasil generate, bukan placeholder).
5. **Ketahanan kecil** (bukan security): `google_accounts.py` list endpoint
   memanggil `decrypt_data` di loop (audit M9) — bila satu akun gagal dekripsi,
   jangan crash seluruh list; lewati akun itu + catat error, kembalikan sisanya.
   JANGAN ubah perilaku lain di endpoint itu.

JANGAN UBAH: route/prefix/skema respons yang ada; perbaikan fix round 1–3;
`SECRET_KEY`, auth/JWT, enkripsi yang ada; batas karakter (maks 6 TIDAK
ditegakkan); story engine tetap di router yang sama (jangan pindah file).

SEBELUM menyatakan selesai, jalankan sendiri tes live (uvicorn + SQLite segar):
register + login + proyek + 6 karakter + episode + story generate LLM nyata
(konten BUKAN template mock — buktikan dengan potongan respons) + scene
generate LLM nyata + auth URL Google terbentuk (awal
`https://accounts.google.com/o/oauth2/v2/auth`, berisi `state`) + callback
menolak `state` salah + Settings PATCH tersimpan + `GET /settings` tidak
membocorkan rahasia + pytest tidak turun dari 40 + `npm run build` exit 0.
Tulis `PHASE2-REPORT.md` (apa yang diubah + hasil tes live per endpoint +
NOT VERIFIED: login Google end-to-end).
