# Analisis Niche Hunter vs vidIQ vs TubeBuddy

**Tanggal penilaian:** 14 Oktober 2026 (WIB). **Dasar audit:** kode dalam `niche-hunter-main.rar`, 29 tes bawaan, serta dokumentasi resmi produk dan YouTube yang ditelusuri pada sesi ini. Perbandingan fitur vendor berdasarkan dokumentasi publik, bukan pengujian akun berbayar. Ketersediaan fitur dapat bergantung pada paket.

## Penilaian utama

Niche Hunter sudah merupakan aplikasi riset yang cukup luas, bukan sekadar pencari keyword. Versi awal memiliki 10 mode: pencarian, trending, Viral Intelligence, direktori, analisis dan perbandingan channel, perbandingan artis, SEO Studio, ruang riset, serta evaluasi channel dari CSV. Kelebihannya adalah alur berbahasa Indonesia, riset artis, penyimpanan lokal, rubrik yang bisa diperiksa, dan kode yang bisa Anda ubah sendiri.

Persamaannya dengan kedua produk mencakup riset keyword/video, pengamatan kompetitor, audit metadata, ide konten berbantuan AI, dan analisis performa. Persamaan nama fitur belum berarti kesetaraan kemampuan. vidIQ menghubungkan keyword, outlier, kompetitor, ide dan optimasi; TubeBuddy menonjolkan SEO, pelacakan peringkat, eksperimen dan pekerjaan massal yang terintegrasi dengan YouTube Studio. [S1–S8]

Kelemahan terpenting Niche Hunter awal berada pada kualitas perbandingan metrik, kesinambungan alur kerja, cakupan data, dan otomatisasi. Sebagian bisa diperbaiki langsung dalam kode. Layanan data vendor, akses analytics privat, dan sistem eksperimen terintegrasi memerlukan integrasi/operasi tambahan; skor buatan tidak dapat menggantikan data yang tidak tersedia.

## Persamaan, perbedaan dan perubahan yang sudah diterapkan

| Area | vidIQ | TubeBuddy | Niche Hunter sebelum audit | Hasil upgrade 2.0 |
|---|---|---|---|---|
| Riset keyword | Estimasi volume, kompetisi, tren dan keyword terkait [S1] | Keyword Explorer dan konteks persaingan [S2] | Autocomplete, frekuensi kata dan hasil pencarian; tidak ada ruang perbandingan keyword khusus | Keyword Lab: hingga 5 keyword, filter, frasa, kandidat celah, ekspor dan penyimpanan |
| Konteks channel sendiri | Riset/optimasi terhubung dengan channel [S1,S3] | Alur keyword dan SEO channel [S2,S5] | Belum ada proksi peluang personal dalam perbandingan keyword | Subscriber sendiri opsional; rumus personal dan keterbatasannya ditampilkan |
| Outlier/breakout | Outliers memakai performa relatif baseline channel serta filter [S3] | Analisis kompetitor/niche tersedia [S8] | Sudah ada, tetapi baseline campur usia/durasi dan metrik interval/lifetime | Target dikeluarkan; peer channel/durasi sama, usia sebanding, minimum 3 video; lifetime dibanding lifetime |
| Kompetitor | Pelacakan performa dan video unggulan [S4] | Analisis kompetitor melalui Insights [S8] | Perbandingan channel, sampel unggahan dan tag | Radar hingga 4 channel, masing-masing sampai 50 unggahan, filter usia/durasi, tabel outlier dan CSV |
| Posisi pencarian | Keyword tracking [S1] | Rank Tracking [S6] | Belum ada riwayat posisi keyword-video | Rank Tracker dengan wilayah/bahasa, histori 100 pengukuran, grafik dan CSV |
| SEO metadata | Optimasi judul/deskripsi/metadata [S11] | SEO Studio terintegrasi [S5] | Audit leksikal dan brief sudah ada | Pemeriksaan batas judul, byte deskripsi, panjang tag, duplikasi tag dan pengulangan keyword |
| Produksi konten | Ide, skrip dan alat optimasi terkait [S11] | Ide dan alur produksi terkait [S8] | Brief dan watchlist tanpa status/tanggal produksi | Kalender dengan 5 status, tanggal, prioritas, catatan, ekspor dan handoff ke SEO |
| Judul/thumbnail | Alat thumbnail dan optimasi [S3,S11] | Analisis thumbnail dan A/B metadata [S2,S7] | Ide AI dan unduh thumbnail | Pratinjau A/B lokal serta penyimpanan judul varian; tidak ada klaim prediksi visual |
| Eksperimen | Rujukan penemuan/optimasi yang dibaca tidak cukup untuk mengklaim detail mekanisme A/B vendor | Dokumentasi menjelaskan rotasi metadata per 24 jam [S7] | Belum ada analisis eksperimen | Analisis CTR manual dengan interval Wilson dan selisih; catatan desain serta riwayat |
| Pekerjaan massal | Rekomendasi optimasi video [S11] | Toolkit bulk/workflow terintegrasi [S8] | Audit satu video | Audit CSV sampai 200 video; ekspor masalah dan tindakan. Belum menulis massal ke YouTube |
| Analytics privat | Ekosistem audit channel dan alat terhubung [S11] | Analytics dan workflow channel [S8] | Impor CSV YouTube Studio | Impor CSV dipertahankan. OAuth analytics otomatis belum diimplementasikan |
| Ekstensi/operasi layanan | Ekstensi dan layanan web [S4] | Integrasi YouTube Studio [S5,S8] | Aplikasi Streamlit pribadi | Tetap aplikasi pribadi; belum menjadi ekstensi, layanan multiuser, atau pemantau 24 jam |

