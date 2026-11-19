# AUTO-GENERATE Fase 2 — Frontend Report (kaki Hermes)

**Tanggal:** 19 Nov 2026. **Spek:** `~/workspace/micro-drama-saas/AUTO-GENERATE-SPEC.md` §6.
**Status:** SELESAI (frontend saja — backend TIDAK disentuh, kaki lain TIDAK disentuh, TIDAK push GitHub).

## Yang dibangun

Tombol Auto-Generate + modal input + progres 5 langkah + retry per langkah, memakai
komponen UI yang sudah ada (Modal, Button, Input, Textarea, Badge) dan pola yang sama
dengan halaman lain di kaki ini.

### Penempatan tombol (keputusan dengan alasan, terverifikasi)

Brief minta tombol di "halaman detail proyek, dekat Story Engine". **Halaman itu TIDAK
ADA di kaki Hermes** — terverifikasi: `src/app/dashboard/projects/` hanya berisi
`page.tsx` (daftar) + direktori `new/` yang KOSONG (0 file); tidak ada rute
`[id]/page.tsx`. Tabel rute hasil `next build` mengonfirmasi: tidak ada
`/dashboard/projects/[id]` maupun `/dashboard/projects/new` (tautan "Open project" dan
"New Project" di kaki ini saat ini mengarah ke rute yang tidak ada — temuan lama, bukan
dari pekerjaan ini, lihat § "Temuan lama").
Mengikuti alternatif spek §6 ("dan/atau kartu proyek dashboard"), tombol dipasang di
**kartu proyek di halaman Projects** (`/dashboard/projects`).

## File yang diubah / dibuat

**Dibuat:**
- `frontend/src/components/AutoGenerateModal.tsx` — modal + form + progres + retry.
  Form: judul (wajib, terisi judul proyek), genre, jumlah episode (1–50, default 30),
  premis (opsional). Submit → `POST /auto-generate` (backend jalan sinkron, jadi
  respons POST umumnya sudah final); bila status masih pending/running, polling
  `GET .../auto-generate/{job_id}` tiap 2 detik sampai terminal. Tiap langkah tampil
  nama + status + ringkasan hasil + pesan error; langkah gagal punya tombol Retry
  (`POST .../retry/{step_key}`). Job selesai → tautan "Lihat hasil" ke Series Bible /
  Characters / Locations / Episodes / Prompts (lebih dulu `setCurrentProject` agar
  halaman-halaman itu membuka proyek yang benar) + tombol Done (tutup → refresh daftar).
  Modal tidak bisa ditutup selagi job berjalan (tombol/overlay/Escape diblokir + ada
  catatan) agar tampilan progres tidak hilang di tengah jalan.

**Diubah:**
- `frontend/src/types/index.ts` — tipe baru: `AutoGenerateJobStatus`,
  `AutoGenerateStepStatus`, `AutoGenerateCreate`, `AutoGenerateStep`, `AutoGenerateJob`
  (bentuk respons disalin dari skema Pydantic Fase 1).
- `frontend/src/lib/api.ts` — 3 method baru: `createAutoGenerateJob`,
  `getAutoGenerateJob`, `retryAutoGenerateStep` (base URL `/api/v1` yang sudah ada).
- `frontend/src/app/dashboard/projects/page.tsx` — tombol Sparkles "Auto-Generate" di
  tiap kartu proyek + render `<AutoGenerateModal>`. CRUD manual lain tidak diubah.

**TIDAK diubah:** backend, auth/security, fallback Google, Flow Bridge, kaki lain.

## Kontrak endpoint (dicek statis terhadap backend)

Ketiga path + bentuk respons dicocokkan langsung dengan
`backend/app/api/auto_generate.py` dan `backend/app/main.py` (router di-mount di
`API_V1_PREFIX` = `/api/v1`, sama dengan `NEXT_PUBLIC_API_URL` frontend):
`POST /projects/{id}/auto-generate` (201), `GET /projects/{id}/auto-generate/{job_id}`,
`POST /projects/{id}/auto-generate/{job_id}/retry/{step_key}`. Step key:
`series_bible, characters, locations, episodes, prompts` (urutan 1–5).

