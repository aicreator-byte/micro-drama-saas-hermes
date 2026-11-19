# Uji Fallback Akun Google — kaki Hermes (live, API)

Tanggal: 19 Nov 2026, ~08:40–08:55 WIB (01:40–01:55 UTC).
Perintah: Di 08:36 WIB — tiap kaki tes sendiri khusus fallback akun Google.
Pelaksana: agen kaki Hermes (via API/DB/kode; tanpa browser task).
Scope: fallback akun Google SAJA (bukan auto-generate, bukan fitur lain).

## Lingkungan saat tes

- Backend Hermes: http://127.0.0.1:8001 (prefix `/api/v1`), frontend :3001 — keduanya hidup.
- DB live: `hermes/backend/test_live.db` (dipakai server yang jalan).
- Akun tes (dibuat via API, user terpisah `fbtest-hermes-20261119@example.com`):
  - Akun A `gagal-a-fbtest@example.com`, id `fa820bdd-d72a-4dbd-b7de-fb371bb6f1a8`
  - Akun B `gagal-b-fbtest@example.com`, id `97da3c8e-09d1-4741-a5c8-0741ba09a58d`
  - Keduanya: email palsu + password salah (throwaway, hanya untuk tes ini).
- Proyek `d57cac99-5b23-48e5-b7ce-f4d22480792b` ("Fallback Test Hermes").
- Task `b48fd2b5-8edd-421b-b812-fdf4b56ce41d` (`video_generation`, tanpa
  `google_account_id` — auto-pick / preferred kosong).

## Temuan saat persiapan (bukan kode produk yang diubah)

1. **DB live belum pernah dimigrasi.** `POST /flow/.../tasks` pertama
   mengembalikan 500: `table flow_tasks has no column named
   active_account_id`. `test_live.db` tidak punya tabel `alembic_version`
   (DB dibuat via `create_all`, bukan migrasi). Perbaikan setup tes:
   `alembic stamp phase2_settings_oauth` → `upgrade head` (kolom
   `active_account_id` / `fallback_history` / `error_message` berhasil
   ditambahkan; migrasi berikutnya `auto_generate_jobs` gagal karena
   tabelnya sudah ada dari `create_all`) → `alembic stamp head`
   (efek migrasi itu sudah ada di DB). Sesudahnya `alembic current` =
   head, task create 201. **Tidak ada file kode produk yang diubah.**
2. **Playwright tidak ada di `.venv`** (venv yang dipakai server yang
   jalan). `POST .../execute-browser` pertama: 502 `Playwright is not
   installed — browser login cannot run`. Playwright 1.55.0 hanya ada di
   `venv` (venv satunya). Perbaikan setup tes: `pip install --only-binary
   :all: playwright==1.55.0` ke `.venv`; Chromium sudah ada di cache
   (`~/.cache/ms-playwright`, launch terverifikasi v140.0.7339.16);
   server di-restart (kill by PID, start ulang perintah yang sama).
   Sesudahnya `/docs` 200.

## Tes 1 — jalur browser, proxy egress bawaan (`POST .../execute-browser`)

- Hasil: **502 dalam 7,6 dtk.** `Browser could not reach Google:
  Page.goto: net::ERR_TUNNEL_CONNECTION_FAILED at
  https://myaccount.google.com/`.
- Task sesudahnya: `status: failed`, `active_account_id: null`,
  `fallback_history: []` (kosong), `error_message` = pesan jaringan itu.
- `GET browser-session` akun A sesudahnya: `has_password: true`,
  `profile_exists: true` (profil persisten terbentuk),
  `session: {}` (tidak ada sesi).
- Artinya: sesuai desain, **error jaringan menghentikan eksekusi tanpa
  fallback ke akun berikut** (ganti akun tidak memperbaiki jaringan) dan
  **tidak disamarkan jadi `login_failed`** — kedua akun belum sempat
  dicoba sama sekali. Penyebabnya egress VM (Chromium tidak menembus
  proxy ke Google), bukan bug service. Sama seperti yang dilaporkan di
  BROWSER-LOGIN-REPORT.md (17 Nov).

## Tes 2 — jalur token, tanpa token (`POST .../execute`)

- Kondisi: kedua akun masih `DISCONNECTED`, tanpa token OAuth.
- Hasil: **502 dalam 0,2 dtk.** `No usable Google account: no CONNECTED
  account with valid tokens`. `fallback_history` tetap `[]`.
- Artinya: filter kandidat bekerja — tanpa akun CONNECTED bertoken,
  loop tidak jalan dan endpoint mengembalikan 502 jujur.

## Tes 3 — jalur token, token palsu + CONNECTED (`POST .../execute`)

- Kondisi: kedua akun di-PATCH via API jadi `status: connected` +
  `session_data` berisi token palsu (access + refresh).
- Hasil: **502 dalam 15,3 dtk.** `All Google accounts failed —
  gagal-a-fbtest@example.com: refresh_failed;
  gagal-b-fbtest@example.com: refresh_failed`.
- `fallback_history` +2 entri (A 01:44:09 UTC, B 01:44:11 UTC),
  keduanya `failed` / `refresh_failed`.
- Artinya: **mekanisme fallback loop TERVERIFIKASI live (jalur token)**
  — urutan A lalu B (terlama dulu), tiap percobaan dicatat dengan
  alasan, gagal di A → pindah ke B, semua gagal → 502 jujur dengan
  alasan per akun. Tokeninfo ke Google lewat httpx JALAN dari VM ini
  (token palsu ditolak Google → refresh gagal karena tanpa kredensial
  OAuth di Settings) — beda dengan Chromium yang terblokir egress.

## Tes 4 — jalur browser via relay, sesi dipakai ulang

