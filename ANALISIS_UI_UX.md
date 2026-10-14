# Audit Niche Hunter

Tanggal pemeriksaan: 9 Oktober 2026. Sumber: niche-hunter-main.zip dan aplikasi https://diffic.streamlit.app/.

## Penilaian

Aplikasi memiliki cakupan fitur riset yang luas, tetapi penyajian awal memberi bobot visual hampir sama pada navigasi, filter, indikator, dan analisis lanjutan. Untuk penggunaan pribadi, penyederhanaan yang paling relevan adalah menampilkan langkah yang diperlukan saat ini dan membuka detail ketika dibutuhkan. Pendekatan ini mempertahankan fungsi sambil mengurangi jumlah pilihan yang harus dipindai sekaligus.

Penilaian merupakan audit kode dan evaluasi antarmuka, bukan studi usability dengan responden. Tidak diberikan skor kualitas numerik karena tidak ada pengukuran waktu penyelesaian tugas, tingkat kesalahan, atau survei pengguna.

## Temuan yang diamati

| Temuan | Bukti pada sumber asli | Dampak | Penanganan dalam revisi |
|---|---|---|---|
| Sidebar menumpuk navigasi, status API, dan seluruh filter | app.py baris 1312-1402. Pada browser, tombol pencarian berada dekat bagian bawah sidebar yang harus digulir. | Alur utama sulit ditemukan dan ruang konten kurang dimanfaatkan. | Sidebar berisi tiga kelompok kerja. Form pencarian dipindahkan ke area utama. Status API masuk panel bantuan. |
| Analisis tampil sebelum hasil | Expander dashboard dibuka otomatis, app.py baris 1460. Dikonfirmasi pada hasil pencarian ASMR Rain. | Daftar video terdorong jauh ke bawah. | Hasil menjadi tab awal. Analisis pasar dan ide AI berada pada tab lain. |
| Kartu video terlalu banyak indikator dan tombol | app.py baris 1500-1550: pendapatan, engagement, rasio, SEO, likes, komentar, VPH, dan berbagai tindakan. | Pemindaian judul dan performa utama terganggu. | Kartu dua kolom berisi informasi pokok. Detail lengkap tersedia dalam expander. |
| Grid channel menggunakan empat atau lima kolom | app.py baris 1710 dan 1773. | Ruang setiap judul dan statistik menjadi sempit, terutama saat sidebar terbuka. | Direktori memakai dua kolom dan halaman hasil. Perbandingan menggunakan tabel. |
| Identitas visual tidak konsisten | CSS awal menggunakan banyak warna badge, gradien, bayangan, border, dan ukuran teks. | Banyak elemen tampak sama-sama menuntut perhatian. | Satu aksen warna, judul lebih pendek, tombol dengan penamaan konsisten, dan tanpa ikon dekoratif pada navigasi baru. |
| Form artis langsung memperlihatkan lima nama | app.py baris 1194-1205. | Form terasa panjang walaupun hanya ingin membandingkan dua artis. | Dua nama utama. Artis ketiga sampai kelima tetap tersedia di panel opsional. |
| Grafik artis mencampur satuan | app.py baris 1254: Interest Proxy, Avg VPH, Fresh Videos dalam satu grafik. | Besaran dengan skala besar menutupi metrik lain. | Satu metrik dipilih untuk setiap grafik; seluruh angka tetap tersedia pada Data lengkap. |

## Temuan fungsi dan ketepatan informasi

