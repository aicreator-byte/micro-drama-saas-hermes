# HERMES LEG — FIX ROUND (perintah Di, 16 Nov 2026 ~04:23 WIB)

Kamu adalah agen yang membangun MVP ini. Sekarang perbaiki cacat-cacat di bawah,
yang ditemukan lewat verifikasi independen (tes unit + tes live + build).
Kerja HANYA di direktori ini (`micro-drama-saas/hermes/`). Jangan bangun ulang
dari nol. Jangan ubah modul yang tidak terkait. Jangan minta klarifikasi —
perbaiki langsung.

## CACAT 1 — Frontend production build GAGAL, 34 error (paling penting)

Perintah: `cd frontend && npm run build` → `Turbopack build failed with 34 errors`.

- 32× `Export SelectContent / SelectItem / SelectTrigger / SelectValue doesn't exist
  in target module` — halaman `src/app/dashboard/prompts/page.tsx`,
  `src/app/dashboard/flow/page.tsx`, `src/app/dashboard/assets/page.tsx`,
  `src/app/dashboard/dialogues/page.tsx` (dan mungkin halaman lain) meng-import
  subkomponen Select gaya Radix, tapi `src/components/ui/Select.tsx` hanya
  mengekspor SATU wrapper `<select>` native
  (`export const Select = forwardRef<HTMLSelectElement, SelectProps>`).
  Perbaiki dengan salah satu cara: (a) implementasikan subkomponen yang hilang
  sesuai pemakaian di halaman, atau (b) tulis ulang halaman-halaman itu memakai
  API Select native yang sudah ada. Pilih yang paling sedikit mengubah kode.
- 2× `the name 'Select' is defined multiple times` dan
  `the name 'useState' is defined multiple times` di
  `src/app/dashboard/scenes/page.tsx` baris 141–142 — import ganda di tengah file
  (komentar `// Need to import useState, Select`). Hapus duplikatnya.

Penerimaan: `npm run build` exit 0 tanpa error.

## CACAT 2 — Breakdown episode HTTP 500 bila proyek TANPA lokasi (terverifikasi live)

- `backend/app/api/story_engine.py`: `_generate_scene_breakdown()` memakai fallback
  `{"id": "0", "name": "Unknown Location"}` saat `locations` kosong; lalu
  `breakdown_episode()` memanggil `UUID(scene_data["location_id"])` →
  `ValueError: badly formed hexadecimal UUID string` → 500 tanpa penanganan.
- Perbaiki: bila tidak ada lokasi, set `location_id=None` (jangan pakai string "0"
  atau UUID palsu). Endpoint harus sukses untuk proyek dengan nol lokasi.

Penerimaan: buat proyek baru → generate series → breakdown episode 1 tanpa lokasi
→ HTTP 201/200 dan scene terbentuk. Uji dengan server lokal + SQLite sekali pakai
(contoh: `DATABASE_URL='sqlite+aiosqlite:////tmp/fix-smoke.db' uvicorn
app.main:app --port 8125`), lalu matikan servernya.

## CACAT 3 — Google Account Manager TIDAK PUNYA login Google beneran

- `POST /api/v1/google-accounts` langsung menandai status `connected` tanpa
  verifikasi apa pun ke Google. Tidak ada OAuth di mana pun di codebase
  (tanpa client_id/secret, tanpa authorize/callback).
- `POST /api/v1/google-accounts/{id}/sync` hanya menempel stempel `last_sync`
  (komentar kode sendiri mengakuinya).
- Perbaiki SESUAI spek awal (manual-first; JANGAN PERNAH simpan password Google;
  JANGAN bypass kuota/CAPTCHA): buat alurnya jujur — akun yang baru dibuat hanya
  dengan email TIDAK BOLEH berstatus `connected` (pakai `pending`/`disconnected`
  sampai data sesi yang valid ditempel); `sync` harus benar-benar memvalidasi
  sesi tersimpan dan melaporkan `expired`/`error` secara jujur bila tidak bisa
  diverifikasi — jangan pernah mengklaim connected secara diam-diam.
  JANGAN tambahkan login Google berbasis password. JANGAN tambahkan otomasi
  apa pun yang bypass kuota atau CAPTCHA Google.

Penerimaan: buat akun hanya dengan email → status BUKAN `connected`; sync pada
akun tanpa data sesi → tidak mengklaim sukses.

## CACAT 4 (minor) — Proses pytest tidak keluar setelah suite selesai

Diamati 2×: 40/40 tes lulus tapi proses pytest tetap hidup (harus di-kill manual).
Kemungkinan resource async/event loop tidak ditutup. Perbaiki agar
`pytest tests/ -q` keluar sendiri dengan bersih.

## VERIFIKASI AKHIR (wajib, dengan perintah nyata — bukan klaim)

1. `cd backend && ./venv/bin/python -m pytest tests/ -q` → 40 passed, proses keluar sendiri.
2. `cd frontend && npm run build` → exit 0.
3. Smoke test live singkat (server sekali pakai, SQLite /tmp, lalu matikan):
   daftar+login, buat proyek, generate series, breakdown TANPA lokasi → sukses.
4. Buat akun Google hanya dengan email → status bukan `connected`.

## SELESAI

Bila semua penerimaan lulus, tulis `FIX-REPORT.md` di direktori ini berisi:
apa yang diubah (file + baris), hasil tiap perintah verifikasi, dan apa yang
belum/tidak diperbaiki bila ada. Tambahkan juga bagian "Fixes applied" ke
`FINAL-REPORT.md`. Lalu berhenti.
