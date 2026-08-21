# \U0001F3E0 Dasbor Komparasi Rumah

Aplikasi Streamlit untuk membandingkan beberapa pilihan rumah sebelum membeli:

- **Peta interaktif** — semua rumah tampil sebagai marker; klik marker untuk melihat detail.
- **Tab Survey** — jadwalkan kunjungan survey per rumah, isi kuisioner penilaian (kondisi bangunan, lingkungan, dll), dan lihat rekap skor/kesimpulan tiap rumah.
- **Kalkulator KPR** — simulasi cicilan bulanan berdasarkan harga, uang muka, tenor, dan suku bunga.
- **Tab Komparasi** — bandingkan beberapa rumah berdampingan: harga, spesifikasi, dan skor survey, lengkap dengan grafik.
- **Tab Kelola Data** — tambah, edit, atau hapus data rumah lewat form (tersimpan otomatis ke `data/houses.json`).
- **Sinkronisasi Google Sheets (opsional)** — backup / bagikan data ke Google Sheets sendiri, dua arah (push & pull).
- **Mode Aplikasi Desktop (opsional)** — jalankan sebagai jendela aplikasi tersendiri, tinggal double-click ikon, tanpa perlu buka VSCode/browser setiap hari.

## 1. Struktur Folder

```
rumah-dashboard/
├── app.py                        # Aplikasi utama (jalankan file ini)
├── desktop_app.py                # Launcher mode aplikasi desktop (opsional)
├── Buka Dasbor Rumah.bat         # Double-click untuk buka mode desktop (Windows)
├── Buka Dasbor Rumah (debug).bat # Sama seperti di atas, tapi menampilkan pesan error
├── utils.py                      # Fungsi bantuan: data, format, skor survey, KPR
├── sheets_utils.py               # Fungsi integrasi Google Sheets (opsional)
├── requirements.txt              # Daftar library yang dibutuhkan
├── data/
│   └── houses.json               # Data rumah + riwayat survey (5 contoh data)
├── images/                       # (opsional) taruh foto rumah lokal di sini
├── videos/                       # (opsional) taruh video rumah lokal di sini
└── .streamlit/
    ├── config.toml               # Tema warna aplikasi
    └── secrets.toml.example      # Contoh format kredensial Google Sheets
```

## 2. Cara Menjalankan di VSCode

**Prasyarat:** Python 3.9+ sudah terpasang, dan ekstensi *Python* di VSCode.

1. Buka folder `rumah-dashboard` ini di VSCode (`File > Open Folder...`).
2. Buka terminal di VSCode (`Terminal > New Terminal`).
3. Buat virtual environment (opsional tapi disarankan):
   ```bash
   python -m venv venv
   ```
4. Aktifkan virtual environment:
   - **Windows:** `venv\Scripts\activate`
   - **Mac/Linux:** `source venv/bin/activate`
5. Install semua library yang dibutuhkan:
   ```bash
   pip install -r requirements.txt
   ```
   > Baris `gspread` dan `google-auth` di `requirements.txt` hanya dipakai untuk fitur sinkronisasi Google Sheets. Boleh dihapus dari file itu kalau Anda tidak memakai fitur tersebut.
6. Jalankan aplikasi:
   ```bash
   streamlit run app.py
   ```
7. Browser akan terbuka otomatis di `http://localhost:8501`. Jika tidak, buka URL tersebut secara manual.

Jika port 8501 sudah dipakai aplikasi lain:
```bash
streamlit run app.py --server.port 8502
```

## 3. Mode Aplikasi Desktop (Tanpa Buka VSCode Lagi)

Setelah setup awal (bagian 2) selesai satu kali, Anda bisa menjalankan aplikasi ini setiap hari lewat **satu klik ikon** — muncul sebagai jendela aplikasi sendiri (tanpa address bar/tab browser), dan tidak perlu membuka VSCode/terminal lagi.

Cara ini memakai mode "--app" bawaan Microsoft Edge/Google Chrome untuk menampilkan Streamlit tanpa tampilan browser biasa — **tidak butuh library tambahan apa pun** di luar `requirements.txt` yang sudah ada, dan tidak perlu instalasi khusus lain karena Edge sudah terpasang bawaan di Windows 10/11.

### Setup (dilakukan sekali saja, lewat VSCode)

Cukup pastikan Anda sudah menyelesaikan langkah 1–5 di bagian 2 (virtual environment aktif, `pip install -r requirements.txt` sudah dijalankan). Tidak ada langkah tambahan lain.

### Pemakaian sehari-hari