## §7.2 — counter "Active Projects" vs badge "Active"

**TIDAK BERLAKU di kaki Hermes.** Terverifikasi dengan grep seluruh `frontend/src/`:
tidak ada teks "Active Projects" maupun badge berlabel "Active" di mana pun.
Dashboard menampilkan "Projects" = total proyek (`response.total`), dan badge di kartu
proyek menampilkan status mentah (`draft` / `in_production` / `completed` / `archived`).
Tidak ada dua definisi yang bertentangan, jadi tidak ada yang disamakan — keanehan yang
Di lihat ada di kaki OpenCode, bukan di sini. Tidak ada counter baru yang ditambahkan
(YAGNI).

## Cara pakai (alur klik)

1. Buka `/dashboard/projects`, klik ikon **Sparkles** di kartu proyek.
2. Isi judul (wajib) / genre / jumlah episode / premis → **Start Auto-Generate**.
3. Tunggu — 5 langkah tampil satu per satu (pending → running → completed/failed).
4. Bila satu langkah gagal, klik **Retry** di langkah itu saja.
5. Selesai → klik tautan hasil (Series Bible / Characters / Locations / Episodes /
   Prompts) untuk melihat data terisi, atau **Done** untuk kembali ke daftar.

## Hasil verifikasi (angka persis)

- `npx tsc --noEmit`: **0 error**.
- `npx eslint` pada 4 file yang saya ubah/buat (`--quiet`): **0 error, 0 warning**.
  Repo ini secara keseluruhan punya 21 error lint lama; 1 error di
  `projects/page.tsx` (`react-hooks/immutability` pada `loadProjects`) sudah ada
  sebelum pekerjaan ini — dibuktikan: file versi HEAD (sebelum perubahan saya)
  menghasilkan error yang sama persis (1 error, baris yang sama). Bukan regresi saya.
- `npm run build` (Next.js 16.4.6, Turbopack): **compiled successfully (22,9 dtk)**,
  TypeScript selesai, **20/20 halaman** ter-generate. Tidak ada rute baru yang dibuat
  (modal, bukan halaman).
- Perbaikan selama kerja: 2 error lint awal di `AutoGenerateModal.tsx`
  (`react-hooks/set-state-in-effect`, aturan React 19.2) diperbaiki dengan pola
  "adjust state during render" yang didokumentasikan React (reset form saat modal
  dibuka) + dependensi effect polling diluruskan; setelah itu scoped lint bersih.

## Temuan lama (bukan dari pekerjaan ini, dicatat untuk Fase 3)

- Rute `/dashboard/projects/[id]` (halaman detail proyek) **tidak ada** — tautan "Open
  project" di kartu proyek + "Open Project" di dashboard mengarah ke 404. Ini juga
  alasan tombol Auto-Generate dipasang di kartu, bukan di halaman detail.
- Rute `/dashboard/projects/new` **tidak ada** (direktori kosong) — tombol "New Project"
  (dashboard + halaman Projects) mengarah ke 404; pembuatan proyek hanya jalan lewat
  modal "Create New Project" di halaman Projects.
- Keduanya di luar scope Fase 2 (brief melarang ubah CRUD manual) — tidak diperbaiki.

## NOT VERIFIED

- **Uji klik manual di browser** (itu Fase 3): alur di atas baru terverifikasi lewat
  typecheck/lint/build + pencocokan kontrak statis, belum diklik di server berjalan.
- **Job terhadap backend nyata + LLM nyata** (Fase 3): tidak ada panggilan HTTP nyata
  yang dilakukan selama Fase 2.
- **Kualitas konten hasil generate** (Fase 3).
