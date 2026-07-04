import streamlit as st
import pandas as pd
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

st.set_page_config(page_title="Sistem Tabungan", layout="centered")

# =========================================================================
# 1. KONEKSI DATABASE CLOUD (POSTGRESQL)
# =========================================================================
# Menggunakan fitur koneksi bawaan Streamlit untuk SQL
conn = st.connection("postgresql", type="sql")

def init_db():
    with conn.session as s:
        s.execute(text('''CREATE TABLE IF NOT EXISTS users (
                        id SERIAL PRIMARY KEY,
                        username TEXT UNIQUE, password TEXT, nama TEXT, 
                        role TEXT, is_member BOOLEAN)'''))
        
        s.execute(text('''CREATE TABLE IF NOT EXISTS transactions (
                        id SERIAL PRIMARY KEY,
                        tanggal TEXT, anggota TEXT, jumlah INTEGER, pencatat TEXT, tipe TEXT DEFAULT 'Setor')'''))
        
        s.execute(text('''CREATE TABLE IF NOT EXISTS config (
                        key TEXT PRIMARY KEY, value TEXT)'''))
        
        # Masukkan data awal jika database masih kosong
        res = s.execute(text("SELECT COUNT(*) FROM users")).fetchone()
        if res[0] == 0:
            s.execute(text("INSERT INTO users (username, password, nama, role, is_member) VALUES (:u, :p, :n, :r, :m)"),
                      {"u": 'admin1', "p": '123', "n": 'Super Admin', "r": 'Admin', "m": False})
            s.execute(text("INSERT INTO users (username, password, nama, role, is_member) VALUES (:u, :p, :n, :r, :m)"),
                      {"u": 'budi', "p": '123', "n": 'Budi (Pengurus)', "r": 'Pengurus', "m": True})
            s.execute(text("INSERT INTO config (key, value) VALUES (:k, :v)"), 
                      {"k": 'status_pencatatan', "v": 'Buka'})
        s.commit()

init_db()

def fetch_data(query, params=None):
    if params is None:
        params = {}
    # ttl=0 sangat penting agar saldo dan history selalu ter-update (tidak di-cache)
    return conn.query(query, params=params, ttl=0)

def execute_query(query, params=None):
    if params is None:
        params = {}
    with conn.session as s:
        s.execute(text(query), params)
        s.commit()

def cek_saldo_anggota(nama_anggota):
    df_saldo = fetch_data("SELECT SUM(jumlah) as total FROM transactions WHERE anggota=:a", {"a": nama_anggota})
    saldo = df_saldo.iloc[0]['total']
    return saldo if pd.notna(saldo) else 0

def get_saldo_semua_anggota():
    df_users = fetch_data("SELECT nama FROM users WHERE is_member=TRUE")
    df_tx = fetch_data("SELECT anggota, jumlah FROM transactions")
    
    if df_users.empty:
        return pd.DataFrame()
        
    if not df_tx.empty:
        df_saldo = df_tx.groupby('anggota')['jumlah'].sum().reset_index()
        df_final = pd.merge(df_users, df_saldo, left_on='nama', right_on='anggota', how='left')
        df_final['jumlah'] = df_final['jumlah'].fillna(0)
        if 'anggota' in df_final.columns:
            df_final.drop(columns=['anggota'], inplace=True)
    else:
        df_final = df_users.copy()
        df_final['jumlah'] = 0
        
    df_final.rename(columns={'nama': 'Nama Anggota', 'jumlah': 'Total Saldo'}, inplace=True)
    return df_final

@st.cache_data
def convert_df_to_csv(df):
    return df.to_csv(index=False).encode('utf-8')

# =========================================================================
# 2. SISTEM LOGIN & UI
# =========================================================================
if 'user' not in st.session_state:
    st.session_state.user = None

