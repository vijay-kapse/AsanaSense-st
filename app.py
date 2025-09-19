# app.py
import streamlit as st
import base64
import os
from PIL import Image
import google.generativeai as genai
from gtts import gTTS
import tempfile

# -------------------------
# CONFIG
# -------------------------
st.set_page_config(page_title="AsanaSense", page_icon="🧘", layout="centered")

def configure_gemini() -> None:
    api_key = st.secrets.get("GOOGLE_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        st.error("⚠️ Set GOOGLE_API_KEY in Streamlit secrets or environment variables.")
        st.stop()
    genai.configure(api_key=api_key)

configure_gemini()

# -------------------------
# CUSTOM CSS (Glassmorphic UI)
# -------------------------
st.markdown("""
    <style>
    .stApp {
        background: linear-gradient(135deg, rgba(34,193,195,0.6), rgba(253,187,45,0.6));
        backdrop-filter: blur(15px);
        color: white;
    }
    .glass-card {
        padding: 25px;
        border-radius: 20px;
        background: rgba(255,255,255,0.1);
        backdrop-filter: blur(20px);
        box-shadow: 0 8px 32px rgba(0,0,0,0.3);
        text-align: center;
    }
    .title {
        font-size: 2rem;
        font-weight: bold;
        color: white;
        text-shadow: 1px 1px 2px black;
    }
    </style>
""", unsafe_allow_html=True)

# -------------------------
# HEADER
# -------------------------
st.markdown("<div class='glass-card'><p class='title'>🧘 AsanaSense</p><p>AI-powered yoga feedback</p></div>", unsafe_allow_html=True)

# -------------------------
# LIVE CAMERA INPUT
# -------------------------
img_file = st.camera_input("Capture your yoga pose 📸")

analysis_text = ""
if img_file and st.button("Analyze Pose"):
    img = Image.open(img_file)

    # Convert image to base64
    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
        img.save(tmp.name)
        image_path = tmp.name

    img_bytes = open(image_path, "rb").read()
    img_b64 = base64.b64encode(img_bytes).decode()

    st.image(img, caption="Your Pose", use_column_width=True)

    # -------------------------
    # GEMINI VISION API CALL
    # -------------------------
    model = genai.GenerativeModel("gemini-1.5-flash")
    prompt = "Analyze this yoga pose and provide corrective feedback in 3-4 concise sentences."

    try:
        response = model.generate_content([
            prompt,
            {"mime_type": "image/png", "data": img_bytes}
        ])
        analysis_text = response.text
        st.success("✅ Analysis Complete")
        st.markdown(f"**Feedback:** {analysis_text}")
    except Exception as e:
        st.error(f"❌ API Error: {str(e)}")

# -------------------------
# TEXT TO SPEECH
# -------------------------
if analysis_text:
    if st.button("🔊 Listen to Feedback"):
        tts = gTTS(analysis_text)
        tts_path = "feedback.mp3"
        tts.save(tts_path)
        with open(tts_path, "rb") as f:
            st.audio(f.read(), format="audio/mp3")

