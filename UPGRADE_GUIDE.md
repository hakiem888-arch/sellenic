# Hotfix 2.0.1

Jika Anda sudah memasang versi 2.0, ekstrak paket ini, ganti hanya `modules/simple_ui.py` di proyek Anda, lalu restart aplikasi. Perbaikan memisahkan state pilihan kunci API dari state backend untuk mengatasi error `current_api_index cannot be modified after the widget is instantiated`. Pertahankan Secrets serta folder data Anda.

# Panduan upgrade Niche Hunter 2.0

Tanggal rilis paket: 14 Oktober 2026 (WIB).

## Memasang

1. Hentikan aplikasi lama. Cadangkan **seluruh folder `data/`**, file konfigurasi dan Secrets. Cadangan JSON juga tersedia di Studio → Ruang riset → Cadangan.
2. Ekstrak paket ini. Ganti kode proyek lama dengan kode baru; pertahankan folder `data/` serta Secrets milik Anda.
3. Gunakan Python 3.10+ dan lingkungan virtual. Dari folder yang berisi `app.py`, jalankan:

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m streamlit run app.py
```

Alternatif untuk memakai versi dependensi utama yang diuji: `python -m pip install -r requirements-tested.txt`. Berkas ini mematok dependensi utama, bukan seluruh dependensi transitif.

4. Masukkan API key di `.streamlit/secrets.toml` atau environment:

```toml
YOUTUBE_API_KEY = "isi_kunci_anda"
GEMINI_API_KEY = "isi_kunci_anda"
GROQ_API_KEY = "isi_kunci_anda"
```

Jangan menyalin teks contoh sebagai kunci nyata. YouTube API key diperlukan untuk data publik. Gemini dan Groq diperlukan hanya saat fitur AI terkait dijalankan. Tidak ada kredensial nyata dalam paket.

5. Untuk hosting, arahkan `NICHE_HUNTER_DATA_DIR` ke volume persisten. Gunakan instalasi privat satu pengguna seperti desain versi sebelumnya.

## Fitur baru dan cara mencoba

| Menu | Cara memakai | Yang dihasilkan |
|---|---|---|
| Riset → Keyword Lab | Isi 1–5 keyword, wilayah, usia video dan durasi; subscriber sendiri opsional | Perbandingan proksi peluang, rincian rumus, frasa, kandidat celah dan ekspor CSV |
| Riset → Radar kompetitor | Isi 1–4 ID channel atau @handle | Perbandingan sampel unggahan dan outlier dengan baseline sebanding |
| Riset → Rank Tracker | Tambahkan keyword + URL/ID video; pilih hingga 5 pelacakan lalu periksa | Riwayat posisi dalam 50 hasil API, grafik dan CSV |
| Studio → Kalender konten | Buat ide, tanggal, prioritas, catatan; ubah status saat produksi | Daftar produksi persisten, ekspor CSV dan tautan ke SEO Studio |
| Studio → Eksperimen CTR | Opsional: pratinjau dua judul/thumbnail. Isi impresi dan klik dari impresi masing-masing varian | CTR, interval Wilson, interval selisih, catatan desain dan riwayat eksperimen |
| Studio → Audit massal | Unduh template lalu unggah CSV ≤2 MB dan ≤200 video | Daftar masalah metadata serta urutan tindakan per video |

SEO Studio tetap dapat dipakai tanpa API. Audit kini menampilkan batas judul, deskripsi berbasis byte UTF-8, dan total tag. Skor relevansi dan kelayakan batas metadata adalah dua pemeriksaan berbeda.

## Data dan kompatibilitas

- Database `research.sqlite3` memakai tabel lama sehingga tidak perlu migrasi manual.
- Cadangan JSON baru menggunakan schema 2 dan mencakup watchlist, brief, riwayat riset, keyword, rank tracking, kalender, dan eksperimen.
- Pemulihan cadangan schema 1 masih didukung. Pemulihan menggabungkan data menurut ID, bukan menghapus seluruh database.
- Maksimal 30 riwayat riset dan 100 pengukuran posisi per pelacakan disimpan. Maksimal 20 pelacakan dikelola lewat UI.
- Gambar pratinjau thumbnail bersifat sementara dan tidak masuk cadangan eksperimen. Judul varian ikut disimpan.
- Database snapshot video tetap terpisah; cadangkan seluruh `data/` saat aplikasi berhenti untuk memindahkan snapshot juga.
- Fitur lama tetap tersedia. `ANALISIS_UI_UX.md` adalah catatan historis, bukan audit rilis 2.0.

## Membaca hasil secara benar

**Keyword Lab:** tidak menyediakan volume pencarian bulanan. Skor merupakan rumus internal dari sampel hasil pencarian. Skor personal hanya menambah konteks ukuran channel; bukan simulasi algoritma rekomendasi YouTube.

**Outlier:** rasio baru memakai VPH sejak publikasi di kedua sisi; peer berasal dari channel yang sama, kelompok durasi sama, usia 0,5–2 kali usia target, dan mengecualikan target. Minimal 3 peer dengan median positif. Tanpa cukup bukti, tidak ada kontribusi baseline. Penyamaan usia ini masih pendekatan; bukan pengukuran semua video pada jam kehidupan yang persis sama.

**Rank Tracker:** posisi hasil API dapat berbeda dari hasil personal penonton. Posisi kosong berarti video tidak ditemukan dalam sampel, bukan peringkat 51. Pemeriksaan berjalan ketika tombol dipilih; belum ada scheduler.

**Eksperimen:** input klik harus berasal dari impresi yang sama. Pergantian varian pada hari berbeda rentan perubahan audiens/traffic. Interval statistik berasumsi sampel binomial independen; CTR tinggi tidak otomatis berarti watch time atau kepuasan lebih tinggi. Ini alat analisis manual, bukan layanan rotasi varian.

## Penghematan dan penanganan API

Client publik baru memberi cache 5 menit, timeout koneksi/respons, satu retry untuk HTTP 429/5xx, pesan error tanpa URL/kunci, serta hitungan panggilan sesi. Pengambilan unggahan channel memakai uploads playlist; tidak menghabiskan panggilan pencarian untuk setiap baseline channel. Kuota aktual bergantung pada proyek Google dan kebijakan API terkini, bukan angka penggunaan sesi.

Daftar beberapa kunci lama tetap dapat dibaca, tetapi kunci tidak lagi diganti otomatis saat permintaan ditolak. Bila lebih dari satu kunci tersedia, pilih kunci aktif di Pengaturan dan bantuan. Kunci dalam satu proyek tidak menambah kuota proyek itu.

## Setelah pemasangan dengan kredensial Anda

1. Cari satu keyword, lalu pastikan judul, views, dan tautan beberapa hasil sesuai YouTube.
2. Coba satu channel di Radar kompetitor, satu video di Rank Tracker, dan satu permintaan AI.
3. Pastikan data yang disimpan tetap ada setelah aplikasi direstart pada volume yang sama.

57 tes otomatis dan startup HTTP telah lulus dalam lingkungan pengembangan. API nyata, rendering browser/perangkat seluler, serta deployment hosting Anda belum diverifikasi. Lihat `VALIDATION.md`.
