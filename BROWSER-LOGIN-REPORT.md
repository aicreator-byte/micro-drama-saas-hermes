# Jalur Login Browser + Auto Ganti Akun — Flow Bridge (kaki Hermes)

Perintah Di 22:22 WIB 17 Nov 2026. Di menolak jalur Google Cloud Console
("Hrsnya login biasa. Dengan browser masing2"). Scope: fungsionalitas saja,
security ditunda. Tidak ada push GitHub. Hanya kaki Hermes yang disentuh.

## Ringkas

- Login Google **biasa lewat browser** (email + password, Playwright +
  Chromium), **tanpa client_id/secret Cloud Console**. OAuth tetap ada dan
  tidak dihapus — jalur browser jalan berdampingan dan tidak memakainya.
- Satu profil browser persisten per akun
  (`BROWSER_PROFILE_DIR/<user_id>/<account_id>/`): cookie/sesi Google
  tersimpan, login cukup sekali, eksekusi berikut memakai ulang sesi.
- Eksekusi Flow otomatis: `POST /flow/{project_id}/tasks/{task_id}/execute-browser`
  — login browser per akun -> submit prompt task ke Google Flow.
- Auto ganti akun: bila satu akun gagal karena alasan akun itu
  (`no_password` / `login_failed` / `browser_challenge` / `session_expired` /
  `flow_blocked`), otomatis pindah ke akun berikutnya milik user yang sama;
  setiap percobaan tercatat di `FlowTask.fallback_history` (field yang sudah
  ada). Semua gagal -> 502 jujur dengan alasan per akun.
- Mode manual tetap jalan: `export-prompts` tidak diubah.

## Yang diubah

| File | Perubahan |
|---|---|
| `backend/app/services/browser_login.py` | **Baru.** Driver + service login browser + eksekusi Flow (lihat Cara kerja). |
| `backend/app/services/google_account_fallback.py` | `ACCOUNT_SPECIFIC_REASONS` + 5 alasan browser (`no_password`, `login_failed`, `browser_challenge`, `session_expired`, `flow_blocked`); `run_with_google_fallback` terima override `candidates`. |
| `backend/app/api/flow_bridge.py` | Endpoint baru `POST /flow/{project_id}/tasks/{task_id}/execute-browser` (body opsional `{"force_relogin": bool}`). Endpoint `/execute` lama (token OAuth) tidak diubah. |
| `backend/app/api/google_accounts.py` | Endpoint baru `POST /google-accounts/{account_id}/browser-login` dan `GET /google-accounts/{account_id}/browser-session`. OAuth + password endpoint tidak diubah. |
| `backend/app/schemas/__init__.py` | `FlowTaskBrowserExecuteRequest`, `BrowserLoginRequest` baru. |
| `backend/app/core/config.py` | `BROWSER_PROFILE_DIR` (default `.../hermes/browser-profiles`), `FLOW_URL` (default `https://labs.google/fx/tools/flow`), `BROWSER_HEADLESS` (default true). |
| `backend/requirements.txt` | `playwright==1.55.0`. |
| `backend/tests/test_browser_login.py` | **Baru.** 11 tes (lihat Verifikasi). |
| `BROWSER-LOGIN-REPORT.md` | File ini. |

Tidak disentuh: kaki lain, folder audit, OAuth login, enkripsi (password
tetap dibaca via `decrypt_data` yang sudah ada), rate limiting, security
headers, `SECRET_KEY`, frontend, migrasi DB (tidak perlu — tidak ada kolom
baru; metadata sesi hanya file `session.json` per profil, tanpa kredensial).

## Cara kerja

1. **Kandidat browser** — `get_browser_candidate_accounts`: akun milik user
   yang punya `password_encrypted` tersimpan, **tanpa syarat status OAuth
   CONNECTED** (login browser tidak butuh token OAuth; akun fresh
   DISCONNECTED + password = kandidat valid). Urutan: akun yang diminta
   dulu, lalu akun lain (terlama dulu). Tanpa satu pun password tersimpan ->
   502 jujur "no account with a stored browser password".
