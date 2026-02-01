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
st.set_page_config(page_title="My Life OS 12.0 (Archive Master)", layout="wide", page_icon="🧬")

# ==========================================
# 🔒 SISTEM KEAMANAN (LOGIN)
# ==========================================
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    if st.session_state["password_correct"]:
        return True

    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.title("🔒 Restricted Access")
        st.write("Sistem terkunci. Silakan masukkan kunci akses Anda.")
        pwd = st.text_input("Password:", type="password")
        if st.button("Buka Gembok 🔓"):
            if pwd == st.secrets["APP_PASSWORD"]:
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("⛔ Password Salah! Akses ditolak.")
    return False

if not check_password(): st.stop()

# ==========================================
# 🚀 APLIKASI UTAMA
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
        
        # Cek/Buat Tab Advisor jika belum ada
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

# --- 3. DATA LOADING (Cache) ---
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

# --- 4. SETUP AI ---
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
except: pass

# --- UTILITIES ---
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
        st.toast("Tabel diperbaiki!", icon="🛠️"); clear_cache_and_rerun()
    except: pass

# --- FUNGSI ARSIP PINTAR (UNIVERSAL) ---
def render_archive_system(df, date_col, title_col, subtitle_col=None, type_col=None):
    """
    Fungsi canggih untuk membuat arsip bertingkat: Tahun > Bulan > Hari.
    Digunakan ulang di ToDo, Uang, Jurnal, dan Advisor.
    """
    if df.empty:
        st.caption("Belum ada data arsip.")
        return

    try:
        # 1. Persiapan Data Tanggal
        df['DateObj'] = pd.to_datetime(df[date_col], errors='coerce')
        df['Tahun'] = df['DateObj'].dt.year
        df['Bulan'] = df['DateObj'].dt.month_name()
        df['Hari'] = df['DateObj'].dt.day_name()
        df['Tanggal_Angka'] = df['DateObj'].dt.day
        
        # Ambil daftar tahun unik
        years = sorted(df['Tahun'].dropna().unique(), reverse=True)
        
        if not years:
            st.caption("Format tanggal data tidak valid.")
            return

        # 2. Level 1: TAHUN (Expander)
        for y in years:
            with st.expander(f"📂 Arsip Tahun {int(y)}"):
                df_year = df[df['Tahun'] == y]
                
                # Level 2: BULAN (Tabs agar rapi dan tidak nested expander error)
                months = df_year['Bulan'].unique()
                if len(months) > 0:
                    tabs = st.tabs([str(m) for m in months])
                    
                    for i, m in enumerate(months):
                        with tabs[i]:
                            df_month = df_year[df_year['Bulan'] == m]
                            
                            # Level 3: HARI (Grouping by date)
                            dates = sorted(df_month['Tanggal_Angka'].unique(), reverse=True)
                            
                            for d in dates:
                                df_day = df_month[df_month['Tanggal_Angka'] == d]
                                day_name = df_day['Hari'].iloc[0] if not df_day.empty else ""
                                
                                st.markdown(f"**🗓️ {day_name}, {int(d)} {m} {int(y)}**")
                                
                                # Render Item
                                for idx, row in df_day.iterrows():
                                    title = row[title_col]
                                    sub = f"{row[subtitle_col]}" if subtitle_col and subtitle_col in row else ""
                                    
                                    # Warna khusus jika ada tipe (misal Keuangan)
                                    color_str = ""
                                    if type_col and type_col in row:
                                        color = "red" if row[type_col] == "Pengeluaran" else "green"
                                        color_str = f":{color}[{row[type_col]}]"
                                    
                                    st.caption(f"• {color_str} **{title}** {f'({sub})' if sub else ''}")
                                st.divider()
    except Exception as e:
        st.error(f"Gagal memuat arsip: {e}")

# --- SIDEBAR ---
with st.sidebar:
    st.title("🧬 My Life OS")
    if st.button("🔒 Logout"): st.session_state["password_correct"] = False; st.rerun()
    st.divider()

    xp_point = 0
    if not df_todo.empty and 'Status' in df_todo.columns: xp_point += len(df_todo[df_todo['Status'] == 'Selesai']) * 15
    if not df_habit.empty and 'Status' in df_habit.columns: xp_point += len(df_habit[df_habit['Status'] == 'Done']) * 10 
    level = int(xp_point / 200) + 1
    st.metric(f"Level {level}", f"{xp_point} XP")
    st.progress((xp_point % 200) / 200)
    
    with st.expander("🍅 Fokus Timer"):
        menit = st.number_input("Menit", 1, 120, 25)
        if st.button("Mulai"):
            bar = st.progress(0); t_s = st.empty()
            for i in range(menit * 60):
                t_s.caption(f"{menit*60 - i}s"); bar.progress((i+1)/(menit*60)); time.sleep(1)
            st.success("Selesai!")
    
    with st.expander("📥 Backup Excel"):
        if st.button("Download"):
            out = io.BytesIO()
            with pd.ExcelWriter(out, engine='xlsxwriter') as w:
                df_todo.to_excel(w, sheet_name='ToDo', index=False)
                df_fin.to_excel(w, sheet_name='Keuangan', index=False)
                df_habit.to_excel(w, sheet_name='Habits', index=False)
                df_journal.to_excel(w, sheet_name='Jurnal', index=False)
            st.download_button("Klik Download", out.getvalue(), f'Backup.xlsx', 'application/vnd.ms-excel')

    st.divider()
    if st.button("🛠️ Fix Error"): fix_headers_only()

