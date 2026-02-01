import streamlit as st
import google.generativeai as genai
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date
import json
import plotly.express as px
import time
import io

# --- 1. SETUP HALAMAN ---
st.set_page_config(page_title="My Life OS 7.0 (Secure & Visual)", layout="wide", page_icon="🧬")

# ==========================================
# 🔒 SISTEM KEAMANAN (LOGIN GATE)
# ==========================================
def check_password():
    """Memeriksa apakah user sudah login dengan benar."""
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    if st.session_state["password_correct"]:
        return True

    # Tampilan Layar Login
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.title("🔒 Restricted Access")
        st.write("Aplikasi ini terkunci. Masukkan sandi pemilik.")
        pwd = st.text_input("Password:", type="password")
        
        if st.button("Buka Gembok 🔓"):
            # Cek password dari secrets.toml
            if pwd == st.secrets["APP_PASSWORD"]:
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("⛔ Password Salah! Akses Ditolak.")
    return False

# JIKA BELUM LOGIN, STOP DISINI (JANGAN MUAT APLIKASI)
if not check_password():
    st.stop()

# ==========================================
# 🚀 APLIKASI UTAMA DIMULAI DARI SINI
# ==========================================

# --- 2. KONEKSI DATABASE ---
@st.cache_resource
def init_connection():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        raw = st.secrets["GCP_SERVICE_ACCOUNT"]
        if isinstance(raw, str): creds_info = json.loads(raw)
        else: creds_info = dict(raw)
        
        if "private_key" in creds_info:
            creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n")
        
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
        client = gspread.authorize(creds)
        sh = client.open("productivity_db")
        
        try: ws_adv = sh.worksheet("advisor")
        except: ws_adv = sh.add_worksheet("advisor", rows=1000, cols=3); ws_adv.append_row(["Timestamp", "Pertanyaan", "Jawaban"])

        return {
            "todo": sh.worksheet("todos"),
            "fin": sh.worksheet("finance"),
            "habit": sh.worksheet("habits"),
            "journal": sh.worksheet("journal"),
            "advisor": ws_adv
        }
    except Exception as e:
        st.error(f"❌ Error Database: {e}")
        return None

sheets = init_connection()

# --- 3. DATA LOADING (Cache 60 Detik) ---
@st.cache_data(ttl=60)
def load_all_data():
    if not sheets: return None, None, None, None, None
    try:
        def safe_get(key):
            try: return pd.DataFrame(sheets[key].get_all_records())
            except: return pd.DataFrame()

        df_todo = safe_get("todo")
        df_fin = safe_get("fin")
        df_habit = safe_get("habit")
        df_journal = safe_get("journal")
        df_advisor = safe_get("advisor")
        return df_todo, df_fin, df_habit, df_journal, df_advisor
    except:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

df_todo, df_fin, df_habit, df_journal, df_advisor = load_all_data()

# --- 4. SETUP AI (Anti-Sensor) ---
model = None
try:
    if "GEMINI_API_KEY" in st.secrets:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        safe_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
        model = genai.GenerativeModel('models/gemini-2.5-flash', safety_settings=safe_settings)
except Exception as e: pass

# --- 5. UTILITIES ---
def clear_cache_and_rerun():
    load_all_data.clear()
    st.rerun()

def fix_headers_only():
    if not sheets: return
    try:
        sheets["todo"].update("A1:D1", [["Tanggal", "Task", "Prioritas", "Status"]])
        sheets["fin"].update("A1:E1", [["Tanggal", "Item", "Kategori", "Jumlah", "Tipe"]])
        sheets["habit"].update("A1:C1", [["Tanggal", "Habit", "Status"]])
        sheets["journal"].update("A1:D1", [["Tanggal", "Isi_Jurnal", "AI_Mood", "AI_Saran"]])
        sheets["advisor"].update("A1:C1", [["Timestamp", "Pertanyaan", "Jawaban"]])
        st.toast("Format tabel diperbaiki!", icon="🛠️")
        clear_cache_and_rerun()
    except: pass

