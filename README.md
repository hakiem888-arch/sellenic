# Niche Hunter 2.1 (Nexlev Edition) — riset, optimasi dan produksi konten

Versi 15 Oktober 2026 (WIB). Aplikasi riset YouTube pribadi berbasis Streamlit yang menggabungkan kemampuan riset keyword/outlier dengan seluruh rangkaian fitur riset & produktivitas bergaya [Nexlev](https://www.nexlev.io/) ([Chrome Extension](https://www.nexlev.io/chrome-extension)).

Mulai dari [UPGRADE_GUIDE.md](UPGRADE_GUIDE.md). Perbandingan lengkap dengan vidIQ, TubeBuddy, dan Nexlev ada di [COMPARISON_REPORT.md](COMPARISON_REPORT.md). Hasil pengujian ada di [VALIDATION.md](VALIDATION.md).

## Pemetaan Fitur Nexlev.io pada Niche Hunter 2.1

| Kategori Nexlev | Fitur Nexlev.io | Status di Niche Hunter | Lokasi Menu / Modul |
|---|---|---|---|
| **Video Research** | **Monetization Status** | **Ditambahkan (Baru)** | `Video → Monetization & Transkrip`, `Video Detail`, & `Channel → Analisis` |
| **Video Research** | **Videos Sort by Popularity** | **Ditambahkan (Baru)** | `Channel → Analisis → Performa dan video` (Urutkan: Terpopuler, VPH Tertinggi, Outlier, Terbaru, Terlama) |
| **Video Research / Productivity** | **Thumbnail Compressor** | **Ditambahkan (Baru)** | `Studio → Thumbnail Compressor` (Kompresi otomatis <2 MB standar YouTube dengan resolusi HD 1280×720) |
| **Video Research** | **Similar Thumbnail Search** | **Ditambahkan (Baru)** | `Video → Similar Thumbnail` (Perceptual hash + RGB histogram + tone/contrast matching) |
| **Video Research** | **Transcript Analysis** | **Ditambahkan (Baru)** | `Video → Monetization & Transkrip` (Skor Hook 30 detik pertama, WPM, struktur 4 kuartal, kata filler, frasa & chapter) |
| **Video Research** | **Video Outlier Score** | **Sudah Ada (Diperluas)** | `Video → Viral Intelligence`, `Riset → Radar kompetitor`, & `Channel → Analisis` |
| **Video Research** | **Video Views Per Hour (VPH)** | **Sudah Ada** | Tersedia di seluruh kartu/tabel video, `Viral Intelligence`, `Keyword Lab`, dan `Radar kompetitor` |
| **Niche Research** | **Search Term Analytics** | **Sudah Ada** | `Riset → Keyword Lab` & `Video → Pencarian → Analisis pasar` |
| **Niche Research** | **Channel Analytics Tab (Free & Pro)** | **Sudah Ada (Diperluas)** | `Channel → Analisis` & `Studio → Evaluasi channel` |
| **Niche Research** | **Similar Channels** | **Ditambahkan (Baru)** | `Channel → Similar Channels` (Ekstraksi DNA topik/tag channel & skor kemiripan multi-dimensi) |
| **Niche Research** | **Advanced Homepage Filter** | **Ditambahkan (Baru)** | `Video → Pencarian` & `Trending` (`Advanced Homepage Filter`: filter subscriber, rasio outlier, VPH, views, durasi, sembunyikan Shorts) |
| **Niche Research** | **Niche Overview / Niche Finder** | **Ditambahkan (Baru)** | `Riset → Niche Finder & Overview` (Skor Niche 0–100, Small-Channel Gems, kesiapan mid-roll, estimasi pendapatan & ekspor CSV/JSON) |
| **Niche Research** | **Subscriber Count** | **Sudah Ada** | Ditampilkan pada setiap kartu video, tabel pencarian, direktori, dan analisis channel |
| **Productivity** | **Automatic Ad Placer** | **Ditambahkan (Baru)** | `Studio → Automatic Ad Placer` (Generator titik iklan mid-roll otomatis untuk video ≥8 menit dengan penyelarasan jeda transkrip) |
| **Productivity** | **Net Profit Calculator** | **Ditambahkan (Baru)** | `Studio → Net Profit & Combined` (Kalkulator laba bersih: Gross AdSense + Sponsor dikurangi biaya produksi per video, langganan tools, bagi hasil & pajak) |
| **Productivity** | **Combined Analytics** | **Ditambahkan (Baru)** | `Studio → Net Profit & Combined` (Dasbor gabungan multi-channel: total subscriber, views, pangsa per channel, dan estimasi pendapatan gabungan) |
| **Productivity** | **Screenshot Analytics (Hide Sensitive Data)** | **Ditambahkan (Baru)** | `Studio → Screenshot Studio` (Ekspor kartu PNG analitik dengan mode privasi penyembunyian nama channel & pendapatan) |
| **Productivity** | **Channel Page Screenshot** | **Ditambahkan (Baru)** | `Studio → Screenshot Studio` & `Channel → Analisis → Monetisasi & Screenshot` |
| **Productivity** | **Video Performance Screenshot** | **Ditambahkan (Baru)** | `Studio → Screenshot Studio` (Kartu PNG performa video terbaru bergaya YouTube Studio / Nexlev) |

## Mulai

Gunakan Python 3.10 atau lebih baru, lalu jalankan dari direktori proyek:

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Tanpa kunci API, SEO Studio, brief dasar, watchlist, impor CSV, Thumbnail Compressor, Automatic Ad Placer, Net Profit Calculator, Combined Analytics, Transcript Analysis, dan Screenshot Studio tetap dapat dibuka dan digunakan. Riset data YouTube memerlukan kunci YouTube. Paket konten AI memerlukan Gemini.

Simpan kunci pada `.streamlit/secrets.toml`, pengaturan Secrets hosting, atau environment Anda:

```toml
YOUTUBE_API_KEY = "ISI_KUNCI_ANDA"
GEMINI_API_KEY = "ISI_KUNCI_ANDA"
GROQ_API_KEY = "ISI_KUNCI_ANDA"
```

## Pengujian

```bash
python -m unittest discover -s tests -v
```