- Cukup **double-click** file **`Buka Dasbor Rumah.bat`** di folder ini. Jendela aplikasi akan terbuka dalam beberapa detik (server Streamlit menyala otomatis di baliknya, tanpa jendela hitam/console yang terlihat).
- Supaya terasa seperti ikon aplikasi sungguhan: klik kanan file `.bat` tersebut → **Send to > Desktop (create shortcut)**. Shortcut baru muncul di Desktop — klik kanan shortcut itu → **Properties > Change Icon...** untuk memberinya ikon rumah/kustom. Selanjutnya tinggal double-click ikon itu dari Desktop.
- Untuk menutup aplikasi, tutup jendelanya seperti aplikasi biasa (klik tombol X).

### Kalau ada masalah

- Jendela tidak muncul / langsung tertutup → jalankan **`Buka Dasbor Rumah (debug).bat`** sebagai gantinya; file ini membuka jendela terminal yang menampilkan pesan error secara langsung.
- Bisa juga cek file `desktop_app.log` dan `streamlit_server.log` yang otomatis dibuat di folder ini setelah aplikasi dijalankan — berisi catatan proses & error (jika ada).
- Jika Edge maupun Chrome tidak ditemukan di komputer Anda, aplikasi otomatis dibuka sebagai tab biasa di browser default — tetap berfungsi, hanya tampilannya bukan mode "app" tanpa address bar.
- Data yang ditambahkan lewat mode desktop tetap tersimpan ke `data/houses.json` di folder ini, sama seperti mode browser biasa.

> **Catatan:** mode ini menjalankan Streamlit secara lokal di komputer Anda (butuh Python & library sudah terpasang) — bukan file `.exe` yang berdiri sendiri tanpa Python sama sekali. Peta dan foto/tile online tetap membutuhkan koneksi internet seperti biasa (ini normal untuk semua aplikasi peta); data rumah, kuisioner survey, dan seluruh isi aplikasi lainnya tetap berfungsi penuh secara offline.
>
> Ingin file `.exe` tunggal yang bisa dibagikan ke orang lain **tanpa Python terpasang sama sekali**? Itu bisa dibuat lewat *PyInstaller*, tapi prosesnya lebih rumit dan perlu diuji langsung di komputer Windows (karena packaging Streamlit dengan PyInstaller kadang butuh penyesuaian tambahan). Beri tahu saya kalau Anda ingin saya siapkan panduan/skripnya.

## 4. Mengelola Data Rumah

**A. Lewat aplikasi (disarankan)** — buka tab **"➕ Kelola Data"** untuk tambah/edit/hapus rumah lewat form. Tersimpan otomatis ke `data/houses.json`.

**B. Edit langsung file JSON** — buka `data/houses.json` di VSCode. Field utama per rumah:

| Field | Keterangan |
|---|---|
| `nama`, `alamat` | Nama listing & alamat lengkap |
| `latitude`, `longitude` | Koordinat lokasi |
| `harga` | Angka penuh, contoh `1850000000` untuk Rp 1,85 M |
| `status` | `Survey`, `Nego`, `Deal`, `Pertimbangan`, atau `Batal` |
| `luas_tanah`, `luas_bangunan` | Meter persegi |
| `kelebihan`, `kekurangan` | List teks (poin-poin) |
| `gambar` | List URL gambar atau path lokal |
| `video` | URL video atau path lokal, boleh `""` |
| `survey_records` | List riwayat jadwal & hasil kuisioner survey (dikelola lewat tab Survey, tidak perlu diedit manual) |