# --- 6. SIDEBAR ---
with st.sidebar:
    st.title("🧬 My Life OS")
    
    # Tombol Logout
    if st.button("🔒 LOGOUT (Kunci App)"):
        st.session_state["password_correct"] = False
        st.rerun()
    
    st.divider()

    # XP System
    xp_point = 0
    if not df_todo.empty and 'Status' in df_todo.columns:
        xp_point += len(df_todo[df_todo['Status'] == 'Selesai']) * 15
    if not df_habit.empty and 'Status' in df_habit.columns:
        xp_point += len(df_habit[df_habit['Status'] == 'Done']) * 10 
    
    level = int(xp_point / 200) + 1
    st.subheader(f"Level {level}")
    st.progress((xp_point % 200) / 200)
    st.caption(f"{xp_point} XP Total")
    
    with st.expander("🍅 Fokus Timer"):
        menit = st.number_input("Menit:", 1, 120, 25)
        if st.button("Mulai Fokus"):
            bar = st.progress(0); t_s = st.empty()
            for i in range(menit * 60):
                t_s.caption(f"⏳ {menit*60 - i} detik lagi")
                bar.progress((i+1)/(menit*60))
                time.sleep(1) # Sleep aman karena di sidebar
            st.balloons()
            st.success("Waktu Habis!")
    
    with st.expander("📥 Backup Excel"):
        if st.button("Download Data"):
            out = io.BytesIO()
            with pd.ExcelWriter(out, engine='xlsxwriter') as w:
                df_todo.to_excel(w, sheet_name='ToDo', index=False)
                df_fin.to_excel(w, sheet_name='Keuangan', index=False)
                df_habit.to_excel(w, sheet_name='Habits', index=False)
                df_journal.to_excel(w, sheet_name='Jurnal', index=False)
            st.download_button("Klik Download", out.getvalue(), f'Backup_{date.today()}.xlsx', 'application/vnd.ms-excel')

    st.divider()
    if st.button("🛠️ Fix Error Tabel"): fix_headers_only()

# --- 7. TABS UTAMA ---
tab_home, tab1, tab2, tab3, tab4, tab5 = st.tabs(["🏠 Dashboard", "📝 ToDo", "💰 Uang", "✅ Habit", "📔 Jurnal", "🤖 Advisor"])

# === TAB 1: DASHBOARD (PUSAT GRAFIK) ===
with tab_home:
    st.header(f"📊 Analisis Kehidupan Level {level}")
    
    # Metric Utama
    c1, c2, c3, c4 = st.columns(4)
    keluar = 0
    if not df_fin.empty and 'Jumlah' in df_fin.columns:
        df_fin['Jumlah'] = pd.to_numeric(df_fin['Jumlah'], errors='coerce').fillna(0)
        keluar = df_fin[df_fin['Tipe'] == 'Pengeluaran']['Jumlah'].sum()
    c1.metric("Total Pengeluaran", f"Rp {keluar:,.0f}")
    
    pending = 0
    if not df_todo.empty and 'Status' in df_todo.columns:
        pending = len(df_todo[df_todo['Status'] == 'Pending'])
    c2.metric("Tugas Pending", f"{pending}")
    
    habit_today = 0
    if not df_habit.empty and 'Tanggal' in df_habit.columns:
        today_str = str(date.today())
        habit_today = len(df_habit[(df_habit['Tanggal'] == today_str) & (df_habit['Status'] == 'Done')])
    c3.metric("Habit Hari Ini", f"{habit_today}")
    c4.metric("Total XP", xp_point)
    
    st.divider()
    
    # Grafik Gabungan
    g1, g2 = st.columns(2)
    with g1:
        st.subheader("💰 Uang vs 📝 Tugas")
        tab_g1, tab_g2 = st.tabs(["Uang (Pie)", "Tugas (Status)"])
        with tab_g1:
            if not df_fin.empty:
                df_out = df_fin[df_fin['Tipe'] == 'Pengeluaran']
                if not df_out.empty:
                    st.plotly_chart(px.pie(df_out, values='Jumlah', names='Kategori', hole=0.4), use_container_width=True)
        with tab_g2:
            if not df_todo.empty and 'Status' in df_todo.columns:
                st.plotly_chart(px.pie(df_todo, names='Status', color='Status', color_discrete_map={'Pending':'red', 'Selesai':'green'}), use_container_width=True)

    with g2:
        st.subheader("✅ Top Habit")
        if not df_habit.empty and 'Habit' in df_habit.columns:
            df_done = df_habit[df_habit['Status'] == 'Done']
            if not df_done.empty:
                cnt = df_done['Habit'].value_counts().reset_index(); cnt.columns=['H','C']
                st.plotly_chart(px.bar(cnt, x='C', y='H', orientation='h'), use_container_width=True)

