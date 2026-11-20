# Perbaikan Temuan Audit Ronde 2 — kaki Hermes (20 Nov 2026)

Sumber temuan: `audit-3way-round2-hermes/AUDIT-REPORT.md` (verdict LAYAK
DENGAN CATATAN, skor 8,2/10, P0 = 0). Semua P1 + P2 diperbaiki di
`hermes/` saja. Tanpa push GitHub, tanpa akun Google asli, tanpa video Flow.

## Ringkasan

| Temuan | Status | Perbaikan |
|---|---|---|
| P1-1 cek konsistensi sinkron di request | FIXED | Background task + polling status |
| P1-2 kolaborasi single-worker in-memory | FIXED | Versi + presence persisten di DB |
| P1-3 upload subtitle baca penuh ke RAM + model_size bebas | FIXED | Streaming berbatas + whitelist model |
| P2-1 secret webhook test default hardcoded | FIXED | Wajib env, tanpa default; fallback secret acak per proses |
| P2-2 nama hantu hanya 1/episode | FIXED | Semua nama per episode, dedup |
| P2-3 JWT WS via query param | FIXED | Subprotocol `collab` (fallback query tetap ada) |
| P2-4 `datetime.utcnow()` deprecated | FIXED | 4 tempat yang disebut audit |
| P2-5 mobile `assets/icon.png` tidak ada | FIXED | Ikon 1024x1024 dibuat |

## Detail per temuan

### P1-1 — Cek konsistensi ke background task
- `backend/app/api/consistency.py`: POST `/{project_id}/consistency-check`
  kini membuat check RUNNING, menjadwalkan `_run_consistency_check`
  via `BackgroundTasks` (session sendiri lewat `_session_factory`,
  pola sama seperti auto-generate), dan kembali **201 langsung**.
  Hasil di-poll lewat `GET .../consistency-checks/{id}` (sudah ada).
  Gagal LLM/rule tetap disimpan sebagai FAILED, bukan 500.
- Frontend `consistency/Client.tsx`: setelah POST, poll tiap 2 dtk
  (maks ~5 menit) sampai status bukan `running`; tampilkan pesan
  "Cek sedang berjalan di background".
- Bukti live (smoke server scratch port 18098): POST 201 `running`,
  poll `running` x6 lalu `completed` 3 issue (~7 dtk — LLM tanpa key
  gagal lambat; inilah alasan async: request sinkron akan menggantung).

### P1-2 — State kolaborasi persisten di DB
- Model baru `CollabRoomState` (project_id, version) +
  `CollabPresence` (project_id, user_id, name, field, color,
  updated_at) di `backend/app/models/__init__.py`.
- Migrasi `alembic/versions/audit_r2_collab.py` (revises
  `round2_future_dev`, head baru `audit_r2_collab`).
- `backend/app/services/collab.py`: `bump_room_version` atomik
  (`UPDATE ... SET version = version + 1 ... RETURNING`), `get_room_version`,
  `upsert_presence`, `remove_presence`, `list_presence` (bersihkan baris
  basi > 300 dtk). Koneksi WS + broadcast tetap in-memory (tidak bisa
  disimpan di DB); versi + presence otoritatif di DB.
- `backend/app/api/collab.py`: join/set_field/disconnect tulis presence
  ke DB; edit naikkan versi DB; REST presence baca DB; heartbeat
  (refresh `updated_at` tiap 30 dtk tanpa pesan masuk).
- Bukti: REST edit v1, v2, lalu room in-memory dibuang (simulasi
  restart) → edit berikut v3 (lanjut dari DB, bukan dari 0). WS join
  menulis baris presence; disconnect menghapusnya.
- **Batasan tersisa (didokumentasikan di kode):** broadcast WS live
  hanya menjangkau koneksi di worker yang sama — tanpa Redis pub-sub.
  Edit dari worker lain tetap tersimpan di DB dan terlihat lewat REST,
  tapi tidak di-push real-time ke socket worker lain. Bila kolaborasi
  multi-worker penuh dibutuhkan, tambahkan Redis pub-sub di depan
  broadcast (`REDIS_URL` sudah ada di config).
- **Insiden saat perbaikan (temuan baru):** `finally` handler WS tidak
  bisa menyelesaikan cleanup DB di bawah TestClient — task di-cancel
  saat WS ditutup dan `await` di `finally` langsung `CancelledError`
  (scope anyio tetap tercancel). Diperbaiki dengan
  `anyio.CancelScope(shield=True)` di sekeliling cleanup disconnect.
  Di uvicorn produksi disconnect normal berupa `WebSocketDisconnect`
  dan `finally` jalan biasa; shield tidak mengubah perilaku itu.

### P1-3 — Upload subtitle streaming + whitelist model
- `backend/app/api/subtitles.py`: upload dibaca per chunk 1 MB langsung
  ke disk; begitu melewati 200 MB dibatalkan + file parsial dihapus —
  RAM tidak pernah memegang file utuh. `model_size` divalidasi ke
  whitelist sebelum file dibaca (400 bila tidak diizinkan).
- `backend/app/services/subtitles.py`: `ALLOWED_MODEL_SIZES =
  {"tiny", "base", "small"}`; `transcribe_file` menolak model lain
  dengan `ValueError` (defense in depth, sebelum cek engine/file).
- Bukti live: `model_size=large-v3` → 400; batas 0 MB (monkeypatched)
  → 400 tanpa file parsial tertinggal.

### P2-1 — Secret webhook test tanpa default hardcoded
- `backend/app/services/billing.py`: tidak ada lagi default
  `"whsec_..."` di repo (kode produk). Secret diambil dari env
  `BILLING_TEST_WEBHOOK_SECRET`; bila env kosong, dipakai secret acak
  per proses (`secrets.token_hex(32)`) + warning di log — webhook dari
  proses lain tidak valid. Set env untuk secret stabil antar restart.
