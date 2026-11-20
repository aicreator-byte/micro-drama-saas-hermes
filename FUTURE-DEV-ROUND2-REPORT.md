# Future Development Round 2 — kaki Hermes (20 Nov 2026)

Perintah Di 20 Nov 06:03: selesaikan SEMUA Future Improvements kaki Hermes.
Dikerjakan HANYA di `~/workspace/micro-drama-saas/hermes/`. **Push ke GitHub
TIDAK dilakukan** — itu urusan parent agent. Tidak ada video Flow yang
di-generate, tidak ada akun Google asli Di yang dipakai, tidak ada nilai
key/password yang dicetak atau di-commit (`.env` tetap ter-ignore).

## Ringkasan hasil

Keenam item SELESAI + terverifikasi tes. Full suite backend: **139 passed**
(108 round 1 + 27 tes baru round 2 + 4 tes tambahan; 0 gagal, 0 regresi).
Frontend: `tsc --noEmit` 0 error, `npm run build` sukses (25 route,
termasuk 4 route baru `[id]/collab|timeline|consistency|subtitles`).
Migrasi Alembic: `upgrade head` di DB scratch bersih → head
`round2_future_dev`, 5 tabel baru ada.
Live smoke server nyata (DB scratch, tanpa LLM kecuali cek konsistensi):
**17/17 cek OK**, termasuk transkrip Whisper nyata dari audio ucapan
Bahasa Indonesia (2 segmen, SRT + VTT terunduh).

## 1. Real-time collaboration — SELESAI

- `backend/app/services/collab.py` (baru): `CollabManager`/`CollabRoom`
  in-memory per proyek (single-worker, sama seperti auto-generate async);
  presence (user, nama, field yang sedang diedit) + broadcast update;
  `validate_edit_op` — field di-whitelist per resource
  (project: title/description/genre; series_bible: premise/main_plot/tone/
  visual_style/world_settings/ending_direction; episode: title/outline/
  production_notes; character: personality/physical_appearance/background/
  costume). Field di luar whitelist (mis. `owner_id`, `status`) ditolak.
- `backend/app/api/collab.py` (baru): `WS /projects/{id}/collab/ws?token=<JWT>`
  (auth JWT via query param — header Authorization tidak bisa di WS browser);
  pesan masuk `presence` / `edit`; keluar `presence` / `update` / `ack` /
  `error`. REST fallback: `GET .../collab/presence`,
  `POST .../collab/edit` (edit tersimpan + disiarkan ke room).
  Tenant check di setiap edit (resource harus milik proyek user).
- Frontend: `src/app/dashboard/projects/[id]/collab/page.tsx` (+ `Client.tsx`)
  — daftar yang online, edit judul proyek + plot bible bersama via WS
  (fallback REST bila WS putus), log aktivitas.
- Bukti: `tests/test_future_dev_round2.py` — WS end-to-end 2 koneksi
  (join → presence → edit episode → update diterima koneksi ke-2 → nilai
  tersimpan di DB); REST edit + field terlarang ditolak + presence kosong.
  Smoke live: REST edit OK, judul episode berubah jadi "EP1 Kolaborasi",
  presence kosong (tidak ada editor lain).

## 2. Payment integration (TEST MODE) — SELESAI

- `backend/app/services/billing.py` (baru): paket Free Rp0 / Pro Rp99.000 /
  Studio Rp249.000 (IDR/bulan, test only). `TestBillingProvider` — checkout
  mengembalikan URL `https://checkout.test/...` (tidak ada charge nyata,
  tidak ada panggilan ke Stripe, tidak ada live key). Webhook: verifikasi
  HMAC-SHA256 header `X-Test-Signature`; event yang dipetakan:
  checkout.session.completed / subscription.created|updated → active,
  invoice.payment_failed → past_due, subscription.deleted → canceled.
  **Integrasi live Stripe sengaja TIDAK diimplementasikan** (Di tidak punya
  kartu kredit; bila suatu saat ada live key di env, provider test tidak
  akan memakainya).
