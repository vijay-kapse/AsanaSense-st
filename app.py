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
# CUSTOM CSS
# -------------------------
st.markdown("""
    <style>
    .stApp {background: linear-gradient(135deg, rgba(34,193,195,0.6), rgba(253,187,45,0.6)); color:white;}
    .glass-card {padding:20px; border-radius:20px; background:rgba(255,255,255,0.1); backdrop-filter:blur(20px);}
    .title {font-size:2rem; font-weight:bold; text-shadow:1px 1px 2px black;}
    </style>
""", unsafe_allow_html=True)

# -------------------------
# HEADER
# -------------------------
st.markdown("<div class='glass-card'><p class='title'>🧘 AsanaSense</p><p>AI-powered yoga feedback</p></div>", unsafe_allow_html=True)

# -------------------------
# JAVASCRIPT VOICE LISTENER
# -------------------------
st.markdown("""
<script>
let recognition;
if (!window.recognitionStarted) {
    window.recognitionStarted = true;
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = false;
    recognition.lang = "en-US";
    recognition.start();

    recognition.onresult = function(event) {
        const transcript = event.results[event.results.length-1][0].transcript.trim().toLowerCase();
        if (transcript.includes("click")) {
            // Save trigger in localStorage
            localStorage.setItem("voice_trigger", "click");
            // Force streamlit reload
            window.location.reload();
        }
    };
}
</script>
""", unsafe_allow_html=True)

# -------------------------
# CHECK IF "CLICK" TRIGGERED
# -------------------------
voice_trigger = st.session_state.get("voice_trigger", False)
if "voice_trigger" not in st.session_state:
    st.session_state["voice_trigger"] = False

# Hack: Read trigger from browser localStorage via Streamlit
trigger = st.experimental_get_query_params().get("voice_trigger", None)

# -------------------------
# CAMERA CAPTURE & ANALYZE
# -------------------------
img_file = st.camera_input("Say 'click' to capture 📸")

if img_file:
    img = Image.open(img_file)
    st.image(img, caption="Your Pose", use_column_width=True)

    # Auto analyze immediately
    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
        img.save(tmp.name)
        image_path = tmp.name
        img_bytes = open(image_path, "rb").read()

    model = genai.GenerativeModel("gemini-1.5-flash")
    prompt = "Analyze this yoga pose and provide corrective feedback in 3-4 concise sentences."

    try:
        response = model.generate_content([prompt, {"mime_type": "image/png", "data": img_bytes}])
        feedback = response.text
        st.success("✅ Analysis Complete")
        st.markdown(f"**Feedback:** {feedback}")

        # Auto TTS playback
        tts = gTTS(feedback)
        tts_path = "feedback.mp3"
        tts.save(tts_path)
        with open(tts_path, "rb") as f:
            st.audio(f.read(), format="audio/mp3", autoplay=True)
    except Exception as e:
        st.error(f"❌ API Error: {str(e)}")