# --- TABS ---
tab_home, tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["🏠 Home", "📝 ToDo", "💰 Uang", "✅ Habit", "📔 Jurnal", "🤖 Advisor", "🗄️ Database"])

with tab_home: # DASHBOARD
    st.header(f"Dashboard Level {level}")
    c1,c2,c3,c4 = st.columns(4)
    out=0
    if not df_fin.empty: 
        df_fin['Jumlah'] = pd.to_numeric(df_fin['Jumlah'], errors='coerce').fillna(0)
        out = df_fin[df_fin['Tipe']=='Pengeluaran']['Jumlah'].sum()
    c1.metric("Pengeluaran", f"Rp {out:,.0f}")
    
    pen=0; 
    if not df_todo.empty: pen = len(df_todo[df_todo['Status']=='Pending'])
    c2.metric("Task Pending", pen)
    
    hab=0
    if not df_habit.empty: hab = len(df_habit[(df_habit['Tanggal']==str(date.today())) & (df_habit['Status']=='Done')])
    c3.metric("Habit Today", hab)
    c4.metric("Total XP", xp_point)
    
    st.divider()
    g1, g2 = st.columns(2)
    with g1:
        st.subheader("Porsi Pengeluaran")
        if not df_fin.empty: 
            df_out = df_fin[df_fin['Tipe']=='Pengeluaran']
            if not df_out.empty: st.plotly_chart(px.pie(df_out, values='Jumlah', names='Kategori', hole=0.4), use_container_width=True)
    with g2:
        st.subheader("Konsistensi Habit")
        if not df_habit.empty:
            df_done = df_habit[df_habit['Status']=='Done']
            if not df_done.empty: 
                cnt=df_done['Habit'].value_counts().reset_index(); cnt.columns=['H','C']
                st.plotly_chart(px.bar(cnt, x='C', y='H', orientation='h'), use_container_width=True)

# === TAB 1: TODO (VISUAL + ARCHIVE) ===
with tab1:
    c1,c2,c3=st.columns([3,1,1])
    with c1: t=st.text_input("Tugas", key="t")
    with c2: p=st.selectbox("Prio", ["Tinggi","Sedang","Rendah"], key="p")
    with c3: 
        st.write(""); 
        if st.button("➕", use_container_width=True) and t: sheets["todo"].append_row([str(datetime.now()), t, p, "Pending"]); clear_cache_and_rerun()
    
    if not df_todo.empty:
        # Grafik & Tabel
        with st.expander("📊 Grafik & Tabel"):
             prio = df_todo['Prioritas'].value_counts().reset_index(); prio.columns=['P','C']
             c_g1, c_g2 = st.columns(2)
             c_g1.plotly_chart(px.bar(prio, x='P', y='C', color='P', title="Distribusi Prioritas"), use_container_width=True)
             c_g2.dataframe(df_todo, use_container_width=True) 
        
        st.write("### 📌 Tugas Pending")
        active_tasks = df_todo[df_todo['Status'] == 'Pending']
        
        if active_tasks.empty: st.info("Tidak ada tugas pending.")
        else:
            for i, row in active_tasks.iterrows():
                icon = "🔥" if row['Prioritas'] == "Tinggi" else "⚠️" if row['Prioritas'] == "Sedang" else "☕"
                with st.expander(f"{icon} {row['Task']} ({row['Prioritas']})"):
                    st.write(f"📅 {row['Tanggal']}")
                    c_act1, c_act2 = st.columns(2)
                    if c_act1.button("✅ Selesai", key=f"done_{i}"):
                        sheets["todo"].update_cell(i + 2, 4, "Selesai"); st.toast("Selesai!"); time.sleep(0.5); clear_cache_and_rerun()
                    if c_act2.button("🗑️ Hapus", key=f"del_todo_{i}"):
                        sheets["todo"].delete_rows(i + 2); st.toast("Dihapus"); time.sleep(0.5); clear_cache_and_rerun()
        
        st.divider()
        st.subheader("🗄️ Arsip Tugas (Tahun > Bulan > Hari)")
        render_archive_system(df_todo, 'Tanggal', 'Task', 'Status')