- `backend/app/api/billing.py` (baru): `GET /billing/plans`,
  `GET /billing/subscription` (auto-buat baris Free bila belum ada),
  `POST /billing/checkout` (Free langsung aktif tanpa checkout),
  `POST /billing/webhook`, `POST /billing/cancel` (kembali Free).
  Semua event dicatat ke `billing_events` (audit trail, tanpa nomor kartu).
- Frontend: `src/app/dashboard/billing/page.tsx` (+ link sidebar) — paket,
  status langganan, checkout (buka URL test di tab baru), batalkan.
- Bukti: 8 tes billing (plans, default Free/inactive, checkout Pro test,
  plan tak dikenal 400, Free aktif langsung, webhook HMAC valid → active +
  `current_period_end` terisi, signature salah 401, cancel → canceled/Free).
  Smoke live: webhook HMAC valid → subscription `active`.

## 3. Mobile app (React Native / Expo) — SCAFFOLD SELESAI

- `mobile/` (baru): Expo SDK 52, `App.tsx` (navigasi state sederhana:
  Login → Projects → Detail), `src/lib/api.ts` (axios + AsyncStorage,
  `EXPO_PUBLIC_API_URL`; default emulator Android `10.0.2.2:8001`),
  `src/screens/LoginScreen.tsx`, `ProjectsScreen.tsx` (daftar + buat proyek
  + pull-to-refresh), `ProjectDetailScreen.tsx` (detail + trigger
  Auto-Generate + polling status tiap 2 dtk, sama seperti web),
  `app.json`, `tsconfig.json`, `.gitignore`, `README.md`.
- **Koreksi saat implementasi:** login backend Hermes memakai JSON
  `{email, password}`, bukan OAuth2 form — `mobile/src/lib/api.ts` sudah
  diperbaiki ke JSON (bug yang sama sempat menggagalkan smoke script).
- Bukti: `node node_modules/typescript/bin/tsc --noEmit` di `mobile/` = 0 error.
  `npm install` awal gagal `EPERM chown` (batasan container) — berhasil
  dengan `npm install --ignore-scripts --no-bin-links` (885 paket).
- NOT VERIFIED: **belum dijalankan di Expo Go / emulator / HP fisik**
  (tidak ada emulator di VM ini). Ikon `assets/icon.png` belum ada.

## 4. Advanced video editing timeline — SELESAI

- Model `VideoTimeline` (1 timeline per episode): `clips` JSON
  `{id, track, start, duration, prompt_id, scene_id, asset_id, label,
  transition}`, `duration_seconds` = max(start+duration),
  `fps` (default 30), `resolution` (default `1080x1920`).
- `backend/app/api/timeline.py` (baru): `GET/POST/PATCH/DELETE
  /projects/{id}/episodes/{ep_id}/timeline` (POST kedua → 409) +
  `POST .../timeline/from-prompts` — bangun timeline otomatis dari prompt
  video-generation episode (1 clip per prompt, 8 detik, berurutan, track 0).
  Tenant check per episode.
- Frontend: `src/app/dashboard/projects/[id]/timeline/page.tsx`
  (+ `Client.tsx`) — pilih episode, bangun dari prompt / kosong, tambah
  clip (label + durasi), hapus clip, hapus timeline.
- Bukti: 3 tes (CRUD + durasi total, from-prompts 2 prompt = 16 dtk,
  user lain 404). Smoke live: create 2 clip = 16,0 dtk, GET 2 clip.

## 5. AI-powered character consistency checking — SELESAI