### Cara mendapatkan koordinat
1. Buka [Google Maps](https://maps.google.com), cari lokasi rumah.
2. Klik kanan pada titik lokasi persis.
3. Klik angka koordinat yang muncul (otomatis tersalin), contoh: `-6.301640, 106.653500`.
4. Angka pertama = `latitude`, angka kedua = `longitude`.

## 5. Tab Survey — Jadwal & Kuisioner

1. Pilih rumah, lalu isi form **"Jadwalkan Survey Baru"** (tanggal, surveyor/PIC).
2. Setelah survey benar-benar dilakukan, buka jadwal tersebut dan isi **Kuisioner Survey**: penilaian 1–5 untuk kondisi bangunan, lingkungan, akses jalan, dll, plus catatan bebas.
3. Aplikasi otomatis menghitung **skor rata-rata** dan menyarankan **kesimpulan** (Layak Dilanjutkan / Masih Dipertimbangkan / Tidak Layak) — Anda tetap bisa mengubahnya secara manual sesuai penilaian Anda sendiri.
4. Rekap skor semua rumah tampil di bagian bawah tab Survey, dan otomatis ikut muncul di tab **Komparasi** serta panel detail peta.

## 6. Kalkulator KPR

Masukkan harga rumah, persentase/uang muka, tenor (tahun), dan suku bunga tahunan untuk melihat estimasi cicilan bulanan (metode anuitas). Berguna untuk mengecek apakah cicilan tiap kandidat rumah sesuai budget bulanan Anda.

## 7. Mengganti Gambar & Video

Data contoh memakai foto stok Unsplash sebagai **placeholder** — silakan ganti dengan foto rumah asli. Ada tiga cara mengisi field `gambar` (foto, boleh lebih dari satu URL) dan `video`:

**A. Link Google Drive (paling praktis kalau foto/video sudah ada di Drive)**
1. Di Google Drive, klik kanan file foto/video → **Bagikan (Share)**.
2. Ubah akses jadi **"Siapa saja yang memiliki link" (Anyone with the link)**, peran **Viewer**.
3. Klik **Salin link**, tempel apa adanya ke field `gambar` atau `video` di tab "Kelola Data" — tidak perlu diedit/dipotong, aplikasi otomatis mendeteksi & mengonversinya.
   > Catatan: karena aksesnya "siapa saja dengan link", foto/video tersebut bisa dilihat siapa pun yang punya link-nya (tapi tidak muncul di pencarian Drive publik). Jangan pakai cara ini untuk foto/dokumen sensitif.
4. Untuk video, tampilannya berupa pemutar video Google Drive yang ditanam langsung di halaman (bukan file diunduh).

**B. URL online biasa** — tempel langsung link gambar/video dari internet (mis. hasil upload ke Imgur, YouTube, dsb) di field `gambar` / `video`.

**C. File lokal di komputer** — taruh file di folder `images/` atau `videos/`, lalu isi field dengan path relatif, contoh `"images/rumah1-depan.jpg"` atau `"videos/rumah1-tour.mp4"`. Cocok untuk mode offline karena tidak butuh internet untuk menampilkannya.

## 8. Integrasi Google Sheets (Opsional)

Fitur ini memakai **Service Account** Google Cloud agar aplikasi bisa membaca/menulis ke spreadsheet Anda tanpa login manual tiap kali dibuka.

### Langkah pengaturan

1. **Buat project & aktifkan API**
   - Buka [Google Cloud Console](https://console.cloud.google.com/) → buat project baru (atau pakai yang sudah ada).
   - Aktifkan **Google Sheets API** dan **Google Drive API** (menu *APIs & Services > Library*).
2. **Buat Service Account**
   - Menu *APIs & Services > Credentials* → *Create Credentials* → *Service Account*.
   - Beri nama bebas, klik *Create and Continue*, lalu *Done*.
3. **Buat kunci JSON**
   - Buka service account yang baru dibuat → tab *Keys* → *Add Key* → *Create new key* → pilih **JSON** → unduh filenya.
4. **Bagikan Google Sheet ke Service Account**
   - Buat/gunakan Google Sheet kosong, salin **ID atau URL**-nya.
   - Buka file JSON yang diunduh, salin nilai `client_email` (formatnya seperti `xxxx@xxxx.iam.gserviceaccount.com`).
   - Di Google Sheet, klik *Share* → tempel email tersebut → beri akses **Editor**.
5. **Isi `secrets.toml`**
   - Salin `.streamlit/secrets.toml.example` menjadi `.streamlit/secrets.toml`.
   - Buka file JSON yang diunduh, pindahkan tiap nilainya ke field yang sesuai di `secrets.toml` (terutama `private_key`, `client_email`, `project_id`, dll).
   - Isi `sheet_id` dengan ID/URL Google Sheet dari langkah 4.
   - **Jangan** membagikan atau meng-commit file `secrets.toml` ini — sudah otomatis diabaikan lewat `.gitignore`.
6. **Install dependency tambahan** (jika belum): `pip install gspread google-auth`, lalu jalankan ulang `streamlit run app.py`.
7. Buka tab **"☁️ Sinkronisasi"** di aplikasi — gunakan tombol **Push** untuk mengirim data lokal ke Sheets, atau **Pull** untuk menarik data dari Sheets (menimpa data lokal).
8. Setelah kredensial & `sheet_id` terisi, aplikasi otomatis menarik data dari Sheets ini **setiap kali pertama kali dibuka** (bukan cuma saat klik Pull manual) — lihat indikator "📡 Data dimuat dari Google Sheets" di sidebar untuk memastikan ini aktif. Ini penting terutama untuk deployment di cloud (lihat bagian 9), karena membuat data tidak hilang saat server restart.

## 9. Deploy ke Internet Lewat GitHub (Bisa Diakses dari HP)

Repo ini sudah siap deploy ke **Streamlit Community Cloud** (gratis) lewat GitHub — begitu online, tinggal buka URL-nya di browser HP, tanpa install apa pun.

1. **Unggah ke GitHub** — buat repository baru di [github.com](https://github.com), lalu di terminal VSCode (folder project ini):
   ```bash
   git init
   git add .
   git commit -m "Dasbor Komparasi Rumah"
   git branch -M main
   git remote add origin https://github.com/USERNAME/NAMA-REPO.git
   git push -u origin main
   ```
   `.gitignore` sudah menyaring `venv/`, `secrets.toml`, dan file log supaya tidak ikut ter-upload.
2. Buka **[share.streamlit.io](https://share.streamlit.io)**, masuk pakai akun GitHub.
3. Klik **New app** → pilih repo & branch `main` → isi **Main file path** dengan `app.py`.
4. **Kalau memakai Google Sheets** (sangat disarankan untuk versi cloud — lihat kenapa di bawah): sebelum deploy, buka **Advanced settings > Secrets**, salin-tempel seluruh isi `.streamlit/secrets.toml` Anda ke sana.
5. Klik **Deploy**. Setelah build selesai (1–3 menit), Anda dapat URL publik seperti `nama-app.streamlit.app` — buka dari HP, langsung bisa dipakai.

**Kenapa sebaiknya pakai Google Sheets untuk versi cloud:** penyimpanan file (`data/houses.json`) di Streamlit Community Cloud bersifat **sementara** — begitu server restart (misalnya karena tidak diakses beberapa hari, atau Anda push kode baru), data yang ditambahkan lewat aplikasi bisa hilang dan kembali ke data contoh. Dengan Google Sheets sudah dikonfigurasi (bagian 8), aplikasi otomatis **menarik data terbaru dari Sheets setiap kali dibuka** — jadi Sheets berfungsi sebagai penyimpanan permanennya. Ingat klik **Push** di tab Sinkronisasi setelah menambah/mengubah data penting, supaya tersimpan ke Sheets dan tidak hilang.

**Tips lain untuk versi cloud:**
- Pakai link **Google Drive** atau URL online untuk foto/video (bukan path lokal seperti `images/rumah1.jpg`), karena server cloud tidak bisa mengakses file di komputer Anda — lihat bagian 7.
- File `desktop_app.py` dan `.bat` tidak dipakai di cloud (itu khusus mode desktop lokal) — boleh dibiarkan ikut ter-upload, tidak mengganggu.

## 10. Troubleshooting

- **`ModuleNotFoundError`** → jalankan ulang `pip install -r requirements.txt` (pastikan virtual environment aktif).
- **Peta tidak muncul / kosong** → pastikan koneksi internet aktif (tile peta & Google Fonts dimuat online).
- **Gambar tidak muncul** → URL contoh (Unsplash) butuh koneksi internet; gunakan file gambar lokal untuk mode offline (lihat bagian 7).
- **Gambar/video dari Google Drive tidak muncul** → pastikan akses share filenya sudah "Siapa saja yang memiliki link" (bukan "Dibatasi"/Restricted) — kalau masih private, aplikasi tidak akan bisa menampilkannya walau link sudah benar.
- **Port sudah dipakai** → jalankan dengan `--server.port <nomor lain>`.
- **Tab Sinkronisasi menampilkan error kredensial** → pastikan `.streamlit/secrets.toml` sudah dibuat dan diisi sesuai bagian 8, serta email service account sudah diberi akses Editor di Sheet tujuan.
- **`gspread.exceptions.APIError` / permission denied** → cek kembali bahwa Google Sheets API & Drive API sudah diaktifkan di Cloud Console, dan Sheet sudah dibagikan ke `client_email` yang benar.
- **Data awal tidak sesuai isi Google Sheets** → cek indikator sumber data di sidebar. Kalau tertulis "Data dimuat dari file lokal" padahal Sheets sudah dikonfigurasi, berarti kredensial/`sheet_id` belum lengkap atau worksheet "Rumah" belum ada di Sheet tujuan — buka tab Sinkronisasi untuk melihat detail errornya, atau klik **Push** sekali dari data lokal untuk membuat worksheet-nya otomatis.
- **Mode desktop: jendela tidak muncul / langsung hilang** → jalankan `Buka Dasbor Rumah (debug).bat`, baca pesan error di jendela terminal yang muncul, atau cek file `desktop_app.log` dan `streamlit_server.log`. Aplikasi otomatis mengecek kelengkapan library sebelum menyala — kalau ada yang belum terpasang, akan muncul jendela pesan berisi path Python yang dipakai beserta perintah `pip install` yang perlu dijalankan persis seperti itu (supaya dijamin memakai Python yang sama, bukan Python lain yang mungkin terinstal di komputer Anda).
