# Micro Drama SaaS — Mobile App (React Native / Expo)

Scaffold layar utama yang jalan: login, daftar proyek, detail proyek,
trigger Auto-Generate + polling progres per langkah (sama seperti web).

## Menjalankan

```bash
cd mobile
npm install
# Backend Hermes harus jalan (default di laptop: http://localhost:8001)
# Emulator Android pakai 10.0.2.2 (sudah default EXPO_PUBLIC_API_URL).
# HP fisik: samakan LAN, lalu:
EXPO_PUBLIC_API_URL=http://<IP-LAPTOP>:8001/api/v1 npx expo start
# lalu scan QR dengan Expo Go.
npm run typecheck   # tsc --noEmit
```

## Yang belum terverifikasi

- **Belum dijalankan di Expo Go / emulator** (tidak ada emulator di VM ini).
  Kode terverifikasi hanya lewat `tsc --noEmit` + review terhadap API
  backend yang sama dengan web (`/projects`, `/projects/{id}/auto-generate`).
- Ikon `assets/icon.png` belum ada — ganti dengan ikon sendiri sebelum
  build store; Expo memakai placeholder bila tidak ada.

## Catatan

- Token login disimpan di AsyncStorage (`access_token`), sama seperti
  web memakai localStorage.
- Auto-generate di mobile memicu job yang sama dengan web (POST 202,
  polling GET tiap 2 detik). Hasil lengkap (bible/karakter/episode)
  dilihat di web.
- Endpoint timeline/kolaborasi/billing/subtitle belum ada layarnya di
  mobile — scope scaffold ini: proyek + auto-generate.