# === TAB 2: UANG (VISUAL + ARCHIVE) ===
with tab2:
    with st.form("u"):
        c1,c2=st.columns(2); i=c1.text_input("Item"); k=c2.selectbox("Kat", ["Makan","Transport","Belanja","Tagihan","Lainnya"])
        c3,c4=st.columns(2); j=c3.number_input("Rp", step=1000); tp=c4.selectbox("Tipe", ["Pengeluaran","Pemasukan"])
        if st.form_submit_button("Simpan"): sheets["fin"].append_row([str(datetime.now()), i, k, j, tp]); clear_cache_and_rerun()
    
    if not df_fin.empty:
        # Grafik
        with st.expander("📊 Grafik Keuangan"):
            df_trend = df_fin[df_fin['Tipe'] == 'Pengeluaran'].copy()
            if not df_trend.empty:
                df_trend['Tanggal'] = pd.to_datetime(df_trend['Tanggal']).dt.date
                daily = df_trend.groupby('Tanggal')['Jumlah'].sum().reset_index()
                st.plotly_chart(px.line(daily, x='Tanggal', y='Jumlah', markers=True, title="Tren Pengeluaran"), use_container_width=True)

        st.write("### 💳 20 Transaksi Terakhir")
        recent_fin = df_fin.tail(20)[::-1]
        for i, row in recent_fin.iterrows():
            color = "red" if row['Tipe'] == "Pengeluaran" else "green"
            with st.expander(f":{color}[Rp {row['Jumlah']:,}] - {row['Item']}"):
                st.write(f"📅 {row['Tanggal']} | 📂 {row['Kategori']}")
                if st.button("🗑️ Hapus", key=f"del_fin_{i}"):
                    sheets["fin"].delete_rows(i + 2); st.toast("Terhapus"); time.sleep(0.5); clear_cache_and_rerun()

        st.divider()
        st.subheader("🗄️ Arsip Keuangan (Tahun > Bulan > Hari)")
        render_archive_system(df_fin, 'Tanggal', 'Item', 'Jumlah', 'Tipe')

# === TAB 3: HABIT (VISUAL + ARCHIVE) ===
with tab3:
    nh=st.text_input("Habit Baru")
    if st.button("Tambah"): sheets["habit"].append_row([str(date.today()), nh, "Belum"]); clear_cache_and_rerun()
    
    if not df_habit.empty:
        # Grafik Habit (Dikembalikan)
        df_done = df_habit[df_habit['Status'] == 'Done']
        if not df_done.empty:
            perf = df_done['Habit'].value_counts().reset_index()
            perf.columns = ['Habit', 'Total Selesai']
            with st.expander("📊 Statistik Habit"):
                st.plotly_chart(px.bar(perf, x='Habit', y='Total Selesai', color='Total Selesai'), use_container_width=True)

        uh=df_habit['Habit'].unique(); today=str(date.today())
        st.write("### ✅ Ceklis Hari Ini")
        with st.container(border=True):
            for h in uh:
                done=not df_habit[(df_habit['Habit']==h)&(df_habit['Tanggal']==today)&(df_habit['Status']=='Done')].empty
                c1,c2=st.columns([3,1]); c1.write(f"**{h}**")
                if done: c2.success("Selesai")
                else: 
                    if c2.button("Ceklis", key=f"hb_{h}"): sheets["habit"].append_row([today, h, "Done"]); clear_cache_and_rerun()
        
        st.write("### ⚙️ Manajemen Habit")
        for h in uh:
            with st.expander(f"Habit: {h}"):
                if st.button(f"🗑️ Hapus Permanen '{h}'", key=f"del_hab_{h}"):
                    indices = df_habit[df_habit['Habit'] == h].index
                    sheets["habit"].delete_rows(indices[-1] + 2)
                    st.toast(f"Entry {h} dihapus"); time.sleep(0.5); clear_cache_and_rerun()

