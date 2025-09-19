# app.py
import streamlit as st
from streamlit_webrtc import webrtc_streamer, VideoTransformerBase, AudioProcessorBase
import av, queue, os, tempfile
import google.generativeai as genai
from gtts import gTTS
import torch
import base64
from PIL import Image

# -----------------------------
# GEMINI CONFIG
# -----------------------------
def configure_gemini():
    api_key = st.secrets.get("GOOGLE_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        st.error("⚠️ Set GOOGLE_API_KEY in secrets or env vars")
        st.stop()
    genai.configure(api_key=api_key)

configure_gemini()

# -----------------------------
# SPEECH RECOGNITION (Whisper tiny)
# -----------------------------
import whisper
model = whisper.load_model("tiny")

class AudioProcessor(AudioProcessorBase):
    def __init__(self):
        self.q = queue.Queue()
    def recv_audio(self, frame: av.AudioFrame) -> av.AudioFrame:
        pcm = frame.to_ndarray()
        self.q.put(pcm)
        return frame

audio_processor = AudioProcessor()

# -----------------------------
# VIDEO CAPTURE
# -----------------------------
frame_queue = queue.Queue()

class VideoTransformer(VideoTransformerBase):
    def transform(self, frame):
        img = frame.to_ndarray(format="bgr24")
        frame_queue.put(img)
        return frame

# -----------------------------
# STREAMERS
# -----------------------------
st.title("🧘 AsanaSense - Hands Free")

ctx = webrtc_streamer(
    key="asana",
    video_transformer_factory=VideoTransformer,
    audio_processor_factory=lambda: audio_processor,
    media_stream_constraints={"video": True, "audio": True}
)

# -----------------------------
# LOOP: Check for hotword
# -----------------------------
if ctx.state.playing:
    if not audio_processor.q.empty():
        pcm = audio_processor.q.get()
        # save temp wav
        tmp_wav = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        import soundfile as sf
        sf.write(tmp_wav.name, pcm, 16000)
        result = model.transcribe(tmp_wav.name)
        if "click" in result["text"].lower():
            st.success("🎤 Heard 'click' – capturing pose...")

            if not frame_queue.empty():
                frame = frame_queue.get()
                # Save frame as PNG
                img_path = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name
                Image.fromarray(frame).save(img_path)
                st.image(frame, caption="Captured Pose")

                # GEMINI VISION
                with open(img_path, "rb") as f:
                    img_bytes = f.read()

                gmodel = genai.GenerativeModel("gemini-1.5-flash")
                prompt = "Analyze this yoga pose and provide corrective feedback."
                try:
                    resp = gmodel.generate_content([prompt, {"mime_type":"image/png","data":img_bytes}])
                    feedback = resp.text
                    st.markdown(f"**Feedback:** {feedback}")

                    # TTS playback
                    tts = gTTS(feedback)
                    tts_path = "feedback.mp3"
                    tts.save(tts_path)
                    with open(tts_path, "rb") as f:
                        st.audio(f.read(), format="audio/mp3", autoplay=True)
                except Exception as e:
                    st.error(str(e))




