import streamlit as st
import google.generativeai as genai
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import json
import plotly.express as px

# --- PAGE CONFIG ---
st.set_page_config(page_title="My Life OS", layout="wide", page_icon="🧬")

# --- KONEKSI DATABASE & AI ---
@st.cache_resource
def init_connection():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        # Mengambil credentials dari secrets
        creds_dict = json.loads(st.secrets["GCP_SERVICE_ACCOUNT"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        
        sh = client.open("productivity_db")
        return {
            "todo": sh.worksheet("todos"),
            "fin": sh.worksheet("finance"),
            "habit": sh.worksheet("habits"),
            "journal": sh.worksheet("journal")
        }
    except Exception as e:
        st.error(f"Error Koneksi Database: {e}")
        return None

sheets = init_connection()

try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash')
except:
    pass # Error ditangani nanti jika key kosong

# --- AI PARSER ---
def ai_brain(text, mode):
    today = datetime.now().strftime('%Y-%m-%d')
    prompts = {
        "todo": f"Analisis: '{text}'. Context: {today}. JSON: {{'task': 'str', 'deadline': 'YYYY-MM-DD', 'is_recurring': bool, 'frequency': 'str'}}",
        "finance": f"Analisis: '{text}'. JSON: {{'item': 'str', 'category': 'str', 'amount': int, 'type': 'expense/income'}}",
        "habit": f"Analisis: '{text}'. JSON: {{'habit_name': 'str', 'status': 'Done'}}",
        "journal": f"Analisis: '{text}'. JSON: {{'mood_score': 1-10, 'tags': 'str'}}"
    }
    try:
        response = model.generate_content(prompts[mode] + " Output JSON only.")
        clean = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(clean)
    except:
        return None

# --- UI ---
st.title("🧬 My AI Life OS")

# Dashboard Mini
if sheets:
    df_f = pd.DataFrame(sheets["fin"].get_all_records())
    df_j = pd.DataFrame(sheets["journal"].get_all_records())
    
    col1, col2, col3 = st.columns(3)
    
    # Saldo
    saldo = 0
    if not df_f.empty:
        df_f['amount'] = pd.to_numeric(df_f['amount'])
        saldo = df_f[df_f['type']=='income']['amount'].sum() - df_f[df_f['type']=='expense']['amount'].sum()
    col1.metric("💰 Saldo", f"Rp {saldo:,.0f}")
    
    # Mood
    mood = df_j['mood_score'].mean() if not df_j.empty else 0
    col2.metric("😊 Mood Avg", f"{mood:.1f}/10")

st.divider()

# Tabs
t1, t2, t3, t4, t5 = st.tabs(["📝 ToDo", "💰 Uang", "✅ Habit", "📔 Jurnal", "🤖 Advisor"])

# 1. TODO
with t1:
    txt = st.text_input("Tugas baru...", key="t")
    if st.button("Simpan Task") and txt:
        d = ai_brain(txt, "todo")
        if d:
            sheets["todo"].append_row([d['task'], "Pending", d['deadline'], 1 if d['is_recurring'] else 0, d['frequency']])
            st.success("Masuk!")
            st.rerun()
    st.dataframe(pd.DataFrame(sheets["todo"].get_all_records()), use_container_width=True)

# 2. UANG
with t2:
    txt = st.text_input("Catat uang...", key="f")
    if st.button("Simpan Uang") and txt:
        d = ai_brain(txt, "finance")
        if d:
            sheets["fin"].append_row([datetime.now().strftime('%Y-%m-%d'), d['item'], d['category'], d['amount'], d['type']])
            st.success("Masuk!")
            st.rerun()
    
    if not df_f.empty:
        # Grafik
        fig = px.pie(df_f[df_f['type']=='expense'], values='amount', names='category', hole=0.4)
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df_f, use_container_width=True)

# 3. HABIT
with t3:
    txt = st.text_input("Kebiasaan...", key="h")
    if st.button("Ceklis Habit") and txt:
        d = ai_brain(txt, "habit")
        if d:
            sheets["habit"].append_row([datetime.now().strftime('%Y-%m-%d'), d['habit_name'], "Done"])
            st.success("Good job!")
            st.rerun()
    st.dataframe(pd.DataFrame(sheets["habit"].get_all_records()), use_container_width=True)

# 4. JURNAL
with t4:
    txt = st.text_area("Cerita hari ini...")
    if st.button("Simpan Jurnal") and txt:
        d = ai_brain(txt, "journal")
        if d:
            sheets["journal"].append_row([datetime.now().strftime('%Y-%m-%d'), txt, d['mood_score'], d['tags']])
            st.success("Tercatat.")
            st.rerun()
    
    if not df_j.empty:
        st.line_chart(df_j, y="mood_score")

# 5. ADVISOR
with t5:
    if st.button("Analisis Hidup Saya"):
        with st.spinner("Mikir..."):
            summary = f"Finance Last 5: {df_f.tail(5).to_string() if not df_f.empty else ''}"
            res = model.generate_content(f"Berikan saran keuangan & produktivitas singkat dan tajam berdasarkan data ini: {summary}")
            st.markdown(res.text)