- `backend/app/services/consistency.py` (baru): dua lapis —
  (a) rule-based deterministik: varian ejaan nama mirip (SequenceMatcher
  ≥ 0,80, mis. Nadia vs Nadya) + nama yang disebut ≥2x di outline tapi
  tidak ada di daftar karakter; (b) LLM via `AIClient` yang sama dengan
  auto-generate (temperature 0,2, max 4000 token, output JSON list
  `{character, episode_number, type, severity, description, suggestion}`);
  `parse_llm_issues` toleran terhadap fence ```json/teks pengantar;
  LLM gagal → `[]` (hasil rule-based tetap tersimpan, bukan exception);
  `merge_issues` dedup.
- `backend/app/api/consistency.py` (baru): `POST /projects/{id}/consistency-check`
  (201; 400 bila proyek belum punya karakter),
  `GET .../consistency-checks` + `GET .../consistency-checks/{id}`.
- Frontend: `src/app/dashboard/projects/[id]/consistency/page.tsx`
  (+ `Client.tsx`) — jalankan cek, daftar masalah per severity, riwayat cek.
- Bukti: 7 tes (rule-based varian nama, nama hantu di outline, parse LLM
  toleran + invalid → [], dedup, endpoint menemukan `name_variant`,
  400 tanpa karakter, jalur LLM dengan fake client, provider gagal → []).
  Smoke live: cek 1 karakter + 1 episode → `completed`, 0 issue
  (data bersih — tidak ada inkonsistensi untuk ditemukan).
- NOT VERIFIED: panggilan LLM nyata saat smoke live tidak terkonfirmasi
  dari log server (0 baris "Trying AI provider"; kemungkinan level log) —
  jalur LLM terverifikasi lewat fake client di unit test, bukan provider
  live. Uji dengan data yang memang inkonsisten + LLM nyata belum dilakukan.

## 6. Automated subtitle generation (Whisper) — SELESAI

- `backend/app/services/subtitles.py` (baru): `faster-whisper` lokal
  (default model `tiny`, bahasa `id`, CPU int8; model diunduh sekali dari
  Hugging Face saat pertama dipakai, setelahnya offline). Formatter murni
  `segments_to_srt` / `segments_to_vtt` (tanpa engine).
- **Bug ketemu saat smoke + perbaikan:** faster-whisper 1.2.1 memanggil
  `av.open(..., metadata_errors="ignore")` yang ditolak PyAV 19.0.2
  (`TypeError`); pin `av==14.4.0` gagal build (tidak ada wheel Python
  3.14). Perbaikan: decode audio via **ffmpeg CLI** (`-ac 1 -ar 16000
  pcm_s16le`) + stdlib `wave` + numpy, lalu `model.transcribe(numpy_array)`
  — jalur PyAV faster-whisper tidak dipakai sama sekali. Catatan ini ada
  di `requirements.txt` + docstring `_load_audio_array`.
- `backend/app/api/subtitles.py` (baru): `GET /projects/subtitles/engine`
  (status engine), `POST /projects/{id}/subtitles` (upload audio/video
  ≤200 MB, format mp3/wav/m4a/ogg/flac/mp4/mov/mkv/webm; transkrip di
  background thread via `asyncio.to_thread` supaya event loop tidak macet;
  503 jelas bila engine belum terpasang),
  `POST .../subtitles/from-segments` (bangun SRT/VTT dari segmen transkrip
  tanpa engine), `GET .../subtitles`, `GET .../subtitles/{id}`,
  `GET .../subtitles/{id}/download?fmt=srt|vtt`.
  File di `UPLOAD_DIR/subtitles/`.
- Frontend: `src/app/dashboard/projects/[id]/subtitles/page.tsx`
  (+ `Client.tsx`) — status engine, upload + polling daftar, buat SRT/VTT
  dari segmen (format `start-end teks` per baris), unduh SRT/VTT.
- Bukti: 5 tes (format SRT/VTT, engine tersedia, from-segments +
  download SRT/VTT, status engine, decode wav via ffmpeg + transcribe
  dengan fake model yang menegaskan model menerima numpy array).
  Smoke live (audio ucapan Bahasa Indonesia dari espeak-ng,
  "Halo, saya Nadia. Selamat datang di episode pertama."): job
  `completed`, **2 segmen** — "Halo, saya Nadia." (0–2 dtk),
  "Selamat Nadia Pesodepertama." (2–5 dtk, salah dengar espeak) —
  transkrip Whisper nyata, SRT (112 B) + VTT terunduh OK.

## 7. Verifikasi keseluruhan

- Backend full suite: **139 passed** (128,57 dtk), 0 gagal — termasuk
  31 tes baru `tests/test_future_dev_round2.py`.
- Migrasi Alembic: `upgrade head` di `/tmp/r2_smoke.db` bersih →
  head `round2_future_dev`; 5 tabel baru terverifikasi ada
  (`subscriptions`, `billing_events`, `video_timelines`,
  `character_consistency_checks`, `subtitle_jobs`).
- Frontend: `npx tsc --noEmit` 0 error; `npm run build` sukses (25 route).
  **Perbaikan build:** route `[id]` baru sempat gagal prerender
  (`usePathname()` di `DashboardLayout` di luar Suspense; Next 16 +
  `cacheComponents: true` melarang `export const dynamic` dan `instant`
  di Client Component). Perbaikan: `DashboardLayout` dibungkus
  `<Suspense>` di `src/app/dashboard/layout.tsx` + tiap page `[id]`
  baru jadi server component tipis (`export const instant = false` +
  `<Suspense>`) yang merender `Client.tsx`. Route baru tampil sebagai
  Partial Prerender (◐) di output build.
- Mobile: `tsc --noEmit` 0 error.
- Live smoke (`/tmp/r2_smoke.py`, server scratch port 18098, DB scratch):
  **17/17 OK** (server dimatikan setelah smoke, port bebas).
  Data smoke tertinggal di `/tmp/r2_smoke.db` (bisa hilang saat VM swap)
  dan file subtitle di `uploads/subtitles/` (job smoke).
- `faster-whisper==1.2.1` + `numpy` ditambah ke `requirements.txt`
  (terpasang di `.venv` kaki Hermes).

## 8. NOT VERIFIED (jujur, jangan dianggap selesai)

- Mobile app belum dijalankan di Expo Go / emulator / HP fisik; ikon
  `assets/icon.png` belum ada; layar timeline/kolaborasi/billing/subtitle
  belum ada di mobile (scope scaffold: proyek + auto-generate).
- Cek konsistensi: panggilan LLM nyata saat smoke live tidak terkonfirmasi
  dari log; belum diuji dengan data yang memang inkonsisten + LLM nyata.
- Klik manual keempat halaman baru di browser (hanya API + unit tes +
  live smoke via HTTP); WS kolaborasi di browser nyata belum diklik.
- Login Google asli + video Flow asli (tetap di luar scope, seperti round 1).
- Job subtitle video (mp4) live — baru audio wav yang ditranskrip live;
  jalur decode video memakai ffmpeg yang sama, tapi belum dibuktikan file mp4.

## 9. File yang diubah / dibuat

Backend: `app/models/__init__.py` (5 model baru),
`alembic/versions/round2_future_dev.py` (baru),
`app/schemas/__init__.py` (schema billing/timeline/consistency/subtitle/collab),
`app/services/billing.py`, `app/services/consistency.py`,
`app/services/subtitles.py`, `app/services/collab.py` (baru),
`app/api/billing.py`, `app/api/timeline.py`, `app/api/consistency.py`,
`app/api/subtitles.py`, `app/api/collab.py` (baru),
`app/main.py` (daftarkan 5 router), `requirements.txt`
(faster-whisper + numpy), `tests/test_future_dev_round2.py` (baru, 31 tes).
Frontend: `src/types/index.ts`, `src/lib/api.ts`,
`src/components/layout/DashboardLayout.tsx` (link Billing),
`src/app/dashboard/layout.tsx` (Suspense),
`src/app/dashboard/billing/page.tsx` (baru),
`src/app/dashboard/projects/[id]/{collab,timeline,consistency,subtitles}/page.tsx`
+ `Client.tsx` (baru).
Mobile: `mobile/` (baru: `package.json`, `app.json`, `tsconfig.json`,
`.gitignore`, `README.md`, `App.tsx`, `src/lib/api.ts`,
`src/screens/{LoginScreen,ProjectsScreen,ProjectDetailScreen}.tsx`).
Root: `README.md`, `FUTURE-DEV-ROUND2-REPORT.md` (file ini).

Tidak ada file di luar `~/workspace/micro-drama-saas/hermes/`.
`.env` tidak dibaca nilainya, tidak dicetak, tidak di-commit.
Tidak ada video yang di-generate. Tidak ada akun Google asli dipakai.
Tidak ada push ke GitHub.
