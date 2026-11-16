# MICRO DRAMA SAAS — FIX ROUND 2 (FRONTEND ONLY)

Kamu adalah agen perbaikan untuk proyek Micro Drama SaaS, kaki Hermes.
Direktori kerja KAMU: `/home/hatch/workspace/micro-drama-saas/hermes/`
JANGAN menulis file di luar direktori itu.

## Konteks

Ronde perbaikan pertama (FIX-REPORT.md) memperbaiki 3 dari 4 cacat dan
sudah terverifikasi: breakdown episode tanpa lokasi, kejujuran Google
Account Manager, dan pytest yang keluar sendiri. Yang TERSISA hanya:

**CACAT 1 — Frontend TIDAK BISA BUILD.**

- Build awal: 34 error (halaman import SelectContent/SelectItem/
  SelectTrigger/SelectValue ala Radix, tapi Select.tsx hanya export 1
  komponen native + import ganda di scenes/page.tsx).
- Ronde 1 menulis ulang Select.tsx. Hasilnya: error Select awal hilang,
  TAPI build sekarang gagal dengan **195 error TypeScript** (log lengkap:
  `logs/next-build-195-errors.log`).
- Penyebab utama: API Select baru tidak cocok dengan pemakaian halaman —
  contoh: halaman mengirim prop `placeholder` ke `<Select>`, tapi
  `SelectRootProps` baru tidak punya `placeholder`. Ada juga error di
  `src/lib/api.ts` dan `src/lib/project-store.ts` (cek apakah itu bawaan
  lama atau akibat rewrite Select — perbaiki semuanya, apa pun asalnya).

## Tugas (HANYA frontend)

1. Baca `logs/next-build-195-errors.log` sampai paham semua kelompok
   error. Kelompokkan: (a) Select API mismatch, (b) api.ts,
   (c) project-store.ts, (d) lain-lain.
2. Perbaiki dengan perubahan seminimal mungkin. Dua pendekatan yang
   sah — pilih yang paling sedikit mengubah kode:
   - (A) Lengkapi komponen Select supaya cocok dengan pemakaian halaman
     yang sudah ada (tambah prop yang dipakai halaman: `placeholder`,
     `value`, `onValueChange`, children `SelectItem`, dst.).
   - (B) Tulis ulang halaman yang memakai Select supaya cocok dengan
     Select native yang sederhana.
   Jangan campur keduanya sembarangan; satu pendekatan konsisten.
3. JANGAN ubah file backend apa pun. JANGAN ubah logika bisnis halaman.
   Hanya perbaiki supaya type-check lolos.
4. Sesudah tiap kelompok perbaikan, jalankan `npm run build` dan catat
   jumlah error yang tersisa. Ulangi sampai 0.
5. **Bekerja inkremental:** tiap kali satu kelompok error selesai,
   tulis progres ke `FIX2-PROGRESS.md` (kelompok apa, file apa, error
   tersisa berapa). Agen ronde 1 mati mendadak (exit 143) sebelum
   sempat menyelesaikan — file progres ini yang menyelamatkan kerjaan
   bila kamu ikut mati mendadak. JANGAN kerjakan semuanya di kepala
   tanpa menulis progres.
6. Bila satu error tidak bisa diperbaiki dengan cara bersih dalam
   3 percobaan, catat di FIX2-PROGRESS.md sebagai "blocked" dengan
   alasannya, lalu lanjut ke error lain. Jangan mentok di satu error.

## Penerimaan (WAJIB, tanpa kecuali)

- `cd frontend && npm run build` → **exit 0**, 0 error, halaman
  ter-generate semua.
- Backend TIDAK boleh rusak: `cd backend && ./venv/bin/python -m pytest tests/ -q`
  tetap 40 passed dan proses keluar sendiri.

## Sesudah selesai

1. Tulis `FIX2-REPORT.md`: apa yang diubah (file + alasan), hasil
   `npm run build` (exit 0), hasil pytest, dan sisa keterbatasan bila ada.
2. Tambah bagian "Fix round 2 (frontend)" di `FINAL-REPORT.md`.
3. Berhenti. Jangan lanjut mengerjakan hal lain.