# === TAB 4: JURNAL (VISUAL + ARCHIVE) ===
with tab4:
    with st.container(border=True):
        st.subheader("Curhat ke AI")
        curhat = st.text_area("Cerita hari ini...", height=100)
        if st.button("✨ Analisis AI") and model and curhat:
            try:
                mood = model.generate_content(f"Satu kata emosi (Senang/Sedih/Marah/Netral/Semangat): {curhat}").text.strip()
                saran = model.generate_content(f"Berikan saran singkat 1 kalimat supportif: {curhat}").text.strip()
                sheets["journal"].append_row([str(datetime.now()), curhat, mood, saran])
                st.balloons(); clear_cache_and_rerun()
            except Exception as e: st.error(f"Error AI: {e}")

    if not df_journal.empty:
        # Grafik Mood (Dikembalikan)
        if 'AI_Mood' in df_journal.columns:
            try:
                mood_map = {"Senang": 5, "Semangat": 5, "Netral": 3, "Biasa": 3, "Lelah": 2, "Sedih": 1, "Marah": 1}
                df_journal['Score'] = df_journal['AI_Mood'].map(mood_map).fillna(3)
                df_journal['Waktu'] = pd.to_datetime(df_journal['Tanggal'])
                with st.expander("📊 Grafik Mood Tracker"):
                    fig = px.line(df_journal, x='Waktu', y='Score', markers=True, title="Naik Turun Emosi")
                    fig.update_yaxes(range=[0, 6], tickvals=[1,3,5], ticktext=["Sedih", "Netral", "Senang"])
                    st.plotly_chart(fig, use_container_width=True)
            except: pass

        st.write("### 📖 20 Jurnal Terakhir")
        recent_journal = df_journal.tail(20)[::-1]
        for i, row in recent_journal.iterrows():
            with st.expander(f"📅 {str(row['Tanggal'])[:10]} | {row.get('AI_Mood','-')}"):
                st.write(row['Isi_Jurnal'])
                st.info(f"💡 AI: {row.get('AI_Saran','-')}")
                if st.button("🗑️ Hapus", key=f"del_j_{i}"):
                    sheets["journal"].delete_rows(i + 2); st.toast("Terhapus!"); time.sleep(0.5); clear_cache_and_rerun()

        st.divider()
        st.subheader("🗄️ Arsip Cerita (Tahun > Bulan > Hari)")
        render_archive_system(df_journal, 'Tanggal', 'Isi_Jurnal', 'AI_Mood')

# === TAB 5: ADVISOR (VISUAL + ARCHIVE) ===
with tab5:
    st.subheader("Asisten Pribadi")
    
    q = st.chat_input("Tanya...")
    if q and model:
        with st.chat_message("user"): st.write(q)
        with st.chat_message("assistant"):
            res = model.generate_content(q).text; st.write(res); sheets["advisor"].append_row([str(datetime.now()), q, res]); st.rerun()

    st.divider()
    st.subheader("🗄️ Arsip Percakapan (Tahun > Bulan > Hari)")
    render_archive_system(df_advisor, 'Timestamp', 'Pertanyaan', 'Jawaban')

    if st.button("🔥 Hapus Semua Chat (Reset)"):
        sheets["advisor"].resize(rows=1); sheets["advisor"].resize(rows=1000); sheets["advisor"].update("A1:C1", [["Timestamp", "Pertanyaan", "Jawaban"]])
        st.success("Chat bersih!"); time.sleep(1); clear_cache_and_rerun()

# === TAB 6: DATABASE (ADMIN ONLY) ===
with tab6:
    st.header("🗄️ Database Center (Admin)")
    st.warning("Hati-hati! Tab ini menampilkan data mentah. Menghapus data di sini bersifat permanen.")
    
    tab_db1, tab_db2, tab_db3, tab_db4, tab_db5 = st.tabs(["ToDo", "Finance", "Habit", "Journal", "Advisor"])
    
    def render_admin_table(df, sheet_name, sheet_obj):
        if not df.empty:
            st.dataframe(df, use_container_width=True)
            st.write(f"**Total Data: {len(df)} Baris**")
            
            c_del1, c_del2 = st.columns([3, 1])
            with c_del1:
                row_to_del = st.number_input(f"Hapus Baris ID (Index) di {sheet_name}:", min_value=0, max_value=len(df)-1, step=1, key=f"num_{sheet_name}")
            with c_del2:
                st.write(""); st.write("")
                if st.button(f"🗑️ Hapus ID {row_to_del}", key=f"btn_del_{sheet_name}"):
                    sheet_obj.delete_rows(row_to_del + 2)
                    st.success(f"Baris {row_to_del} dihapus!")
                    time.sleep(1)
                    clear_cache_and_rerun()
        else:
            st.info("Tabel Kosong")

    with tab_db1: render_admin_table(df_todo, "ToDo", sheets["todo"])
    with tab_db2: render_admin_table(df_fin, "Finance", sheets["fin"])
    with tab_db3: render_admin_table(df_habit, "Habit", sheets["habit"])
    with tab_db4: render_admin_table(df_journal, "Journal", sheets["journal"])
    with tab_db5: render_admin_table(df_advisor, "Advisor", sheets["advisor"])