2. **Login per akun** — `PlaywrightBrowserDriver` (profil persisten
   `launch_persistent_context`, satu user-data-dir per akun):
   cek sesi dulu (`myaccount.google.com` — bila tidak ada form sign-in,
   sesi dipakai ulang); bila belum login: isi email -> Next -> isi password
   -> Next -> deteksi hasil: sukses, `login_failed` (password salah /
   masih di form password), `challenge` (halaman 2FA/captcha — ditandai
   `browser_challenge`). Password dibaca terenkripsi dari DB dan tidak
   pernah ditulis ke log/file/response. Sukses -> `session.json` ditulis
   (`logged_in_at`, tanpa kredensial) + status akun CONNECTED.
3. **Submit Flow** — dari prompt task (judul + deskripsi + `input_prompts`),
   buka `FLOW_URL`, isi kotak prompt, klik Generate. Sukses submit -> task
   `generating` (video masih dirender di Flow; selesai lewat
   `import-results` yang sudah ada — tidak ada polling download otomatis).
   Sesi kedaluwarsa (Flow redirect ke sign-in) -> `session_expired`;
   kotak prompt tak ditemukan / halaman berisi penanda bot-block ->
   `flow_blocked`.
4. **Auto ganti akun** — loop `run_with_google_fallback` yang sama dengan
   fallback token: tiap percobaan dicatat di `fallback_history`
   (`failed`/`succeeded` + alasan + email + waktu); akun berhasil ->
   `active_account_id`/`google_account_id` pindah ke akun itu.
5. **Error jaringan ≠ error akun** — kegagalan browser mencapai Google
   (`net::ERR_*`, mis. proxy/DNS putus) diklasifikasi
   `GoogleServiceUnavailable`: langsung 502, akun berikut TIDAK dicoba
   (ganti akun tidak bisa memperbaiki jaringan), dan TIDAK disamarkan
   jadi `login_failed`.
6. **Proxy** — driver memakai proxy dari env `HTTPS_PROXY`/`HTTP_PROXY`
   bila target eksternal (Google). Proxy TIDAK dipakai untuk URL lokal:
   opsi `bypass` Playwright terverifikasi diabaikan Chromium di sini
   (request localhost lewat proxy -> `ERR_EMPTY_RESPONSE`), jadi driver
   hanya menyalakan proxy bila ada target non-localhost.

## Verifikasi — pytest (nyata)

Perintah (dari `backend/`): `venv/bin/python -m pytest -q` ->
**81 passed** (70 lama + 11 baru, 0 gagal).

Tes baru (`tests/test_browser_login.py`):
- Fake driver (tanpa jaringan/Google): login sukses -> `session.json`
  tersimpan; tanpa password -> `no_password`; challenge -> `browser_challenge`;
  `GET browser-session` (profil + `has_password`); akun 1 challenge ->
  akun 2 sukses (`generating`, `active_account_id` = akun 2, riwayat
  failed+succeeded, prompt terkirim); semua akun `login_failed` -> 502 +
  task `failed` + alasan per akun; semua akun tanpa password -> 502;
  akun DISCONNECTED + password tetap kandidat dan berhasil; error jaringan
  dari driver -> 502 "could not reach Google", akun berikut TIDAK dicoba,
  riwayat kosong.
- Browser SUNGGUHAN (Playwright + Chromium) vs halaman login lokal palsu
  (form Google 2 langkah + halaman Flow): isi form -> login sukses ->
  launch kedua memakai ulang sesi tanpa isi form lagi -> submit prompt ->
  marker submitted muncul; endpoint `execute-browser` dengan Chromium
  sungguhan -> 200 `generating`, riwayat succeeded.

Playwright: `pip install --only-binary :all: playwright==1.55.0` berhasil
di venv kaki ini (install biasa sempat gagal build wheel `greenlet` —
diatasi dengan binary-only). `playwright install chromium` **BERHASIL**
(CDN Playwright TIDAK terblokir — bertentangan dengan catatan awal tugas):
`chromium_headless_shell-1187` terunduh; default launch jalan. Chromium
lama di cache (`chromium-1248`, dsb.) tetap dipakai sebagai fallback via
`executable_path` bila build default belum ada.

## Verifikasi — smoke live (nyata)

Server: `DATABASE_URL="sqlite+aiosqlite:////tmp/bl-smoke.db"
SECRET_KEY="smoke-test-secret-key" BROWSER_PROFILE_DIR="/tmp/bl-smoke-profiles"
venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8124`
(DB segar, port bebas; skrip `/tmp/bl-smoke.py`, DB + profil dihapus
setelah selesai; server dimatikan by PID, port 8124 dicek bebas).