## Temuan kode yang diperbaiki

1. **Perhitungan VPH channel salah basis.** Kode sebelumnya mengubah angka views menjadi teks `K/M`, lalu mem-parsing kembali teks dan membaginya dengan 24 tanpa memakai usia masing-masing video. Sekarang statistik tetap numerik dan median VPH dihitung dari tanggal publikasi video.
2. **Baseline tidak sebanding.** Velocity dari selisih snapshot dibagi dengan VPH lifetime baseline, lalu dicampur dengan rasio total views. Hasil baru menggunakan VPH lifetime kedua sisi dalam kelompok sebanding. Velocity snapshot tetap indikator terpisah.
3. **Video target ikut baseline.** Median/mean yang memuat target dapat menekan atau mendistorsi kelipatan outlier. Target kini dikeluarkan. Usia berbeda jauh, kelompok durasi lain, dan channel lain tidak masuk kelompok pembanding.
4. **Bukti tidak cukup tetap terlihat seperti indikator terukur.** Kontribusi baseline sekarang nol jika peer kurang dari tiga atau median tidak positif; radar juga tidak memberikan nilai akselerasi/baseline tanpa bukti cukup. Keyword Lab tidak menampilkan skor saat sampelnya belum memenuhi syarat minimum.
5. **Kandidat penemuan tidak seimbang.** Truncation terhadap gabungan hasil menyebabkan pencarian awal menguasai 50 kandidat. Pemilihan kini bergiliran antar kelompok pencarian sebelum batas diterapkan.
6. **Urutan hasil pencarian bisa berubah saat mengambil statistik.** Statistik sekarang dipetakan kembali ke urutan ID hasil search. Rank Tracker memakai urutan respons search langsung.
7. **Tanggal rusak dianggap tanggal saat ini.** Parser tidak lagi menyamarkan tanggal tidak valid sebagai unggahan baru.
8. **Pengambilan baseline menghabiskan jatah search.** Unggahan channel sekarang diambil melalui uploads playlist, mengikuti pola API resmi. Ditambah cache 5 menit, timeout dan retry terbatas. Tidak mengklaim saldo kuota dari hitungan lokal. [S9,S10]
9. **API key bisa muncul dalam error/URL AI.** Kunci Gemini dipindahkan ke header; error AI dan YouTube ditampilkan sebagai pesan terkendali. Respons error mentah Groq tidak ditampilkan. Endpoint autocomplete memakai HTTPS.
10. **Penggantian kunci otomatis dan kesalahan 403 disamakan.** Rotasi otomatis dihentikan; pesan membedakan kemungkinan kuota, izin dan konfigurasi. Pemilihan kunci aktif tetap tersedia bila pengguna memang mengatur beberapa kunci.
11. **Catatan watchlist terhapus saat referensi disimpan ulang.** Penyimpanan ulang sekarang mempertahankan catatan.
12. **Batas metadata belum diperiksa lengkap.** Ditambahkan pemeriksaan 100 karakter judul, 5.000 byte deskripsi, tag 500 karakter beserta pemisah/quote, serta karakter `<`/`>` pada judul/deskripsi. Ketentuan merujuk pada API resmi. Tag tetap berbobot kecil, sesuai penjelasan YouTube bahwa tag umumnya berperan terbatas. [S12,S13]
13. **Ekspor baru/hasil pencarian dapat berisi formula spreadsheet.** Teks yang berpotensi menjadi formula pada CSV diberi awalan pelindung. Cadangan schema 2 mencakup fitur baru dan tetap menerima schema 1, dengan transaksi pemulihan atomik.

