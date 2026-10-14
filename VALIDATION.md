# Validasi hotfix 2.0.1

`python -m unittest tests.test_api_selection -v`: 2 tes regresi lulus (1,852 detik). Tes menggunakan entrypoint aplikasi sebenarnya dan respons API mock. Memeriksa perubahan kunci, pencarian, Trending, navigasi, dan jumlah kunci yang menyusut. Pengujian API dengan kredensial nyata tidak dilakukan. Hasil 57 tes rilis 2.0 di bawah merupakan hasil run sebelumnya.

# Validasi Niche Hunter 2.0

Tanggal: 14 Oktober 2026 (WIB). Python 3.12.14; Streamlit 1.65.0; Pandas 2.2.3.

## Perintah dan hasil

```bash
python -m unittest discover -s tests -v
```

**57 pengujian lulus** (7,273 detik pada run lengkap). Sebelum perubahan, 29 pengujian bawaan lulus. Run lengkap mencakup 28 pengujian tambahan pada `tests/test_upgrade.py`.

Cakupan baru: baseline sebanding yang mengecualikan diri sendiri, tanggal/angka tidak valid, kekurangan bukti, subscriber tersembunyi, deduplikasi sampel, rank di batas sampel dan URL video, interval CTR dan input tidak sah, CSV formula injection, pemilihan kandidat seimbang, batas metadata UTF-8, pemisahan velocity interval/lifetime, cache per query/wilayah/kunci, force refresh, timeout, error teredaksi, retry terbatas, uploads playlist, persistensi lintas koneksi, schema 1/2 dan rollback restore. UI mencakup keenam menu baru, kalender create/update/handoff, rank tracking sukses/gagal, keyword/handoff, radar, audit massal dan catatan watchlist.

Startup proses Streamlit diuji memakai database temporer. Endpoint `/_stcore/health` menghasilkan HTTP 200 `ok`; halaman root menghasilkan HTTP 200. AppTest entrypoint memeriksa eksekusi aplikasi tanpa kredensial.

Pemeriksaan sintaks Python menggunakan compileall berhasil. Arsip akhir diverifikasi dapat dibuka dan tidak menyertakan Secrets, database, cache atau lingkungan virtual.

## Batas validasi

- API YouTube/Gemini/Groq tidak dipanggil dengan kredensial pengguna. Respons pada tes integrasi berupa fixture/mock.
- Tidak melakukan benchmark akurasi head-to-head dengan akun vidIQ/TubeBuddy atau validasi model prediksi. Semua skor riset tetap heuristik.
- Pengujian browser visual belum selesai: unduhan browser pengujian gagal. Widget dan interaksi diperiksa dengan Streamlit AppTest; tampilan mobile/browser dan hosting pengguna belum diverifikasi.
- Ada peringatan deprecation bawaan Streamlit tentang `use_container_width` dan Python tentang `utcnow` pada kode lama. Tidak menyebabkan kegagalan pada versi dependensi yang diuji. Kompatibilitas semua versi dalam rentang requirements belum diverifikasi.
- Deployment publik, repository eksternal, dan data akun YouTube tidak diubah.

Ikuti tiga pemeriksaan akun asli di akhir UPGRADE_GUIDE.md setelah memasukkan kredensial dan memasang pada hosting tujuan.