# === TAB 2: TODO ===
with tab1:
    c1, c2, c3 = st.columns([3,1,1])
    with c1: t_task = st.text_input("Tugas Baru", key="in_task")
    with c2: t_prio = st.selectbox("Prioritas", ["Tinggi", "Sedang", "Rendah"], key="in_prio")
    with c3: 
        st.write("")
        if st.button("➕ Tambah", use_container_width=True) and t_task:
            sheets["todo"].append_row([str(datetime.now()), t_task, t_prio, "Pending"]); clear_cache_and_rerun()

    if not df_todo.empty:
        with st.expander("📊 Grafik Prioritas"):
            prio = df_todo['Prioritas'].value_counts().reset_index(); prio.columns=['P','C']
            st.plotly_chart(px.bar(prio, x='P', y='C', color='P'), use_container_width=True)
        
        st.dataframe(df_todo, use_container_width=True)
        c_act1, c_act2 = st.columns(2)
        opts = [f"{i}. {row['Task']} ({row['Status']})" for i, row in df_todo.iterrows()]; sel = st.selectbox("Pilih Tugas:", opts, key="sel_todo") if opts else None
        if sel:
            idx = int(sel.split(".")[0])
            if c_act1.button("✅ Tandai Selesai"): sheets["todo"].update_cell(idx+2, 4, "Selesai"); clear_cache_and_rerun()
            if c_act2.button("🗑️ Hapus Tugas"): sheets["todo"].delete_rows(idx+2); clear_cache_and_rerun()

# === TAB 3: UANG ===
with tab2:
    with st.form("f_uang"):
        c1, c2 = st.columns(2); u_item = c1.text_input("Item"); u_kat = c2.selectbox("Kategori", ["Makan", "Transport", "Belanja", "Tagihan", "Lainnya"])
        c3, c4 = st.columns(2); u_jum = c3.number_input("Rp", step=1000); u_tipe = c4.selectbox("Tipe", ["Pengeluaran", "Pemasukan"])
        if st.form_submit_button("Simpan Transaksi"): sheets["fin"].append_row([str(datetime.now()), u_item, u_kat, u_jum, u_tipe]); clear_cache_and_rerun()

    if not df_fin.empty:
        st.write("### 📉 Tren Pengeluaran")
        df_trend = df_fin[df_fin['Tipe'] == 'Pengeluaran'].copy()
        if not df_trend.empty:
            df_trend['Tanggal'] = pd.to_datetime(df_trend['Tanggal']).dt.date
            daily = df_trend.groupby('Tanggal')['Jumlah'].sum().reset_index()
            st.plotly_chart(px.line(daily, x='Tanggal', y='Jumlah', markers=True), use_container_width=True)

        st.dataframe(df_fin, use_container_width=True)
        opts = [f"{i}. {row['Item']} ({row['Jumlah']})" for i, row in df_fin.iterrows()]; sel = st.selectbox("Pilih:", opts, key="sel_fin") if opts else None
        if sel and st.button("Hapus Data"): sheets["fin"].delete_rows(int(sel.split(".")[0])+2); clear_cache_and_rerun()

