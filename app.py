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
st.set_page_config(page_title="My Life OS 9.0 (Complete)", layout="wide", page_icon="🧬")

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
        pwd = st.text_input("Password:", type="password")
        if st.button("Masuk"):
            if pwd == st.secrets["APP_PASSWORD"]:
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("⛔ Password Salah")
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
tab_home, tab1, tab2, tab3, tab4, tab5 = st.tabs(["🏠 Home", "📝 ToDo", "💰 Uang", "✅ Habit", "📔 Jurnal", "🤖 Advisor"])

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
        if not df_fin.empty: 
            df_out = df_fin[df_fin['Tipe']=='Pengeluaran']
            if not df_out.empty: st.plotly_chart(px.pie(df_out, values='Jumlah', names='Kategori', hole=0.4), use_container_width=True)
    with g2:
        if not df_habit.empty:
            df_done = df_habit[df_habit['Status']=='Done']
            if not df_done.empty: 
                cnt=df_done['Habit'].value_counts().reset_index(); cnt.columns=['H','C']
                st.plotly_chart(px.bar(cnt, x='C', y='H', orientation='h'), use_container_width=True)

with tab1: # TODO
    c1,c2,c3=st.columns([3,1,1])
    with c1: t=st.text_input("Tugas", key="t")
    with c2: p=st.selectbox("Prio", ["Tinggi","Sedang","Rendah"], key="p")
    with c3: 
        st.write(""); 
        if st.button("➕", use_container_width=True) and t: sheets["todo"].append_row([str(datetime.now()), t, p, "Pending"]); clear_cache_and_rerun()
    
    if not df_todo.empty:
        # --- GRAFIK PRIORITAS DIKEMBALIKAN ---
        with st.expander("📊 Grafik Prioritas"):
             prio = df_todo['Prioritas'].value_counts().reset_index(); prio.columns=['P','C']
             st.plotly_chart(px.bar(prio, x='P', y='C', color='P'), use_container_width=True)
        
        st.dataframe(df_todo, use_container_width=True)
        opts=[f"{i}. {r['Task']}" for i,r in df_todo.iterrows()]; sel=st.selectbox("Pilih:", opts, key="st") if opts else None
        c_a1,c_a2=st.columns(2)
        if sel:
            idx=int(sel.split(".")[0])+2
            if c_a1.button("✅ Selesai"): sheets["todo"].update_cell(idx,4,"Selesai"); clear_cache_and_rerun()
            if c_a2.button("🗑️ Hapus"): sheets["todo"].delete_rows(idx); clear_cache_and_rerun()

with tab2: # UANG
    with st.form("u"):
        c1,c2=st.columns(2); i=c1.text_input("Item"); k=c2.selectbox("Kat", ["Makan","Transport","Belanja","Tagihan","Lainnya"])
        c3,c4=st.columns(2); j=c3.number_input("Rp", step=1000); tp=c4.selectbox("Tipe", ["Pengeluaran","Pemasukan"])
        if st.form_submit_button("Simpan"): sheets["fin"].append_row([str(datetime.now()), i, k, j, tp]); clear_cache_and_rerun()
    
    if not df_fin.empty:
        # --- GRAFIK TREN DIKEMBALIKAN ---
        st.write("### 📉 Tren Pengeluaran")
        df_trend = df_fin[df_fin['Tipe'] == 'Pengeluaran'].copy()
        if not df_trend.empty:
            df_trend['Tanggal'] = pd.to_datetime(df_trend['Tanggal']).dt.date
            daily = df_trend.groupby('Tanggal')['Jumlah'].sum().reset_index()
            st.plotly_chart(px.line(daily, x='Tanggal', y='Jumlah', markers=True), use_container_width=True)

        st.dataframe(df_fin, use_container_width=True)
        opts=[f"{i}. {r['Item']} ({r['Jumlah']})" for i,r in df_fin.iterrows()]; sel=st.selectbox("Hapus:", opts, key="sf") if opts else None
        if sel and st.button("Hapus Data"): sheets["fin"].delete_rows(int(sel.split(".")[0])+2); clear_cache_and_rerun()

