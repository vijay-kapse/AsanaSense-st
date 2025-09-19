import base64
import io
import json
import os
from typing import Any, Dict, Optional

import streamlit as st
from PIL import Image

from asana_component import render as render_asana_component

try:
    import google.generativeai as genai
except ImportError as exc:  # noqa: N813
    raise RuntimeError(
        "google-generativeai must be installed. Run 'pip install -r requirements.txt'."
    ) from exc


st.set_page_config(page_title="AsanaSense", page_icon="🧘", layout="wide")


def configure_gemini() -> None:
    api_key = st.secrets.get("GOOGLE_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        st.error("⚠️ Set GOOGLE_API_KEY in Streamlit secrets or environment variables.")
        st.stop()
    genai.configure(api_key=api_key)


def decode_base64_image(data: str) -> Image.Image:
    if "," in data:
        data = data.split(",", 1)[1]
    try:
        image_bytes = base64.b64decode(data)
    except base64.binascii.Error as exc:
        raise ValueError("Invalid base64 image payload") from exc
    try:
        image = Image.open(io.BytesIO(image_bytes))
    except Exception as exc:  # noqa: BLE001
        raise ValueError("Unable to open image") from exc
    return image.convert("RGB")


def normalize_image(image: Image.Image) -> bytes:
    max_side = 768
    ratio = min(max_side / image.width, max_side / image.height, 1.0)
    if ratio < 1.0:
        new_size = (int(image.width * ratio), int(image.height * ratio))
        image = image.resize(new_size, Image.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=90)
    buffer.seek(0)
    return buffer.read()


def build_prompt(extra_context: Optional[str]) -> str:
    base_prompt = (
        "You are an elite yoga coach evaluating a practitioner's pose from a photograph. "
        "Provide precise, empathetic coaching in short paragraphs. "
        "Respond strictly in compact JSON with the keys: "
        "asanaName (string), alignmentHighlights (array of strings), improvementTips (array), "
        "riskWarnings (array), coachingCopy (string under 120 words)."
    )
    if extra_context:
        base_prompt += f" Additional context: {extra_context}."
    base_prompt += " Keep arrays concise (2-3 bullet points each)."
    return base_prompt


def parse_response_text(text: str) -> Dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`\n")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError("Unable to parse Gemini response") from exc


def analyze_pose(image_base64: str, extra_prompt: Optional[str]) -> tuple[Dict[str, Any], str]:
    image = decode_base64_image(image_base64)
    normalized = normalize_image(image)

    model = genai.GenerativeModel("gemini-1.5-flash")
    prompt = build_prompt(extra_prompt)

    try:
        response = model.generate_content(
            [
                prompt,
                {
                    "mime_type": "image/jpeg",
                    "data": normalized,
                },
            ]
        )
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Gemini request failed: {exc}") from exc

    text = getattr(response, "text", None)
    if not text:
        raise RuntimeError("No response text from Gemini")

    feedback = parse_response_text(text)
    return feedback, text


def init_state() -> None:
    st.session_state.setdefault("system_state", "ready")
    st.session_state.setdefault("feedback", None)
    st.session_state.setdefault("raw_text", "")
    st.session_state.setdefault("voice_enabled", False)
    st.session_state.setdefault("voice_supported", True)
    st.session_state.setdefault("last_event_id", None)
    st.session_state.setdefault("last_spoken_copy", "")
    st.session_state.setdefault(
        "status_text", "Say \"analyze\" or press the Analyze button to capture."
    )


def main() -> None:
    configure_gemini()
    init_state()

    status_map = {
        "listening": "Say \"analyze\" to capture a frame.",
        "processing": "Hold steady while we analyze your pose.",
        "error": "Something went wrong. Please check permissions and try again.",
    }
    state = st.session_state["system_state"]
    default_status = status_map.get(state, "Say \"analyze\" or press the Analyze button to capture.")
    if state == "error":
        status_text = st.session_state.get("status_text", default_status)
    else:
        status_text = default_status
    st.session_state["status_text"] = status_text

    props: Dict[str, Any] = {
        "systemState": state,
        "feedback": st.session_state["feedback"],
        "rawText": st.session_state["raw_text"],
        "voiceEnabled": st.session_state["voice_enabled"],
        "voiceSupported": st.session_state["voice_supported"],
        "statusText": status_text,
        "shouldSpeak": False,
        "lastCaptureId": st.session_state.get("last_processed_capture_id"),
    }

    feedback = st.session_state.get("feedback")
    if (
        feedback
        and feedback.get("coachingCopy")
        and feedback["coachingCopy"] != st.session_state.get("last_spoken_copy")
    ):
        props["shouldSpeak"] = True
        st.session_state["last_spoken_copy"] = feedback["coachingCopy"]

    event = render_asana_component(props, key="asana-sense-holo")

    if not event:
        return

    if not isinstance(event, dict):
        st.warning("Received unexpected payload from UI component.")
        return

    event_id = event.get("eventId")
    last_id = st.session_state.get("last_event_id")
    if event_id and event_id == last_id:
        return
    if event_id:
        st.session_state["last_event_id"] = event_id

    event_type = event.get("type")

    if event_type == "toggle_voice":
        st.session_state["voice_enabled"] = bool(event.get("enable"))
        st.session_state["system_state"] = (
            "listening" if st.session_state["voice_enabled"] else "ready"
        )
        st.experimental_rerun()

    if event_type == "voice_unsupported":
        st.session_state["voice_supported"] = False
        st.session_state["voice_enabled"] = False
        st.session_state["system_state"] = "ready"
        st.experimental_rerun()

    if event_type == "camera_error":
        st.session_state["system_state"] = "error"
        st.session_state["status_text"] = (
            "Camera access failed. Please allow camera permissions and reload."
        )
        st.experimental_rerun()

    if event_type == "voice_error":
        st.session_state["system_state"] = "error"
        st.session_state["voice_enabled"] = False
        st.session_state["status_text"] = "Voice recognition failed. You can still click Analyze."
        st.experimental_rerun()

    if event_type == "voice_transcript":
        transcript = event.get("transcript", "")
        if transcript:
            st.toast(f"Heard: {transcript}")
        return

    if event_type == "capture_error":
        st.warning("Unable to capture video frame. Try again.")
        st.session_state["system_state"] = "error"
        st.experimental_rerun()

    if event_type == "capture":
        image_base64 = event.get("imageBase64")
        if not image_base64:
            st.warning("No image data received from capture.")
            return
        st.session_state["system_state"] = "processing"
        st.session_state["status_text"] = "Analyzing pose..."
        with st.spinner("Analyzing pose with Gemini..."):
            try:
                feedback_data, raw_text = analyze_pose(image_base64, None)
            except (RuntimeError, ValueError) as exc:
                st.error(str(exc))
                st.session_state["system_state"] = "error"
                st.experimental_rerun()
                return
        st.session_state["feedback"] = feedback_data
        st.session_state["raw_text"] = raw_text
        st.session_state["system_state"] = (
            "listening" if st.session_state["voice_enabled"] else "ready"
        )
        st.session_state["status_text"] = "Say \"analyze\" or press Analyze to capture."
        st.session_state["last_processed_capture_id"] = event.get("eventId")
        st.experimental_rerun()


if __name__ == "__main__":
    main()
