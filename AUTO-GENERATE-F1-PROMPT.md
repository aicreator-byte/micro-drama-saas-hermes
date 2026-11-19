# AUTO-GENERATE Fase 1 — Backend (kaki Hermes)

**Peran:** kamu agen builder kaki Hermes. **Kontrol:** Muse (bukan kamu yang kontrol).
**Spek (Gate 1, disetujui Di 19 Nov 04:04):** `~/workspace/micro-drama-saas/AUTO-GENERATE-SPEC.md` — BACA DULU.
**Workspace kaki:** `~/workspace/micro-drama-saas/hermes/` (backend di `backend/app/api/`).

## Tugas (Fase 1, backend saja — JANGAN sentuh frontend)

Implementasi spek §5 (API job) + §4 (5 langkah) + §7 bagian backend, di kaki Hermes.

1. **API job:** `POST /projects/{id}/auto-generate` (body: judul/genre/jumlah episode/premis),
   `GET .../auto-generate/{job_id}` (status job + tiap langkah), `POST .../retry/{step}`.
   Job berurutan: 1 Series Bible → 2 Characters → 3 Locations → 4 Episodes → 5 Prompts.
   Langkah gagal → berikutnya TIDAK jalan; retry hanya langkah gagal.
2. **Langkah 2/3:** `generate_character_arcs` / `generate_world_building` — cek di kakimu
   apakah apply-nya bisa menulis Character/Location. Bila tidak (seperti OpenCode yang 400),
   buat jalur tulis baru ke tabel Character/Location. Default 4–6 karakter, 3–5 lokasi.
3. **Langkah 5 Prompts:** cek apakah kakimu sudah punya endpoint generate prompt; bila belum,
   buat (dari Scene Engine atau LLM langsung), simpan via CRUD prompt yang ada. Minimal
   1 prompt per episode.
4. **Idempotent:** jalan ulang job → skip yang sudah ada (jangan duplikat karakter/lokasi/episode).
5. **§7 backend:** akun demo "Test" (test@example.com) jangan jadi akun aktif default —
   periksa mekanisme seed di kakimu dan perbaiki. Counter Active Projects: bila definisi
   status ada di backend, samakan (bila murni frontend, catat untuk Fase 2).
6. Pakai LLM client + Story/Scene Engine yang SUDAH ADA di kaki. Key Nvidia dari env saja,
   JANGAN simpan key di DB.

## Larangan (§8 spek)

- JANGAN eksekusi video otomatis (Flow/Veo). JANGAN ubah auth/security. JANGAN ubah fallback
  akun Google. JANGAN ubah CRUD manual yang ada. JANGAN push ke GitHub. JANGAN hapus file.
  JANGAN sentuh kaki lain.

## Tes + laporan

- Suite pytest lama harus tetap lolos. Tambah tes auto-generate: buat job, langkah berurutan,
  retry langkah gagal, jalan ulang tanpa duplikat.
- Tulis laporan: `~/workspace/micro-drama-saas/hermes/AUTO-GENERATE-F1-REPORT.md` — file yang
  diubah, endpoint baru, hasil pytest (angka persis), apa yang NOT VERIFIED.
- Bila terblokir (dependensi hilang, tes lama gagal dari sananya), catat di laporan dan
  hentikan item itu — jangan looping.