- `backend/.env.example`: variabel didokumentasikan dengan perintah
  generate (`openssl rand -hex 32`).
- Bukti: sign/verify round-trip OK; webhook signature salah → 401
  (smoke live). Nilai secret lama hanya tersisa sebagai string
  pembanding di tes regresi (`test_no_hardcoded_default_secret`) —
  bukan default aktif.

### P2-2 — Semua nama hantu per episode
- `backend/app/services/consistency.py`: `break` setelah issue pertama
  per episode dihapus; tiap nama hantu dilaporkan sekali (dedup per
  episode). Tes: outline dengan Budi + Siti → keduanya dilaporkan.

### P2-3 — JWT WS via subprotocol
- `backend/app/api/collab.py`: `extract_ws_token()` — utamakan
  subprotocol `Sec-WebSocket-Protocol: collab, <jwt>` (tidak masuk
  access log); fallback `?token=` untuk klien lama. Risiko fallback
  didokumentasikan di docstring modul.
- Frontend `collab/Client.tsx`: `new WebSocket(url, ['collab', token])`
  — tanpa query param lagi.
- Tes e2e: WS connect subprotocol tanpa query param → presence OK;
  query param lama tetap jalan (tes lama tidak diubah).

### P2-4 — `datetime.utcnow()` deprecated
- Diganti di 4 tempat yang disebut audit — `billing.py:94`
  (`next_period_end`), `consistency.py:95`, `subtitles.py:88,175` —
  menjadi `datetime.now(timezone.utc).replace(tzinfo=None)` (tetap
  naive-UTC, sama seperti default kolom model; aman untuk kolom
  `DateTime` tanpa timezone). `utcnow()` di luar 4 tempat itu (model
  defaults, API lain) sengaja TIDAK disentuh — di luar temuan audit.

### P2-5 — Mobile icon
- `mobile/assets/icon.png` dibuat (1024x1024 RGB, 23.920 byte):
  latar violet `#7C3AED` (sama dengan `adaptiveIcon.backgroundColor`),
  lingkaran putih + segitiga play + teks "MICRO DRAMA". Dibuat lokal
  dengan Pillow, bukan aset unduhan.

## Verifikasi

- **Full pytest backend: 159 passed, 0 failed (199 dtk)** — 139 lama +
  20 tes regresi baru (`tests/test_audit_round2_fixes.py`).
  Tes lama `test_consistency_check_endpoint` diperbarui ke polling
  (POST kini async); `conftest.py` ikut patch `_session_factory`
  konsistensi ke engine tes (pola sama seperti auto-generate).
- **Migrasi Alembic di DB scratch:** upgrade head → `audit_r2_collab`
  (tabel `collab_room_states` + `collab_presence` ada); downgrade -1
  → `round2_future_dev`; re-upgrade → head OK.
- **Frontend:** `npx tsc --noEmit` 0 error; `npm run build` OK.
  **Mobile:** `tsc` 0 error.
- **Smoke live server scratch (port 18098, DB scratch, dimatikan
  setelahnya):** register/login OK; consistency POST 201 `running` →
  poll `completed` 3 issue; `model_size=large-v3` → 400; presence
  `[]`; REST edit version 1; webhook signature salah → 401. **7/7 OK.**
- Scan: tidak ada default secret hardcoded di kode produk; tidak ada
  file `.env`/secret baru; tidak ada perubahan di luar `hermes/`;
  tidak ada push GitHub.

## File diubah

- `backend/app/models/__init__.py` — model `CollabRoomState`, `CollabPresence`
- `backend/alembic/versions/audit_r2_collab.py` — migrasi baru (head)
- `backend/app/services/collab.py` — helper DB versi/presence + doc arsitektur
- `backend/app/api/collab.py` — auth subprotocol, state DB, heartbeat, shield cleanup
- `backend/app/api/consistency.py` — background task + `_session_factory`
- `backend/app/services/consistency.py` — hapus `break` nama hantu
- `backend/app/api/subtitles.py` — streaming upload + whitelist + utcnow
- `backend/app/services/subtitles.py` — `ALLOWED_MODEL_SIZES` + validasi
- `backend/app/services/billing.py` — secret tanpa default + utcnow
- `backend/.env.example` — dokumentasi `BILLING_TEST_WEBHOOK_SECRET`
- `backend/tests/conftest.py` — patch `_session_factory` konsistensi
- `backend/tests/test_future_dev_round2.py` — tes konsistensi jadi polling
- `backend/tests/test_audit_round2_fixes.py` — 20 tes regresi baru
- `frontend/src/app/dashboard/projects/[id]/consistency/Client.tsx` — polling
- `frontend/src/app/dashboard/projects/[id]/collab/Client.tsx` — subprotocol WS
- `mobile/assets/icon.png` — ikon baru

## NOT FIXED / batasan

- Broadcast WS lintas worker tetap butuh Redis pub-sub (lihat P1-2 di
  atas) — state sudah di DB, push live belum lintas worker.
- `datetime.utcnow()` di luar 4 tempat audit (model defaults + API
  lain) belum diganti — di luar scope temuan; bisa jadi ronde berikut.
- Klik manual UI konsistensi/kolaborasi di browser nyata belum
  dilakukan (hanya WS e2e + REST + build); job subtitle mp4 live
  belum dibuktikan (sama seperti status NOT VERIFIED audit).
- Mobile belum dijalankan di Expo Go/emulator (tidak ada emulator di VM).