with tab3: # HABIT
    nh=st.text_input("Habit Baru")
    if st.button("Tambah"): sheets["habit"].append_row([str(date.today()), nh, "Belum"]); clear_cache_and_rerun()
    
    if not df_habit.empty:
        # --- GRAFIK HABIT DIKEMBALIKAN ---
        df_done = df_habit[df_habit['Status'] == 'Done']
        if not df_done.empty:
            perf = df_done['Habit'].value_counts().reset_index()
            perf.columns = ['Habit', 'Total Selesai']
            with st.expander("📊 Statistik Habit"):
                st.plotly_chart(px.bar(perf, x='Habit', y='Total Selesai', color='Total Selesai'), use_container_width=True)

        uh=df_habit['Habit'].unique(); today=str(date.today())
        st.write("### Ceklis Hari Ini")
        for h in uh:
            done=not df_habit[(df_habit['Habit']==h)&(df_habit['Tanggal']==today)&(df_habit['Status']=='Done')].empty
            c1,c2=st.columns([3,1]); c1.write(f"**{h}**")
            if done: c2.success("✅")
            else: 
                if c2.button("Ceklis", key=f"hb_{h}"): sheets["habit"].append_row([today, h, "Done"]); clear_cache_and_rerun()
        with st.expander("🗑️ Hapus Master Habit"):
             opts=[f"{i}. {r['Habit']}" for i,r in df_habit.iterrows()]; sel=st.selectbox("Pilih:", opts, key="sh") if opts else None
             if sel and st.button("Hapus Permanen"): sheets["habit"].delete_rows(int(sel.split(".")[0])+2); clear_cache_and_rerun()

# === TAB 4: JURNAL (VISUAL LENGKAP + KARTU) ===
with tab4:
    with st.container(border=True):
        st.subheader("Curhat ke AI")
        curhat = st.text_area("Cerita hari ini...", height=100)
        if st.button("✨ Analisis AI") and model and curhat:
            try:
                mood = model.generate_content(f"Satu kata emosi dari teks ini (Senang/Sedih/Marah/Netral/Semangat): {curhat}").text.strip()
                saran = model.generate_content(f"Berikan saran singkat 1 kalimat supportif untuk: {curhat}").text.strip()
                sheets["journal"].append_row([str(datetime.now()), curhat, mood, saran])
                st.balloons()
                clear_cache_and_rerun()
            except Exception as e: st.error(f"Error AI: {e}")

    if not df_journal.empty:
        st.divider()
        # 1. Grafik Mood (Line Chart)
        if 'AI_Mood' in df_journal.columns:
            try:
                mood_map = {"Senang": 5, "Semangat": 5, "Netral": 3, "Biasa": 3, "Lelah": 2, "Sedih": 1, "Marah": 1}
                df_journal['Score'] = df_journal['AI_Mood'].map(mood_map).fillna(3)
                df_journal['Waktu'] = pd.to_datetime(df_journal['Tanggal'])
                fig = px.line(df_journal, x='Waktu', y='Score', markers=True, title="Grafik Perasaan (Naik Turun Emosi)")
                fig.update_yaxes(range=[0, 6], tickvals=[1,3,5], ticktext=["Sedih/Marah", "Netral", "Senang"])
                st.plotly_chart(fig, use_container_width=True)
            except: pass
        
        # 2. Interactive List (Card Style)
        st.write("### 📖 Riwayat Jurnal")
        for i, row in df_journal[::-1].iterrows():
            with st.container(border=True):
                c_head1, c_head2 = st.columns([3, 1])
                c_head1.markdown(f"**📅 {str(row['Tanggal'])[:16]}**")
                c_head2.markdown(f"*{row.get('AI_Mood','-')}*")
                
                st.write(row['Isi_Jurnal'])
                st.info(f"💡 Advisor: {row.get('AI_Saran','-')}")
                
                if st.button("Hapus Entry Ini", key=f"del_j_{i}"):
                    sheets["journal"].delete_rows(i + 2) 
                    st.toast("Terhapus!")
                    time.sleep(1)
                    clear_cache_and_rerun()

# === TAB 5: ADVISOR (HAPUS CHAT) ===
with tab5:
    st.subheader("Asisten Pribadi")
    for i, row in df_advisor.iterrows():
        with st.chat_message("user"): st.write(row['Pertanyaan'])
        with st.chat_message("assistant"): st.write(row['Jawaban'])
    
    q = st.chat_input("Tanya saran, ide, atau curhat...")
    if q and model:
        with st.chat_message("user"): st.write(q)
        with st.chat_message("assistant"):
            res = model.generate_content(q).text
            st.write(res)
            sheets["advisor"].append_row([str(datetime.now()), q, res])
    
    st.divider()
    with st.expander("🗑️ Pengaturan Chat"):
        if st.button("🔥 Hapus Semua Chat Advisor"):
            sheets["advisor"].resize(rows=1)
            sheets["advisor"].resize(rows=1000)
            sheets["advisor"].update("A1:C1", [["Timestamp", "Pertanyaan", "Jawaban"]])
            st.success("Chat bersih!"); time.sleep(1); clear_cache_and_rerun()