Hasil aktual:
- `health` 200; register/login/project/akun OK; set password OK
  (`POST /google-accounts/{id}/password` 200).
- `GET browser-session` sebelum login: `has_password: true`,
  `profile_exists: false`, `session: {}`.
- `POST browser-login` -> **502** `Browser could not reach Google:
  Page.goto: net::ERR_TUNNEL_CONNECTION_FAILED at
  https://myaccount.google.com/` (browser sungguhan, bukan mock).
  Setelahnya `profile_exists: true` (profil persisten terbentuk).
- `POST execute-browser` -> **502** yang sama; task `failed`,
  `error_message` = pesan jaringan itu. Akun DISCONNECTED + password
  BENAR-BENAR dicoba (sebelum perbaikan kandidat, endpoint ini
  mengembalikan "No usable Google account" tanpa mencoba).
- Perilaku ini jujur dan sesuai desain: error jaringan menggagalkan
  eksekusi tanpa fallback akun, dan tidak disamarkan jadi login gagal.

## Yang TIDAK terverifikasi / batasan jujur

- **Chromium dari VM ini TIDAK BISA mencapai Google asli.**
  `ERR_TUNNEL_CONNECTION_FAILED` baik tanpa proxy maupun lewat proxy env
  (`HTTPS_PROXY`/`HTTP_PROXY` = `hatch-egress-proxy:3128`); dua varian
  konfigurasi proxy Playwright (URL ber-auth, field username/password
  terpisah) sama-sama gagal, sementara `curl` lewat proxy yang sama
  mendapat 302 dari `myaccount.google.com`. Penyebab pasti di sisi proxy
  belum diketahui (kemungkinan aturan egress per-domain/aplikasi) —
  **bukan** bug service ini. Akibatnya: **login Google asli dan eksekusi
  Flow asli BELUM PERNAH jalan dari VM ini**. Di mesin/lingkungan yang
  bisa mencapai Google (laptop Di / VPS tanpa egress seketat ini), jalur
  ini mestinya jalan; verifikasi pertama dengan akun nyata harus dilakukan
  di sana.
- **Selector UI Google Flow BELUM terverifikasi** terhadap UI Flow yang
  sebenarnya (kotak prompt + tombol Generate bersifat best-effort).
  Selector form login Google memakai pola standar accounts.google.com
  (`#identifierId`, `#identifierNext`, `input[name=Passwd]`,
  `#passwordNext`) — juga belum teruji melawan Google asli. Jalankan
  pertama dengan akun nyata kemungkinan butuh penyesuaian selector.
- **Google bisa memblokir otomasi** (bot detection / captcha / 2FA):
  driver mendeteksi halaman challenge dan mengembalikan
  `browser_challenge` (akun dilewati, fallback ke akun berikut). Bila
  semua akun kena challenge, operator harus login manual sekali lewat
  browser dengan profil yang sama (profil persisten dipakai ulang, jadi
  sesi manual itu langsung terpakai eksekusi berikutnya) atau memakai
  `export-prompts` manual.
- **Tidak ada download/polling hasil Flow otomatis**: setelah submit,
  task `generating`; video diunduh/dimpor lewat `import-results` yang
  sudah ada.
- **Tidak ada kredensial Google asli untuk tes** (Di belum berikan
  akun/password) — semua tes login memakai akun palsu / halaman lokal
  palsu. Jangan klaim "login Google berhasil" sebelum uji akun nyata.

## Yang TIDAK dikerjakan + alasan

- **Perbaikan selector Flow terhadap UI asli**: tidak bisa — butuh akun
  Google nyata + akses Flow nyata dari mesin yang mencapai Google.
- **Mode headful / login manual terpandu**: tidak dibuat — operator bisa
  membuka profil browser persisten (`browser-profiles/<user>/<akun>/`)
  dengan Chromium biasa bila perlu login manual sekali.
- **Frontend** (tombol "Login via Browser" / status sesi browser di
  Settings / daftar task): tidak dikerjakan — task ini backend saja;
  endpoint sudah mengembalikan semua field yang dibutuhkan frontend.
- **Security** (rate limiting, security headers, SECRET_KEY, enkripsi):
  ditunda atas perintah — tidak diubah apa pun.
- **Push GitHub**: tidak dilakukan (sesuai perintah).
