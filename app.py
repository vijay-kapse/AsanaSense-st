import streamlit as st
import google.generativeai as genai
from PIL import Image
import os

# Configure Gemini API
if "GOOGLE_API_KEY" not in st.secrets:
    st.error("⚠️ Please set your GOOGLE_API_KEY in Streamlit secrets.")
else:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])

# Streamlit page setup
st.set_page_config(page_title="AsanaSense", layout="wide")
st.title("🧘‍♂️ AsanaSense - Yoga Pose Analyzer")
st.write("Upload a yoga pose image and let AI analyze correctness and improvements.")

# File uploader
uploaded_file = st.file_uploader("Upload a yoga pose image", type=["jpg", "jpeg", "png"])

if uploaded_file is not None:
    # Show uploaded image
    image = Image.open(uploaded_file)
    st.image(image, caption="Uploaded Image", use_column_width=True)

    if st.button("🔍 Analyze Pose"):
        with st.spinner("Analyzing with Gemini..."):
            try:
                model = genai.GenerativeModel("gemini-1.5-flash")

                prompt = (
                    "You are a yoga expert. Analyze this yoga pose. "
                    "1. Identify the asana name. "
                    "2. Evaluate correctness of alignment. "
                    "3. Suggest 2–3 improvements. "
                    "4. Highlight potential risks if done incorrectly."
                )

                response = model.generate_content([prompt, image])

                st.subheader("📊 Analysis Result")
                if response and response.text:
                    st.write(response.text)
                else:
                    st.warning("No response received from Gemini.")

            except Exception as e:
                st.error(f"Error: {e}")