Perubahan utama berada di `app.py`, `modules/intelligence.py`, `modules/youtube_client.py`, `modules/workspace_ui.py`, `modules/growth_engine.py`, `modules/growth_ui.py`, `modules/simple_ui.py`, dan `modules/ai_engine.py`. Tes regresi tambahan ada di `tests/test_upgrade.py`.

## Bagaimana kekuatan analisis ditingkatkan

**Skor keyword yang dapat diperiksa.** Skor sampel terdiri dari 40% momentum median VPH, 25% ruang judul berdasarkan cakupan kata target, 20% keragaman channel, dan 15% proporsi unggahan berusia ≤30 hari. Momentum memakai transformasi logaritmik. Skor personal, bila data tersedia, adalah 80% skor sampel ditambah 20% proporsi channel yang ukuran subscribernya ≤2 kali channel pengguna. Tidak ada komponen yang diberi nama volume pencarian. Rumus ini masih heuristik eksploratif dan belum divalidasi sebagai prediksi pertumbuhan.

**Bukti lebih jelas.** Baseline outlier menyebut jumlah peer dan dasar pembanding. Rank Tracker membedakan “belum diperiksa”, ditemukan, dan tidak ditemukan dalam sampel. Tidak ditemukan tidak diganti dengan angka peringkat 51. Kegagalan API tidak ditulis sebagai penurunan posisi.

**Alur kerja tersambung.** Hasil Keyword Lab dapat disimpan dan dikirim ke Kalender Konten. Rencana dapat dibuka di SEO Studio. Metadata dapat ditinjau massal. Hasil uji CTR dapat disimpan untuk rujukan keputusan berikutnya. Semua ini dapat dipakai tanpa mengganti arsitektur Streamlit pribadi yang sudah dimiliki.

## Batas yang masih ada dan kebutuhan tahap selanjutnya

| Kesenjangan tersisa | Mengapa belum setara | Prasyarat implementasi penuh |
|---|---|---|
| Volume pencarian historis/indeks vendor | Respons search API bukan jumlah pencarian pengguna | Sumber data berlisensi dengan metodologi, cakupan wilayah dan pembaruan yang jelas |
| Analytics privat otomatis | API key publik tidak memberi akses data channel privat | Google OAuth, scope baca, callback, token terenkripsi, persetujuan pengguna dan pengujian akun nyata [S14] |
| Rotasi eksperimen thumbnail/judul | Versi ini menganalisis angka yang dimasukkan pengguna | Integrasi berizin dan penjadwal; pengukuran watch time/traffic; atau gunakan eksperimen native YouTube Studio |
| Penilaian visual/heatmap AI | Pratinjau bukan model visual yang dikalibrasi | Model vision, evaluasi terhadap dataset nyata, biaya dan validasi kinerja |
| Pemantauan kontinu/alert | Histori bertambah saat pemeriksaan manual | Worker/scheduler, volume persisten, anggaran panggilan, refresh dan pengendalian error |
| Publikasi/perubahan massal | Audit hanya menghasilkan rekomendasi | OAuth write terpisah, preview perubahan, transaksi/rollback dan konfirmasi perubahan eksternal |
| Ekstensi, multiuser, klip otomatis | Tidak ada arsitektur layanan/worker media | Proyek ekstensi; autentikasi/pemisahan tenant; penyimpanan media dan pipeline pemrosesan |

