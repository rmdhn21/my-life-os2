import streamlit as st
import google.generativeai as genai

st.set_page_config(page_title="Cek Model Gemini", layout="centered")

st.title("🕵️ Detektif Model Gemini")
st.write("Memeriksa izin akses API Key Anda ke server Google...")

# 1. Ambil API Key dari secrets.toml
try:
    if "GEMINI_API_KEY" in st.secrets:
        api_key = st.secrets["GEMINI_API_KEY"]
        genai.configure(api_key=api_key)
        st.success("✅ API Key DITEMUKAN di secrets.toml")
    else:
        st.error("❌ API Key TIDAK DITEMUKAN di secrets.toml. Cek file secrets Anda.")
        st.stop()
except Exception as e:
    st.error(f"Error membaca secrets: {e}")
    st.stop()

# 2. Tanya Google: Model apa yang tersedia?
if st.button("🔍 Cek Daftar Model Sekarang"):
    st.write("---")
    st.write("### 📋 Daftar Model yang BISA Anda Pakai:")
    
    try:
        # Ini perintah untuk melist semua model yang tersedia buat akun Anda
        found_any = False
        for m in genai.list_models():
            # Kita hanya cari model yang bisa generate text (generateContent)
            if 'generateContent' in m.supported_generation_methods:
                st.code(m.name) # Tampilkan nama modelnya
                found_any = True
        
        if not found_any:
            st.warning("Aneh... Tidak ada model text yang ditemukan. Akun mungkin belum aktif?")
            
    except Exception as e:
        st.error(f"❌ Gagal menghubungi Google: {e}")
        st.info("Kemungkinan penyebab: API Key salah, Kuota habis, atau Library perlu update.")

# 3. Tes Langsung
st.write("---")
st.write("### 🧪 Tes Nyali (Uji Coba)")
model_name = st.text_input("Salin nama model dari daftar di atas (misal: models/gemini-1.5-flash)", "models/gemini-1.5-flash")

if st.button("Kirim Pesan 'Halo'"):
    try:
        model = genai.GenerativeModel(model_name)
        response = model.generate_content("Halo, apakah kamu hidup?")
        st.success("✅ BERHASIL BALAS!")
        st.write(f"Jawabannya: {response.text}")
    except Exception as e:
        st.error(f"❌ Gagal pakai model ini: {e}")