# === TAB 4: HABIT ===
with tab3:
    nh = st.text_input("Habit Baru"); 
    if st.button("Tambah Master Habit") and nh: sheets["habit"].append_row([str(date.today()), nh, "Belum"]); clear_cache_and_rerun()

    if not df_habit.empty:
        u_hab = df_habit['Habit'].unique(); today_str = str(date.today())
        st.write("### 🎯 Ceklis Hari Ini")
        for hb in u_hab:
            done = not df_habit[(df_habit['Habit'] == hb) & (df_habit['Tanggal'] == today_str) & (df_habit['Status'] == 'Done')].empty
            c1, c2 = st.columns([3, 1]); c1.write(f"**{hb}**")
            if done: c2.success("✅ Done")
            else: 
                if c2.button("Ceklis", key=f"h_{hb}"): sheets["habit"].append_row([today_str, hb, "Done"]); clear_cache_and_rerun()
        
        with st.expander("🗑️ Hapus Habit"):
             opts = [f"{i}. {row['Habit']}" for i, row in df_habit.iterrows()]; sel = st.selectbox("Hapus:", opts, key="sel_hab") if opts else None
             if sel and st.button("Hapus Permanen"): sheets["habit"].delete_rows(int(sel.split(".")[0])+2); clear_cache_and_rerun()

# === TAB 5: JURNAL ===
with tab4:
    curhat = st.text_area("Cerita hari ini...", height=100)
    if st.button("Analisis AI") and model and curhat:
        try:
            mood = model.generate_content(f"Satu kata emosi: {curhat}").text.strip()
            saran = model.generate_content(f"Saran: {curhat}").text.strip()
            sheets["journal"].append_row([str(datetime.now()), curhat, mood, saran]); st.balloons(); clear_cache_and_rerun()
        except Exception as e: st.error(f"Gagal: {e}")

    if not df_journal.empty and 'AI_Mood' in df_journal.columns:
        st.write("### 📈 Grafik Mood")
        try:
            mood_map = {"Senang": 5, "Semangat": 5, "Netral": 3, "Biasa": 3, "Lelah": 2, "Sedih": 1, "Marah": 1}
            df_journal['Score'] = df_journal['AI_Mood'].map(mood_map).fillna(3); df_journal['Waktu'] = pd.to_datetime(df_journal['Tanggal'])
            st.plotly_chart(px.line(df_journal, x='Waktu', y='Score', markers=True, title="Emosi"), use_container_width=True)
        except: pass
        
        with st.expander("Riwayat & Hapus"):
            for i, row in df_journal.iterrows(): st.write(f"**{row['Tanggal'][:10]}**: {row['Isi_Jurnal']} ({row.get('AI_Mood','-')})")
            opts = [f"{i}. {str(row['Isi_Jurnal'])[:15]}..." for i, row in df_journal.iterrows()]; sel = st.selectbox("Hapus:", opts, key="sel_jour") if opts else None
            if sel and st.button("Hapus Jurnal"): sheets["journal"].delete_rows(int(sel.split(".")[0])+2); clear_cache_and_rerun()

# === TAB 6: ADVISOR ===
with tab5:
    for i, row in df_advisor.iterrows():
        with st.chat_message("user"): st.write(row['Pertanyaan'])
        with st.chat_message("assistant"): st.write(row['Jawaban'])
    q = st.chat_input("Tanya...")
    if q and model:
        with st.chat_message("user"): st.write(q)
        with st.chat_message("assistant"):
            res = model.generate_content(q).text; st.write(res)
            sheets["advisor"].append_row([str(datetime.now()), q, res])