Jadi, versi ini memperkuat riset, ketepatan metrik dan alur produksi secara nyata. Belum ada dasar untuk menyebutnya setara penuh atau lebih unggul secara keseluruhan dibanding kedua layanan komersial. Tidak dilakukan benchmark akurasi head-to-head pada dataset dan akun yang sama.

## Validasi hasil

- Sebelum perubahan: **29 tes lulus**.
- Setelah perubahan: **57 tes lulus**, termasuk 28 tes tambahan untuk metrik, client API, persistensi dan UI.
- Streamlit berhasil startup; endpoint health dan halaman aplikasi mengembalikan **HTTP 200**.
- API jaringan pada tes diganti fixture/mock. YouTube, Gemini dan Groq belum diuji dengan kredensial asli.
- Pengujian browser visual belum selesai karena browser pengujian tidak berhasil dipasang di lingkungan ini. Interaksi UI diverifikasi melalui Streamlit AppTest; responsif perangkat seluler dan hosting pengguna belum diverifikasi.

Petunjuk pemasangan dan alur uji akun asli terdapat di `UPGRADE_GUIDE.md`. Hasil yang dikirim adalah kode sumber yang sudah diubah; deployment publik/repository eksternal tidak diperbarui dalam pekerjaan ini.

## Sumber resmi

Sumber diakses dalam sesi audit 14 Oktober 2026 (WIB). Klaim vendor dipakai untuk mengidentifikasi fitur, bukan sebagai bukti efektivitas atau akurasi.

- **S1:** vidIQ, [Keyword Tools](https://vidiq.com/features/keyword-tools/).
- **S2:** TubeBuddy, [Keyword Explorer](https://www.tubebuddy.com/tools/keyword-explorer/).
- **S3:** vidIQ, [Outliers](https://vidiq.com/features/outliers/).
- **S4:** vidIQ, [Competitors](https://vidiq.com/features/competitors/).
- **S5:** TubeBuddy Help, [How to use SEO Studio](https://tubebuddy.zendesk.com/hc/en-us/articles/39107477828251-How-to-use-SEO-Studio).
- **S6:** TubeBuddy, [SEO and Ranking](https://www.tubebuddy.com/tools/seo-and-ranking/).
- **S7:** TubeBuddy Help, [A/B Testing Notes](https://tubebuddyhelp.zendesk.com/hc/en-us/articles/53959094125203-A-B-Testing-Notes).
- **S8:** TubeBuddy, [Product overview](https://www.tubebuddy.com/) dan [Competitor Analysis](https://www.tubebuddy.com/tools/youtube-competitor-analysis-tool).
- **S9:** Google, [Search: list](https://developers.google.com/youtube/v3/docs/search/list).
- **S10:** Google, [PlaylistItems: list](https://developers.google.com/youtube/v3/docs/playlistItems/list) dan [Retrieve channel uploads](https://developers.google.com/youtube/v3/guides/implementation/videos).
- **S11:** vidIQ, [Optimize](https://vidiq.com/features/optimize/).
- **S12:** Google, [Videos resource limits](https://developers.google.com/youtube/v3/docs/videos).
- **S13:** YouTube Help, [Peran tag video](https://support.google.com/youtube/answer/146402?hl=en).
- **S14:** Google, [Authorization for channel reports](https://developers.google.com/youtube/analytics/channel_reports).