if st.session_state.user is None:
    st.title("💰 Sistem Tabungan Jamaah")
    with st.form("login_form"):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.form_submit_button("Masuk"):
            df_user = fetch_data("SELECT * FROM users WHERE username=:u AND password=:p", {"u": str(u), "p": str(p)})
            if not df_user.empty:
                user_dict = df_user.iloc[0].to_dict()
                user_dict['is_member'] = bool(user_dict['is_member'])
                st.session_state.user = user_dict
                st.rerun()
            else:
                st.error("Username atau password salah")
else:
    user = st.session_state.user
    role = user['role']
    
    st.sidebar.title(f"Halo, {user['nama']}")
    st.sidebar.write(f"Akses: **{role}**")
    
    with st.sidebar.expander("🔑 Ganti Password"):
        with st.form("form_ganti_pass"):
            pass_lama = st.text_input("Password Lama", type="password")
            pass_baru = st.text_input("Password Baru", type="password")
            if st.form_submit_button("Simpan Password"):
                if pass_lama == str(user['password']):
                    execute_query("UPDATE users SET password=:p WHERE username=:u", {"p": pass_baru, "u": user['username']})
                    st.session_state.user['password'] = pass_baru 
                    st.success("Password berhasil diubah!")
                else:
                    st.error("Password lama salah!")

    if st.sidebar.button("Keluar (Logout)"):
        st.session_state.user = None
        st.rerun()

    # ==========================================
    # TAMPILAN 1: ADMIN
    # ==========================================
    if role == "Admin":
        st.title("🕹️ Panel Admin")
        
        tab_dash, tab_input, tab_users, tab_saldo, tab_koreksi = st.tabs([
            "Dashboard", "Input Transaksi", "Kelola Pengguna", "Saldo Anggota", "Koreksi Data"
        ])
        
        with tab_dash:
            df_tx = fetch_data("SELECT * FROM transactions")
            total = df_tx['jumlah'].sum() if not df_tx.empty else 0
            st.metric("Total Uang Kas Saat Ini", f"Rp {total:,.0f}")
            
            st.divider()
            st.subheader("Atur Waktu Pencatatan")
            df_cfg = fetch_data("SELECT value FROM config WHERE key='status_pencatatan'")
            status_skrg = df_cfg.iloc[0]['value']
            st.write(f"Status saat ini: **{status_skrg}**")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Buka Akses Input", use_container_width=True):
                    execute_query("UPDATE config SET value='Buka' WHERE key='status_pencatatan'")
                    st.rerun()
            with col2:
                if st.button("Tutup Akses Input", use_container_width=True):
                    execute_query("UPDATE config SET value='Tutup' WHERE key='status_pencatatan'")
                    st.rerun()
            
            st.divider()
            st.write("Riwayat Seluruh Transaksi:")
            if not df_tx.empty:
                df_tx_tampil = df_tx[['tanggal', 'anggota', 'tipe', 'jumlah', 'pencatat']]
                st.dataframe(df_tx_tampil, use_container_width=True, hide_index=True)
                
                csv_riwayat = convert_df_to_csv(df_tx_tampil)
                st.download_button(
                    label="📥 Download Laporan Riwayat (CSV)",
                    data=csv_riwayat,
                    file_name=f"Riwayat_Transaksi_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )

        with tab_input:
            st.subheader("Catat Transaksi Tabungan")
            df_cfg = fetch_data("SELECT value FROM config WHERE key='status_pencatatan'")
            if df_cfg.iloc[0]['value'] == "Tutup":
                st.warning("🔒 Pencatatan sedang ditutup. Buka dari tab sebelah jika ingin menginput.")
            else:
                with st.form("admin_input_tx"):
                    df_members = fetch_data("SELECT nama FROM users WHERE is_member=TRUE")
                    list_member = df_members['nama'].tolist() if not df_members.empty else []
                    
                    if list_member:
                        jenis_tx = st.radio("Jenis Transaksi", ["Setor", "Tarik"], horizontal=True)
                        nama_siapa = st.selectbox("Pilih Anggota", list_member)
                        jumlah_input = st.number_input("Jumlah (Rp)", min_value=0, step=5000)
                        
                        if st.form_submit_button("Simpan Data"):
                            saldo_sekarang = cek_saldo_anggota(nama_siapa)
                            if jenis_tx == "Tarik" and jumlah_input > saldo_sekarang:
                                st.error(f"Gagal! Saldo {nama_siapa} tidak mencukupi (Rp {saldo_sekarang:,.0f})")
                            elif jumlah_input > 0:
                                jumlah_db = jumlah_input if jenis_tx == "Setor" else -jumlah_input
                                waktu = datetime.now().strftime("%d/%m/%Y %H:%M")
                                execute_query("INSERT INTO transactions (tanggal, anggota, jumlah, pencatat, tipe) VALUES (:t, :a, :j, :p, :tp)",
                                              {"t": waktu, "a": nama_siapa, "j": jumlah_db, "p": user['nama'], "tp": jenis_tx})
                                st.success(f"Berhasil mencatat {jenis_tx} untuk {nama_siapa}")
                                st.rerun()
                            else:
                                st.error("Jumlah harus lebih dari 0.")
                    else:
                        st.info("Belum ada anggota yang terdaftar.")

        with tab_users:
            st.subheader("Tambah Pengguna Baru")
            with st.form("admin_tambah_user"):
                n_u = st.text_input("Username (Buat Login)")
                n_p = st.text_input("Password")
                n_n = st.text_input("Nama Lengkap")
                n_r = st.selectbox("Jabatan", ["Anggota", "Pengurus", "Admin"])
                n_m = st.checkbox("Centang jika ikut menabung", value=True)
                
                if st.form_submit_button("Daftarkan"):
                    try:
                        execute_query("INSERT INTO users (username, password, nama, role, is_member) VALUES (:u, :p, :n, :r, :m)",
                                      {"u": n_u, "p": n_p, "n": n_n, "r": n_r, "m": n_m})
                        st.success(f"{n_n} Berhasil didaftarkan!")
                        st.rerun()
                    except IntegrityError:
                        st.error("Username sudah dipakai!")
            
            df_u = fetch_data("SELECT * FROM users")
            st.divider()
            
            st.subheader("Edit & Hapus Pengguna (Reset Password)")
            pilih_user_aksi = st.selectbox("Pilih akun yang ingin diedit/dihapus:", [""] + df_u['username'].tolist())
            
            if pilih_user_aksi:
                user_terpilih = df_u[df_u['username'] == pilih_user_aksi].iloc[0]
                with st.form("form_edit_user"):
                    st.write(f"Mengedit: **{user_terpilih['nama']}**")
                    baru_role = st.selectbox("Jabatan", ["Anggota", "Pengurus", "Admin"], index=["Anggota", "Pengurus", "Admin"].index(user_terpilih['role']))
                    baru_member = st.checkbox("Ikut Menabung?", value=bool(user_terpilih['is_member']))
                    baru_password = st.text_input("Password (Bisa diubah jika lupa)", value=str(user_terpilih['password']))
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.form_submit_button("Simpan Perubahan"):
                            execute_query("UPDATE users SET role=:r, is_member=:m, password=:p WHERE username=:u", 
                                          {"r": baru_role, "m": baru_member, "p": baru_password, "u": pilih_user_aksi})
                            st.success("Data pengguna diperbarui!")
                            st.rerun()
                            
                    with col2:
                        if st.form_submit_button("Hapus Pengguna"):
                            if pilih_user_aksi == user['username']:
                                st.error("Tidak bisa menghapus akun Anda sendiri!")
                            else:
                                execute_query("DELETE FROM users WHERE username=:u", {"u": pilih_user_aksi})
                                st.success("Akun dihapus!")
                                st.rerun()
            
            st.divider()
            st.subheader("Daftar Pengguna Saat Ini")
            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown("**👥 Jajaran Admin & Pengurus**")
                df_pengurus = df_u[df_u['role'].isin(['Admin', 'Pengurus'])][['nama', 'role']]
                st.dataframe(df_pengurus, hide_index=True, use_container_width=True)
                
            with col_b:
                st.markdown("**💰 Daftar Anggota Menabung**")
                # Pandas menangani BOOLEAN dari Postgres sebagai nilai True/False
                df_anggota = df_u[df_u['is_member'] == True][['nama', 'username']]
                st.dataframe(df_anggota, hide_index=True, use_container_width=True)

        with tab_saldo:
            st.subheader("Rekap Saldo Setiap Anggota")
            df_rekap = get_saldo_semua_anggota()
            if not df_rekap.empty:
                df_rekap_export = df_rekap.copy()
                df_rekap['Total Saldo'] = df_rekap['Total Saldo'].apply(lambda x: f"Rp {int(x):,.0f}")
                st.dataframe(df_rekap, hide_index=True, use_container_width=True)
                
                csv_saldo = convert_df_to_csv(df_rekap_export)
                st.download_button(
                    label="📥 Download Rekap Saldo (CSV)",
                    data=csv_saldo,
                    file_name=f"Rekap_Saldo_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
            else:
                st.info("Belum ada anggota yang terdaftar.")
                
        with tab_koreksi:
            st.subheader("Batal / Hapus Transaksi (Koreksi Data)")
            
            df_tx_all = fetch_data("SELECT * FROM transactions ORDER BY id DESC")
            if not df_tx_all.empty:
                options = [""] + df_tx_all.apply(
                    lambda x: f"ID: {x['id']} | {x['tanggal']} | {x['anggota']} | {x['tipe']} | Rp {abs(x['jumlah']):,} | Pencatat: {x['pencatat']}", 
                    axis=1
                ).tolist()
                
                pilih_tx = st.selectbox("Pilih transaksi yang ingin dibatalkan:", options)
                
                if pilih_tx:
                    tx_id = int(pilih_tx.split(" | ")[0].replace("ID: ", ""))
                    st.error(f"Anda yakin ingin menghapus transaksi ini permanen?")
                    if st.button("Ya, Hapus Transaksi Ini", type="primary"):
                        execute_query("DELETE FROM transactions WHERE id=:id", {"id": tx_id})
                        st.success("Transaksi dihapus! Saldo sudah dikalkulasi ulang.")
                        st.rerun()
                
                st.divider()
                st.dataframe(df_tx_all, hide_index=True, use_container_width=True)
            else:
                st.info("Belum ada data transaksi yang bisa dikoreksi.")

    # ==========================================
    # TAMPILAN 2: PENGURUS
    # ==========================================
    elif role == "Pengurus":
        st.title("📝 Panel Pengurus")
        df_tx = fetch_data("SELECT * FROM transactions")
        total = df_tx['jumlah'].sum() if not df_tx.empty else 0
        st.metric("Total Kas Keseluruhan", f"Rp {total:,.0f}")

        menu = st.selectbox("Navigasi Tugas:", ["Input Transaksi", "Cek Saldo Tiap Anggota", "Lihat Riwayat Transaksi", "Daftarkan Anggota Baru"])
        
        if menu == "Input Transaksi":
            df_cfg = fetch_data("SELECT value FROM config WHERE key='status_pencatatan'")
            if df_cfg.iloc[0]['value'] == "Tutup":
                st.warning("🔒 Maaf, Admin sedang menutup waktu pencatatan.")
            else:
                with st.form("pengurus_input_tx"):
                    df_members = fetch_data("SELECT nama FROM users WHERE is_member=TRUE")
                    list_member = df_members['nama'].tolist() if not df_members.empty else []
                    
                    if list_member:
                        jenis_tx = st.radio("Jenis Transaksi", ["Setor", "Tarik"], horizontal=True)
                        nama_siapa = st.selectbox("Nama Anggota", list_member)
                        jumlah_input = st.number_input("Jumlah (Rp)", min_value=0, step=5000)
                        
                        if st.form_submit_button("Simpan Transaksi"):
                            saldo_sekarang = cek_saldo_anggota(nama_siapa)
                            if jenis_tx == "Tarik" and jumlah_input > saldo_sekarang:
                                st.error(f"Gagal! Saldo tidak mencukupi (Rp {saldo_sekarang:,.0f})")
                            elif jumlah_input > 0:
                                jumlah_db = jumlah_input if jenis_tx == "Setor" else -jumlah_input
                                waktu = datetime.now().strftime("%d/%m/%Y %H:%M")
                                execute_query("INSERT INTO transactions (tanggal, anggota, jumlah, pencatat, tipe) VALUES (:t, :a, :j, :p, :tp)",
                                              {"t": waktu, "a": nama_siapa, "j": jumlah_db, "p": user['nama'], "tp": jenis_tx})
                                st.success(f"{jenis_tx} berhasil dicatat!")
                                st.rerun()
                            else:
                                st.error("Jumlah tidak valid.")
                    else:
                        st.info("Belum ada anggota terdaftar.")

        elif menu == "Cek Saldo Tiap Anggota":
            st.subheader("Rekap Saldo Keseluruhan")
            df_rekap = get_saldo_semua_anggota()
            if not df_rekap.empty:
                df_rekap_export = df_rekap.copy()
                df_rekap['Total Saldo'] = df_rekap['Total Saldo'].apply(lambda x: f"Rp {int(x):,.0f}")
                st.dataframe(df_rekap, hide_index=True, use_container_width=True)
                
                csv_saldo = convert_df_to_csv(df_rekap_export)
                st.download_button("📥 Download Rekap Saldo (CSV)", data=csv_saldo, file_name=f"Rekap_Saldo_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv")
            else:
                st.info("Belum ada anggota terdaftar.")

        elif menu == "Lihat Riwayat Transaksi":
            if not df_tx.empty:
                df_tx_tampil = df_tx[['tanggal', 'anggota', 'tipe', 'jumlah', 'pencatat']]
                st.dataframe(df_tx_tampil, hide_index=True, use_container_width=True)
                csv_riwayat = convert_df_to_csv(df_tx_tampil)
                st.download_button("📥 Download Laporan Riwayat (CSV)", data=csv_riwayat, file_name=f"Riwayat_Transaksi_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv")

        elif menu == "Daftarkan Anggota Baru":
            with st.form("pengurus_anggota_baru"):
                n_u = st.text_input("Username Baru")
                n_p = st.text_input("Password Baru")
                n_n = st.text_input("Nama Lengkap")
                if st.form_submit_button("Daftarkan Anggota"):
                    try:
                        execute_query("INSERT INTO users (username, password, nama, role, is_member) VALUES (:u, :p, :n, :r, :m)",
                                      {"u": n_u, "p": n_p, "n": n_n, "r": 'Anggota', "m": True})
                        st.success(f"{n_n} Berhasil Terdaftar!")
                        st.rerun()
                    except IntegrityError:
                        st.error("Username sudah dipakai.")

    # ==========================================
    # TAMPILAN 3: ANGGOTA (Atau Pengurus yg Menabung)
    # ==========================================
    if user['is_member']:
        if role != "Anggota": 
            st.divider() 
        st.title("💰 Tabunganku")
        
        my_data = fetch_data("SELECT * FROM transactions WHERE anggota=:a", {"a": user['nama']})
        total_saya = my_data['jumlah'].sum() if not my_data.empty else 0
        st.metric("Total Tabungan Anda", f"Rp {total_saya:,.0f}")
        
        st.write("Riwayat Transaksi Anda:")
        if not my_data.empty:
            st.dataframe(my_data[['tanggal', 'tipe', 'jumlah', 'pencatat']], hide_index=True, use_container_width=True)
        else:
            st.info("Belum ada data transaksi.")