# Niche Hunter 2.1 (Nexlev Edition) — 15 Oktober 2026 (WIB)

- **Audit Fitur Nexlev.io**: Memetakan seluruh fitur pada referensi produk Nexlev.io (Video Research, Niche Research, dan Productivity). Fitur yang sudah ada (`Video Outlier Score`, `Video Views Per Hour`, `Search Term Analytics`, `Subscriber Count`, `Channel Analytics Tab`) dipertahankan dan diperluas; 12 fitur yang belum ada ditambahkan secara penuh di `modules/nexlev_engine.py` dan `modules/nexlev_ui.py`.
- **Monetization Status Checker**: Pemeriksaan indikator kelayakan monetisasi publik untuk video dan channel (ambang 1.000 subscriber YPP, 500 subscriber fan funding, volume views publik, kelayakan mid-roll ≥8 menit, pembatasan `madeForKids`, dan deteksi tautan afiliasi/sponsor pada deskripsi).
- **Videos Sort by Popularity**: Pengurutan sampel video pada halaman Analisis Channel berdasarkan `Terpopuler (Views Tertinggi)`, `VPH Tertinggi`, `Outlier Score Tertinggi`, `Terbaru`, dan `Terlama`.
- **Thumbnail Compressor**: Kompresi otomatis gambar thumbnail (JPEG/WebP/PNG) agar berada di bawah batas 2 MB YouTube (atau target KB pilihan) dengan tetap menjaga resolusi HD `1280×720`.
- **Similar Thumbnail Search**: Pencarian dan pemeringkatan kemiripan visual thumbnail menggunakan kombinasi perceptual average hash (`aHash`), histogram warna RGB 24-bin, serta kecerahan/kontras.
- **Transcript Analysis**: Analisis menyeluruh teks transkrip mencakup skor kualitas Hook pada 30 detik/75 kata pertama, kecepatan bicara (`WPM`), deteksi kata filler, pembagian struktur 4 kuartal, kata kunci/frasa teratas, dan ekstraksi chapter otomatis.
- **Similar Channels Finder**: Penemuan channel sejenis berdasarkan ekstraksi kata kunci DNA/tag channel referensi dan pemeringkatan kemiripan topik, ukuran subscriber, serta kecepatan views.
- **Advanced Homepage Filter**: Filter multi-kriteria langsung pada halaman Pencarian Video dan Trending (VPH minimum, rasio outlier Views/Subs minimum, batas maksimum subscriber channel, views minimum, durasi minimum, usia publikasi, kata wajib, dan opsi sembunyikan Shorts).
- **Niche Finder & Niche Overview**: Dasbor evaluasi kesehatan niche (`Niche Score 0–100`, `Personal Niche Score`, proporsi `Small-Channel Gems`, kesiapan iklan mid-roll, top channel di sampel, kandidat sub-niche, serta ekspor CSV/JSON).
- **Automatic Ad Placer**: Penyusun jadwal titik iklan mid-roll otomatis untuk video berdurasi ≥8 menit (480 detik) dengan penyelarasan otomatis pada jeda timestamp transkrip dan strategi kepadatan (`Konservatif`, `Seimbang`, `Agresif`).
- **Net Profit Calculator & Combined Analytics**: Kalkulator laba bersih channel (Gross AdSense + Sponsor + Afiliasi dikurangi biaya produksi per video, biaya bulanan tools, bagi hasil, dan pajak beserta titik impas views) serta penggabung analitik multi-channel dalam satu dasbor.
- **Screenshot Studio**: Generator kartu gambar PNG siap unduh untuk `Screenshot Analytics` (lengkap dengan Mode Privasi untuk menyembunyikan data sensitif/pendapatan/nama channel), `Channel Page Screenshot`, dan `Video Performance Screenshot`.

# Hotfix 2.0.1 — 14 Oktober 2026 (WIB)

- Memisahkan key widget `youtube_api_selector` dari state backend `current_api_index`.
- Callback pilihan kunci memperbarui state backend sebelum halaman dirender.
- Memperbaiki error Streamlit saat proses API menyimpan indeks setelah widget dibuat.

# Niche Hunter 2.0 — 14 Oktober 2026 (WIB)

- Enam mode baru: Keyword Lab, Radar kompetitor, Rank Tracker, Kalender konten, Eksperimen CTR dan Audit massal.