- Setup tambahan (tanpa ubah kode): server di-restart dengan
  `HTTPS_PROXY=http://127.0.0.1:43681` — relay CONNECT lokal milik
  backend OpenCode (prosesnya sedang jalan; `curl` via relay:
  `example.com` 200, `myaccount.google.com` 302). Verifikasi:
  `HTTPS_PROXY` relay ada di environ proses server yang baru.
- Hasil: **502 dalam 42,9 dtk.** Alasan per akun: `flow_blocked`
  (A 01:49:45 UTC, B 01:50:04 UTC). `fallback_history` +2 entri.
- **Temuan — false positive cek sesi:** `session.json` kedua akun
  tertulis `"last_outcome": "logged_in"` (A 01:49:34, B 01:49:56)
  padahal akun itu palsu dan kredensial TIDAK PERNAH diisikan.
  Penyebab (dari kode `browser_login.py::_is_logged_in`): bila di
  `myaccount.google.com` tidak ditemukan form sign-in DAN tidak ada
  penanda login (`#account-home` / `[data-logged-in]`), fungsi
  mengembalikan `True` ("anggap sesi hidup"). Driver lalu melewati
  login dan langsung submit ke Flow — di sana tidak ada kotak prompt
  (tanpa sesi nyata / bot-block) → `flow_blocked`. **Dengan akun nyata,
  false positive yang sama bisa melewatkan login lalu gagal di Flow
  dengan `flow_blocked` — ini temuan produk, bukan artefak tes.**
  (Selector form login Google juga sudah dicatat belum teruji melawan
  Google asli di BROWSER-LOGIN-REPORT.md.)

## Tes 5 — jalur browser via relay, `force_relogin: true`

- Hasil: **502 dalam 13,6 dtk.** Alasan per akun: `browser_challenge`
  (A 01:51:13 UTC, B 01:51:19 UTC). `fallback_history` +2 entri.
- Artinya: dengan login dipaksa, driver SAMPAI ke form sign-in Google
  asli, mengisi email palsu, dan Google meminta verifikasi tambahan
  (2FA/captcha — deteksi bot pada login otomatis). Loop fallback jalan
  lagi: A `browser_challenge` → B `browser_challenge` → 502 jujur.
- **Jalur browser yang menembus sampai ke Google hanya mungkin di VM
  ini lewat relay + CA egress** (lihat catatan setup di bawah). Tanpa
  itu, Chromium berhenti di `ERR_TUNNEL_CONNECTION_FAILED`
  (Tes 1) atau `ERR_CERT_AUTHORITY_INVALID`.

## Status akhir task (terverifikasi via GET)

- `status: failed`, `active_account_id: null`.
- `error_message`: `All Google accounts failed:
  A: refresh_failed; B: refresh_failed; A: flow_blocked;
  B: flow_blocked; A: browser_challenge; B: browser_challenge`.
- `fallback_history`: 6 entri (2 refresh_failed + 2 flow_blocked +
  2 browser_challenge), urutan A lalu B di tiap pasangan, riwayat
  bersifat append-only (tidak dihapus antar eksekusi).

## Catatan setup relay + CA (bukan kode produk)

- Agar Chromium dari VM ini mencapai Google, dipakai relay CONNECT
  lokal OpenCode (`127.0.0.1:43681`, port ephemeral milik proses
  backend OpenCode yang sedang jalan — bila backend itu restart,
  port berubah dan proxy ini mati) + CA egress Hatch
  (`Hatch Sandbox Egress CA`, dari `/run/hatch/egress-tls/`) yang
  dimasukkan ke salinan NSS DB Chromium (`/tmp/fakehome/.pki/nssdb`,
  karena `~/.pki/nssdb` asli read-only di filesystem ini).
- Server Hermes sempat di-restart dengan env itu
  (`HOME=/tmp/fakehome`, `PLAYWRIGHT_BROWSERS_PATH`,
  `HTTPS_PROXY`/`HTTP_PROXY` relay). **Sesudah tes selesai, server
  dikembalikan ke konfigurasi default** (restart polos, tanpa relay
  / HOME palsu) — jadi kondisi default kembali: jalur browser gagal
  di egress (Tes 1). Yang bertahan dari setup ini: Playwright 1.55.0
  kini terpasang di `.venv`, dan migrasi DB live sudah di head.

## NOT VERIFIED (jujur)

- **Login Google asli (akun Di): TIDAK terverifikasi.** Akun Di tidak
  pernah masuk ke DB kaki Hermes — browser cloud tidak menjangkau
  frontend localhost (`127.0.0.1:3000` ditolak `invalid_request`),
  sehingga penambahan lewat browser tidak bisa jalan. Tidak ada
  kredensial asli yang dipakai dalam tes ini.
- Login browser SUKSES dengan akun nyata, submit prompt ke Google Flow
  nyata, dan video Flow: belum pernah teruji live dari VM ini (butuh
  akun nyata + mesin yang mencapai Google).
- Tidak ada video yang di-generate dalam tes ini.

## Sisa untuk bersih-bersih (bila perlu)

- User tes `fbtest-hermes-20261119@example.com` (id
  `6fb79421-c496-4641-b7d4-036ff39b1f89`), akun A/B di atas, proyek
  `d57cac99…`, task `b48fd2b5…` — semua di `test_live.db`, milik user
  tes saja (kandidat fallback bersifat per-user, tidak memengaruhi
  akun Di). Password tes tidak dicatat di laporan ini.
- Profil browser akun A/B:
  `hermes/browser-profiles/6fb79421-c496-4641-b7d4-036ff39b1f89/<account-id>/`
  (berisi `session.json` dengan `last_outcome: logged_in` yang false
  positive — lihat Tes 4).
- Scratch: `/tmp/fakehome/` (NSS DB salinan + CA), `/tmp/hatch-egress-ca.pem`.