| Prioritas | Temuan | Status |
|---|---|---|
| Tinggi | Channel DNA disimpan pada satu `channel_dna_result` dan dirender di dalam loop setiap kartu, app.py baris 1531-1533. Hasil satu video dapat tampil pada kartu lain. | Diperbaiki. Jawaban dikaitkan dengan ID channel, video, serta konteks data. |
| Tinggi | Pencarian dan trending memakai `st.session_state.results` yang sama, baris 1431 dan 1443. Perpindahan mode dapat menyajikan hasil dari mode sebelumnya dengan konteks yang keliru. | Diperbaiki. Kedua mode mempunyai hasil dan konteks masing-masing. |
| Tinggi | VPH direktori dibentuk dari angka views yang telah diformat. Misalnya `1.2K` diubah menjadi `12000`, lalu dibagi 24 tanpa memakai usia video, app.py baris 243-244. Ini bukan perhitungan laju per jam yang dapat diandalkan. | Belum diubah agar audit rumus terpisah dari revisi UI. Label dan bantuan memperingatkan keterbatasan metode lama. Perbaikan berikutnya: simpan angka mentah dan hitung menggunakan waktu publikasi atau selisih snapshot. |
| Menengah | Analisis channel memberi label rata-rata 15 video, tetapi `recent_videos` hanya menyimpan lima dan dipakai untuk menghitung rata-rata, app.py baris 582-602 dan 1826. | Label diperbaiki sesuai banyaknya sampel aktual. Kalkulasi asli dipertahankan. |
| Menengah | Waktu publikasi yang paling sering muncul disebut waktu upload paling ideal, meskipun fungsi hanya menghitung frekuensi hari dan jam sampel. | Label diperbaiki menjadi pola publikasi, beserta batas interpretasinya. |
| Menengah | Hasil AI hanya dirender di dalam blok klik tombol sehingga hilang pada rerun berikutnya. | Diperbaiki dengan penyimpanan jawaban dalam sesi sesuai konteks. |
| Menengah | Thumbnail diunduh dengan `requests.get` di dalam loop meskipun expander tertutup. Tidak ada timeout pada permintaan tersebut. | Diperbaiki. Unduhan hanya dimulai saat diminta, dengan timeout 15 detik. |
| Menengah | `analyze_channel_deep` dipanggil kembali saat halaman terkait rerun. | Ditambahkan cache per sesi maksimal 15 menit dan tombol pembaruan eksplisit. |
| Menengah | Penambahan channel kelima menghapus channel pertama secara otomatis melalui `pop(0)`. | Diperbaiki. Daftar tetap utuh dan pengguna diminta menghapus salah satu terlebih dahulu. |
| Menengah | Saran autocomplete mengubah `search_query`, sedangkan widget `q_input` mempertahankan nilainya sendiri. | Callback baru memperbarui nilai widget dan preferensi secara bersamaan. |
| Lanjutan | `generate_ai_ideas` belum memiliki timeout; beberapa fungsi memakai `except` luas, fallback diam-diam, atau pesan error mentah. | Masih ada pada mesin layanan asli. Perlu audit reliabilitas terpisah. |
| Lanjutan | Breakout score, skor SEO, estimasi pendapatan, dan artist interest proxy adalah heuristik, bukan metrik resmi atau model prediksi yang sudah divalidasi. | Fitur dipertahankan dengan label lebih tepat. Validasi perlu data historis dan pembandingan terhadap hasil aktual. |

Saat pemeriksaan browser, pencarian ASMR Rain menghasilkan 12 video. Aplikasi juga menampilkan pesan bahwa Google Trends tidak dapat diambil. Penyebab blokir tidak diverifikasi secara independen. Revisi menggunakan pesan kegagalan yang lebih netral dan menyediakan tautan manual.

## Pemetaan fitur

| Fitur asli | Lokasi revisi |
|---|---|
| Pencarian video, seluruh filter, saran kata kunci | Video > Pencarian |
| Trending, filter negara, kategori, jumlah hasil | Video > Trending |
| Metrik lengkap, pendapatan, rasio, engagement, SEO, ringkasan, thumbnail | Detail, SEO, dan tindakan pada kartu, atau detail tampilan tabel |
| Channel DNA, bedah channel, tambah perbandingan | Detail video |
| Chart VPH, top tags, pola upload, Google Trends | Analisis pasar |
| Lima ide konten dengan AI | Ide AI |
| Scan long-form, freshness, durasi minimum, breakout score, acceleration, baseline | Viral Intelligence |
| Radar kandidat, small-channel breakouts, pola pemenang | Kandidat serta Detail dan radar |
| Content opportunity dan analisis AI breakout | Peluang konten |
| Direktori serta filter subscriber, usia, VPH, sorting | Channel > Direktori |
| Statistik channel, lima video terbaru, pola jam, top tags dan salin tag | Channel > Analisis |
| Perbandingan hingga empat channel dan penghapusan daftar | Channel > Perbandingan |
| Perbandingan hingga lima artis, semua metrik dan CSV | Artis |
| Ekspor CSV pencarian, trending, viral, dan artis | Unduh CSV pada hasil masing-masing |
| Rotasi API key dan snapshot SQLite | Mesin layanan app.py yang dipertahankan |

`video_insight`, `competitor_insight`, `content_strategy`, dan `opportunity_score` tetap tersedia pada modul aslinya. Sumber unggahan belum menghubungkan seluruh fungsi tersebut ke tombol antarmuka; fungsi yang tidak terhubung tidak dihitung sebagai fitur UI yang sudah ada.

## Batas validasi

Sepuluh skenario AppTest lulus dengan data simulasi. Entry point utama tidak menghasilkan exception pada pemeriksaan awal. Perbandingan AST memastikan 45 fungsi kalkulasi dan layanan tidak berubah. Dua modul asli tidak berubah. Tidak ada deployment, pengujian AI berbayar, atau pengujian end-to-end API revisi dengan kredensial pengguna. CSS responsif belum diuji secara visual pada perangkat seluler karena cloud browser tidak dapat membuka server lokal.

## Rujukan implementasi

- Streamlit forms: https://docs.streamlit.io/develop/api-reference/execution-flow/st.form
- Streamlit expanders: https://docs.streamlit.io/develop/api-reference/layout/st.expander
- Streamlit AppTest: https://docs.streamlit.io/develop/api-reference/app-testing/st.testing.v1.apptest

Form mengelompokkan perubahan input sampai dikirim. Expander menutup tampilan tetapi tidak otomatis menunda eksekusi seluruh isinya; karena itu pemanggilan jaringan memerlukan kontrol tombol secara eksplisit. Pemisahan tersebut dipakai dalam revisi untuk mengurangi kepadatan sekaligus mencegah panggilan tambahan yang tidak diperlukan.
