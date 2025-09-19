import base64
import io
import json
import os
from typing import Any, Dict, Optional

import streamlit as st
from PIL import Image

try:
    import google.generativeai as genai
except ImportError as exc:  # noqa: N813
    raise RuntimeError(
        "google-generativeai must be installed. Run 'pip install -r requirements.txt'."
    ) from exc


st.set_page_config(page_title="AsanaSense", page_icon="🧘", layout="wide")


def configure_gemini() -> str:
    api_key = st.secrets.get("GOOGLE_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        st.error("⚠️ Set GOOGLE_API_KEY in Streamlit secrets or environment variables.")
        st.stop()
    genai.configure(api_key=api_key)
    return api_key


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
        raise ValueError('Unable to parse Gemini response') from exc


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


def escape_json_for_script(payload: Dict[str, Any]) -> str:
    dumped = json.dumps(payload).replace("<", "\\u003c")
    return dumped


def build_component_html(props: Dict[str, Any]) -> str:
    props_json = escape_json_for_script(props)
    template = """
<!DOCTYPE html>
<html lang=\"en\">
<head>
<meta charset=\"UTF-8\" />
<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\" />
<link rel=\"preconnect\" href=\"https://fonts.googleapis.com\">
<link rel=\"preconnect\" href=\"https://fonts.gstatic.com\" crossorigin>
<link href=\"https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap\" rel=\"stylesheet\">
<style>
  :root {{
    color-scheme: dark;
    font-family: 'Inter', system-ui, sans-serif;
  }}
  body {{
    margin: 0;
    background: radial-gradient(circle at 20% 20%, rgba(79, 70, 229, 0.55), transparent 55%),
                radial-gradient(circle at 80% 0%, rgba(14, 165, 233, 0.35), transparent 55%),
                radial-gradient(circle at 50% 100%, rgba(168, 85, 247, 0.35), transparent 60%),
                #020617;
    color: #e2e8f0;
  }}
  * {{ box-sizing: border-box; }}
  .page {{
    max-width: 1200px;
    margin: 0 auto;
    padding: 40px 32px 64px;
  }}
  header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 24px;
  }}
  .brand-mark {{
    display: flex;
    align-items: center;
    gap: 14px;
  }}
  .brand-icon {{
    width: 48px;
    height: 48px;
    border-radius: 18px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: linear-gradient(135deg, #35a0ff, #9965f4);
    font-size: 26px;
  }}
  .status-pill {{
    border-radius: 9999px;
    border: 1px solid rgba(255, 255, 255, 0.08);
    padding: 6px 16px;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.28em;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: rgba(255, 255, 255, 0.06);
    color: #cbd5f5;
  }}
  .status-dot {{
    width: 8px;
    height: 8px;
    border-radius: 9999px;
    background: #5eead4;
    animation: pulse 1.8s ease-in-out infinite;
  }}
  .status-dot.listening {{ background: #38bdf8; }}
  .status-dot.processing {{ background: #c084fc; }}
  .status-dot.error {{ background: #f87171; animation: none; }}
  @keyframes pulse {{
    0%, 100% {{ transform: scale(1); opacity: 0.9; }}
    50% {{ transform: scale(1.25); opacity: 0.6; }}
  }}
  main {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
    gap: 64px;
    margin-top: 56px;
  }}
  .hero {{
    display: flex;
    flex-direction: column;
    gap: 36px;
  }}
  .hero h1 {{
    font-size: clamp(42px, 5vw, 64px);
    line-height: 1.05;
    margin: 0;
  }}
  .hero span.accent {{
    background: linear-gradient(120deg, #35a0ff, #9965f4, #ec4899);
    -webkit-background-clip: text;
    color: transparent;
  }}
  .callouts {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 18px;
  }}
  .callout {{
    border-radius: 20px;
    border: 1px solid rgba(255, 255, 255, 0.08);
    background: rgba(255, 255, 255, 0.06);
    padding: 18px;
    display: flex;
    gap: 16px;
    align-items: flex-start;
    backdrop-filter: blur(18px);
  }}
  .callout .icon {{
    width: 44px;
    height: 44px;
    border-radius: 16px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: linear-gradient(140deg, rgba(53, 160, 255, 0.2), rgba(153, 101, 244, 0.2));
  }}
  .callout svg {{ width: 26px; height: 26px; stroke: #60a5fa; }}
  .voice-toggle {{
    border-radius: 9999px;
    background: linear-gradient(120deg, #35a0ff, #9965f4);
    padding: 12px 28px;
    font-weight: 600;
    border: none;
    color: white;
    cursor: pointer;
    box-shadow: 0 20px 35px rgba(77, 126, 255, 0.3);
  }}
  .voice-toggle.disabled {{
    opacity: 0.45;
    cursor: not-allowed;
    box-shadow: none;
  }}
  .voice-note {{ color: #94a3b8; font-size: 14px; margin-left: 12px; }}
  .feedback-card {{
    border-radius: 28px;
    border: 1px solid rgba(255, 255, 255, 0.08);
    background: rgba(255, 255, 255, 0.08);
    padding: 28px;
    position: relative;
    overflow: hidden;
    backdrop-filter: blur(22px);
    box-shadow: 0 35px 50px -22px rgba(14, 27, 53, 0.58);
  }}
  .feedback-card::after {{
    content: "";
    position: absolute;
    inset: 0;
    border-radius: inherit;
    pointer-events: none;
    background: linear-gradient(120deg, rgba(255, 255, 255, 0.18), transparent 60%);
    opacity: 0.35;
  }}
  .feedback-empty {{
    color: #94a3b8;
    font-size: 15px;
    line-height: 1.6;
  }}
  .camera-panel {{
    border-radius: 32px;
    border: 1px solid rgba(255, 255, 255, 0.08);
    background: rgba(255, 255, 255, 0.06);
    padding: 24px;
    position: relative;
    backdrop-filter: blur(22px);
    box-shadow: 0 25px 45px rgba(12, 23, 45, 0.55);
  }}
  video {{
    width: 100%;
    height: 320px;
    border-radius: 26px;
    object-fit: cover;
    background: #0f172a;
    border: 1px solid rgba(255, 255, 255, 0.08);
  }}
  .analyze-button {{
    flex: 1;
    border-radius: 9999px;
    background: linear-gradient(120deg, #35a0ff, #9965f4);
    padding: 14px 28px;
    font-weight: 600;
    border: none;
    color: white;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    box-shadow: 0 20px 35px rgba(77, 126, 255, 0.28);
  }}
  .analyze-button.disabled {{
    opacity: 0.5;
    cursor: not-allowed;
    box-shadow: none;
  }}
  .voice-pulse {{
    width: 280px;
    border-radius: 26px;
    border: 1px solid rgba(255, 255, 255, 0.1);
    padding: 18px 16px 22px;
    background: rgba(15, 23, 42, 0.48);
    position: relative;
    text-align: center;
  }}
  .pulse-ring {{
    width: 120px;
    height: 120px;
    border-radius: 9999px;
    margin: 0 auto 18px;
    position: relative;
  }}
  .pulse-glow {{
    position: absolute;
    inset: 0;
    border-radius: inherit;
    background: linear-gradient(135deg, rgba(53, 160, 255, 0.75), rgba(153, 101, 244, 0.75));
    opacity: 0.35;
    filter: blur(30px);
    transition: opacity 0.3s ease, transform 0.3s ease;
  }}
  .pulse-inner {{
    position: absolute;
    inset: 16px;
    border: 1px solid rgba(255, 255, 255, 0.2);
    border-radius: inherit;
    background: rgba(15, 23, 42, 0.82);
    display: flex;
    align-items: center;
    justify-content: center;
  }}
  .pulse-glow.active {{ animation: glow 2.6s ease-in-out infinite; opacity: 0.65; }}
  .pulse-inner.processing::after {{
    content: "";
    width: 34px;
    height: 34px;
    border-radius: 9999px;
    border: 4px solid rgba(153, 101, 244, 0.5);
    border-top-color: transparent;
    animation: spin 1s linear infinite;
  }}
  .pulse-icon {{
    width: 40px;
    height: 40px;
    stroke: currentColor;
  }}
  .voice-state {{
    font-size: 13px;
    letter-spacing: 0.32em;
    color: #cbd5f5;
  }}
  @keyframes glow {{
    0%, 100% {{ transform: scale(1); opacity: 0.55; }}
    50% {{ transform: scale(1.16); opacity: 0.9; }}
  }}
  @keyframes spin {{
    to {{ transform: rotate(360deg); }}
  }}
  footer {{
    margin-top: 40px;
    color: #64748b;
    font-size: 13px;
    line-height: 1.6;
  }}
  pre {{
    white-space: pre-wrap;
    background: rgba(15, 23, 42, 0.7);
    padding: 18px;
    border-radius: 16px;
    border: 1px solid rgba(255, 255, 255, 0.06);
    overflow-x: auto;
  }}
</style>
</head>
<body>
  <div class=\"page\">
    <header>
      <div class=\"brand-mark\">
        <div class=\"brand-icon\">🧘</div>
        <div>
          <div style=\"font-size:12px; letter-spacing:0.32em; text-transform:uppercase; color:#94a3b8;\">AsanaSense</div>
          <div style=\"font-size:18px; font-weight:600; color:#fff; margin-top:4px;\">AI-Powered Yoga Coach</div>
        </div>
      </div>
      <div class=\"status-pill\">
        <span class=\"status-dot\" id=\"status-dot\"></span>
        <span id=\"status-label\">Ready</span>
      </div>
    </header>

    <main>
      <section class=\"hero\">
        <div>
          <div style=\"font-size:13px; letter-spacing:0.52em; text-transform:uppercase; color:#64748b;\">Perfect Your Practice</div>
          <h1>Perfect <span class=\"accent\">Your Pose</span></h1>
          <p style=\"max-width:460px; font-size:18px; line-height:1.7; color:#cbd5f5;\">
            AI-powered yoga coaching that listens, watches, and guides you to perfect form with real-time feedback.
          </p>
        </div>
        <div class=\"callouts\">
          <div class=\"callout\">
            <div class=\"icon\">
              <svg viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"1.5\" stroke-linecap=\"round\" stroke-linejoin=\"round\">
                <path d=\"M9 3v4m6-4v4M5 21h14l-1-10H6l-1 10zm0 0H3v2h18v-2h-2\" />
              </svg>
            </div>
            <div>
              <div style=\"font-weight:600; color:#fff;\">Voice Activated</div>
              <div style=\"color:#cbd5f5; font-size:14px;\">Say "analyze" to start</div>
            </div>
          </div>
          <div class=\"callout\">
            <div class=\"icon\">
              <svg viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"1.5\" stroke-linecap=\"round\" stroke-linejoin=\"round\">
                <path d=\"M4 4h16v12H5.17L4 17.17V4z\" />
                <path d=\"M8 9h8v2H8z\" />
              </svg>
            </div>
            <div>
              <div style=\"font-weight:600; color:#fff;\">Real-time Analysis</div>
              <div style=\"color:#cbd5f5; font-size:14px;\">Instant pose feedback</div>
            </div>
          </div>
        </div>
        <div>
          <button id=\"voice-toggle\" class=\"voice-toggle\">Enable Voice</button>
          <span class=\"voice-note\" id=\"voice-note\">Say "analyze" when enabled.</span>
        </div>

        <div class=\"feedback-card\" id=\"feedback-card\">
          <div class=\"feedback-empty\" id=\"feedback-empty\">
            The latest feedback will appear here once a pose has been analyzed.
          </div>
          <div id=\"feedback-content\" style=\"display:none; position:relative; z-index:1;\">
            <div style=\"display:flex; justify-content:space-between; align-items:center; gap:16px;\">
              <div>
                <div style=\"font-size:12px; letter-spacing:0.32em; text-transform:uppercase; color:#60a5fa;\">Latest Insight</div>
                <div id=\"asana-name\" style=\"font-size:26px; font-weight:600; color:#fff; margin-top:6px;\"></div>
              </div>
              <span style=\"display:inline-flex; align-items:center; gap:8px; border-radius:9999px; padding:6px 14px; font-size:12px; border:1px solid rgba(96, 165, 250, 0.35); color:#60a5fa; background:rgba(96, 165, 250, 0.1);\">
                <span style=\"width:6px; height:6px; border-radius:999px; background:#60a5fa; animation:pulse 1.8s ease-in-out infinite;\"></span>
                Live
              </span>
            </div>
            <div style=\"margin-top:24px; display:grid; gap:18px; font-size:15px; line-height:1.6; color:#dbeafe;\">
              <div>
                <div style=\"font-size:12px; letter-spacing:0.24em; text-transform:uppercase; color:#94a3b8;\">Alignment Highlights</div>
                <ul id=\"alignment-list\" style=\"margin-top:10px; display:grid; gap:8px; padding-left:0; list-style:none;\"></ul>
              </div>
              <div>
                <div style=\"font-size:12px; letter-spacing:0.24em; text-transform:uppercase; color:#94a3b8;\">Improvement Tips</div>
                <ul id=\"improvement-list\" style=\"margin-top:10px; display:grid; gap:8px; padding-left:0; list-style:none;\"></ul>
              </div>
              <div>
                <div style=\"font-size:12px; letter-spacing:0.24em; text-transform:uppercase; color:#94a3b8;\">Risks & Cautions</div>
                <ul id=\"risk-list\" style=\"margin-top:10px; display:grid; gap:8px; padding-left:0; list-style:none;\"></ul>
              </div>
            </div>
            <div style=\"margin-top:24px; border-radius:22px; border:1px solid rgba(255,255,255,0.08); padding:18px; background:rgba(15,23,42,0.6); color:#dbeafe;\">
              <div style=\"font-size:12px; letter-spacing:0.24em; text-transform:uppercase; color:#94a3b8;\">Coaching Copy</div>
              <p id=\"coaching-copy\" style=\"margin-top:10px; line-height:1.7;\"></p>
            </div>
          </div>
        </div>
      </section>

      <section>
        <div class=\"camera-panel\">
          <div style=\"display:flex; justify-content:space-between; color:#cbd5f5; font-size:15px;\">
            <span>Live Camera</span>
            <span style=\"font-size:13px; color:#94a3b8;\">Framed coaching view</span>
          </div>
          <div style=\"margin-top:16px; position:relative; border-radius:28px; overflow:hidden;\">
            <video id=\"camera-stream\" autoplay muted playsinline></video>
            <canvas id=\"capture-canvas\" style=\"display:none;\"></canvas>
          </div>
          <div style=\"margin-top:18px; border-radius:22px; border:1px solid rgba(255,255,255,0.08); padding:16px; background:rgba(15,23,42,0.65); font-size:14px; color:#cbd5f5;\">
            <div style=\"display:flex; justify-content:space-between; align-items:center;\">
              <div style=\"display:flex; align-items:center; gap:10px;\">
                <span id=\"listening-dot\" style=\"width:7px; height:7px; border-radius:999px; background:#38bdf8; animation:pulse 1.8s ease-in-out infinite;\"></span>
                <span>Say "analyze" or press Analyze to capture</span>
              </div>
              <span style=\"font-size:12px; color:#94a3b8;\">Ready</span>
            </div>
            <div id=\"status-text\" style=\"margin-top:10px; color:#94a3b8; font-size:13px;\"></div>
          </div>
          <div style=\"margin-top:22px; display:flex; flex-wrap:wrap; gap:18px; justify-content:flex-start;\">
            <button id=\"analyze-button\" class=\"analyze-button\">
              <svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"1.5\" stroke-linecap=\"round\" stroke-linejoin=\"round\" style=\"width:22px; height:22px;\">
                <circle cx=\"12\" cy=\"12\" r=\"3.8\"></circle>
                <path d=\"M4 7h2l1.6-2h8.8L18 7h2v12H4z\"></path>
              </svg>
              Analyze Pose
            </button>
            <div class=\"voice-pulse\">
              <div class=\"pulse-ring\">
                <div class=\"pulse-glow\" id=\"pulse-glow\"></div>
                <div class=\"pulse-inner\" id=\"pulse-inner\">
                  <svg class=\"pulse-icon\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"1.5\" stroke-linecap=\"round\" stroke-linejoin=\"round\">
                    <path d=\"M12 15.5c1.656 0 3-1.567 3-3.5V6.5a3 3 0 0 0-6 0V12c0 1.933 1.344 3.5 3 3.5z\" />
                    <path d=\"M6 10v2c0 3.18 2.243 5.803 5.2 5.97V21h1.6v-3.03C15.757 17.803 18 15.18 18 12v-2\" />
                  </svg>
                </div>
              </div>
              <div class=\"voice-state\" id=\"voice-state\">Voice idle</div>
            </div>
          </div>
        </div>
      </section>
    </main>

    <footer>
      <div id=\"raw-text-container\" style=\"margin-top:32px;\"></div>
      <p style=\"margin-top:18px;\">Camera and microphone permissions stay local to your browser. Keep this tab active while practicing.</p>
    </footer>
  </div>

  <script>
    const props = __PROPS_JSON__;
    const Streamlit = window.parent.Streamlit;
    const computedVoiceSupport = Boolean(window.SpeechRecognition || window.webkitSpeechRecognition);

    function setStatus(state) {{
      const dot = document.getElementById('status-dot');
      const label = document.getElementById('status-label');
      dot.classList.remove('listening', 'processing', 'error');
      if (state === 'listening') {{
        dot.classList.add('listening');
        label.textContent = 'Listening';
      }} else if (state === 'processing') {{
        dot.classList.add('processing');
        label.textContent = 'Processing';
      }} else if (state === 'error') {{
        dot.classList.add('error');
        label.textContent = 'Check Setup';
      }} else {{
        label.textContent = 'Ready';
      }}
    }

    function renderFeedback() {{
      const feedback = props.feedback;
      const hasFeedback = Boolean(feedback && feedback.asanaName);
      const emptyCard = document.getElementById('feedback-empty');
      const contentCard = document.getElementById('feedback-content');
      if (!hasFeedback) {{
        emptyCard.style.display = 'block';
        contentCard.style.display = 'none';
        return;
      }}
      emptyCard.style.display = 'none';
      contentCard.style.display = 'block';

      document.getElementById('asana-name').textContent = feedback.asanaName;
      const alignmentList = document.getElementById('alignment-list');
      alignmentList.innerHTML = '';
      (feedback.alignmentHighlights || []).forEach((item) => {{
        const li = document.createElement('li');
        li.innerHTML = `<span style="display:inline-block;width:8px;height:8px;border-radius:999px;background:#60a5fa;margin-right:10px;vertical-align:middle;"></span><span>${item}</span>`;
        alignmentList.appendChild(li);
      }});
      const improvementList = document.getElementById('improvement-list');
      improvementList.innerHTML = '';
      (feedback.improvementTips || []).forEach((item) => {{
        const li = document.createElement('li');
        li.innerHTML = `<span style="display:inline-block;width:8px;height:8px;border-radius:999px;background:#c084fc;margin-right:10px;vertical-align:middle;"></span><span>${item}</span>`;
        improvementList.appendChild(li);
      }});
      const riskList = document.getElementById('risk-list');
      riskList.innerHTML = '';
      (feedback.riskWarnings || []).forEach((item) => {{
        const li = document.createElement('li');
        li.innerHTML = `<span style="display:inline-block;width:8px;height:8px;border-radius:999px;background:#f87171;margin-right:10px;vertical-align:middle;"></span><span>${item}</span>`;
        riskList.appendChild(li);
      }});
      document.getElementById('coaching-copy').textContent = feedback.coachingCopy || '';
    }

    function renderRawText() {{
      const container = document.getElementById('raw-text-container');
      container.innerHTML = '';
      if (!props.rawText) {{
        return;
      }}
      const details = document.createElement('details');
      const summary = document.createElement('summary');
      summary.textContent = 'View raw Gemini response';
      summary.style.cursor = 'pointer';
      summary.style.fontSize = '12px';
      summary.style.textTransform = 'uppercase';
      summary.style.letterSpacing = '0.28em';
      summary.style.color = '#94a3b8';
      details.appendChild(summary);
      const pre = document.createElement('pre');
      pre.textContent = props.rawText;
      details.appendChild(pre);
      container.appendChild(details);
    }

    function updateStatusText() {{
      const text = document.getElementById('status-text');
      text.textContent = props.statusText || '';
    }

    function updateVoiceUI() {{
      const toggle = document.getElementById('voice-toggle');
      const note = document.getElementById('voice-note');
      const stateLabel = document.getElementById('voice-state');
      const glow = document.getElementById('pulse-glow');
      const inner = document.getElementById('pulse-inner');
      if (props.voiceSupported && computedVoiceSupport) {{
        toggle.classList.remove('disabled');
        toggle.disabled = false;
        note.textContent = props.voiceEnabled ? 'Say "analyze" to capture or press Analyze.' : 'Click Enable Voice to use wake words.';
      }} else {{
        toggle.classList.add('disabled');
        toggle.disabled = true;
        note.textContent = 'Voice control not supported in this browser.';
      }}
      toggle.textContent = props.voiceEnabled ? 'Disable Voice' : 'Enable Voice';
      let stateCopy = 'Voice idle';
      if (props.systemState === 'listening') {{
        stateCopy = 'Listening…';
        glow.classList.add('active');
        inner.classList.remove('processing');
      }} else if (props.systemState === 'processing') {{
        stateCopy = 'Analyzing…';
        glow.classList.remove('active');
        inner.classList.add('processing');
      }} else if (props.systemState === 'ready') {{
        stateCopy = 'Ready';
        glow.classList.remove('active');
        inner.classList.remove('processing');
      }} else if (props.systemState === 'error') {{
        stateCopy = 'Voice paused';
        glow.classList.remove('active');
        inner.classList.remove('processing');
      }} else {{
        glow.classList.remove('active');
        inner.classList.remove('processing');
      }}
      stateLabel.textContent = stateCopy;
    }

    function updateAnalyzeButton() {{
      const button = document.getElementById('analyze-button');
      if (props.systemState === 'processing') {{
        button.classList.add('disabled');
        button.disabled = true;
      }} else {{
        button.classList.remove('disabled');
        button.disabled = false;
      }}
    }

    let recognition = null;
    let mediaStream = null;
    let lastCaptureId = props.lastCaptureId || null;

    function sendEvent(event) {{
      if (!Streamlit || !Streamlit.setComponentValue) {{
        return;
      }}
      Streamlit.setComponentValue(JSON.stringify(event));
    }

    async function initCamera() {{
      try {{
        mediaStream = await navigator.mediaDevices.getUserMedia({{ video: {{ facingMode: 'user', width: {{ ideal: 1280 }}, height: {{ ideal: 720 }} }}, audio: false }});
        const video = document.getElementById('camera-stream');
        if (video) {{
          video.srcObject = mediaStream;
        }}
      }} catch (error) {{
        sendEvent({{ type: 'camera_error', message: String(error) }});
      }}
    }

    function ensureRecognition() {{
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SpeechRecognition) {{
        return null;
      }}
      if (recognition) {{
        return recognition;
      }}
      const instance = new SpeechRecognition();
      instance.lang = 'en-US';
      instance.continuous = false;
      instance.interimResults = false;
      instance.maxAlternatives = 1;
      instance.onresult = (event) => {{
        const transcript = event.results[0][0].transcript.toLowerCase();
        if (/\banal(y|i)ze\b|\bclick\b/.test(transcript)) {{
          triggerCapture('voice');
        }}
        sendEvent({{ type: 'voice_transcript', transcript }});
      }};
      instance.onerror = (event) => {{
        sendEvent({{ type: 'voice_error', error: event.error || 'unknown' }});
      }};
      instance.onend = () => {{
        if (props.voiceEnabled && props.systemState !== 'processing') {{
          try {{
            instance.start();
          }} catch (err) {{
            console.warn('Restart recognition failed', err);
          }}
        }}
      }};
      recognition = instance;
      return recognition;
    }

    function updateVoiceEngine() {{
      if (!props.voiceEnabled || !computedVoiceSupport) {{
        if (recognition) {{
          recognition.onend = null;
          try {{ recognition.stop(); }} catch (err) {{}}
        }}
        return;
      }}
      const engine = ensureRecognition();
      if (!engine) {{
        return;
      }}
      try {{
        engine.start();
      }} catch (err) {{
        console.warn('Recognition start failed', err);
      }}
    }

    function speakCopy() {{
      if (!props.shouldSpeak || !props.feedback || !props.feedback.coachingCopy) {{
        return;
      }}
      const synth = window.speechSynthesis;
      if (!synth) {{
        return;
      }}
      synth.cancel();
      const utterance = new SpeechSynthesisUtterance(props.feedback.coachingCopy);
      const preferred = synth.getVoices().find((voice) => voice.lang && voice.lang.toLowerCase().startsWith('en'));
      if (preferred) {{
        utterance.voice = preferred;
      }}
      utterance.rate = 1.02;
      utterance.pitch = 1.0;
      synth.speak(utterance);
    }

    function triggerCapture(source) {{
      if (props.systemState === 'processing') {{
        return;
      }}
      const video = document.getElementById('camera-stream');
      const canvas = document.getElementById('capture-canvas');
      if (!video || !canvas || !video.videoWidth) {{
        sendEvent({{ type: 'capture_error', message: 'Video not ready' }});
        return;
      }}
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      const ctx = canvas.getContext('2d');
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      const dataUrl = canvas.toDataURL('image/jpeg', 0.92);
      const eventId = `${{Date.now()}}-${{Math.random().toString(16).slice(2)}}`;
      lastCaptureId = eventId;
      sendEvent({{ type: 'capture', imageBase64: dataUrl, eventId, source }});
    }

    document.getElementById('analyze-button').addEventListener('click', () => triggerCapture('button'));

    document.getElementById('voice-toggle').addEventListener('click', () => {{
      if (!props.voiceSupported) {{
        return;
      }}
      sendEvent({{ type: 'toggle_voice', enable: !props.voiceEnabled, eventId: `${Date.now()}-${Math.random().toString(16).slice(2)}` }});
    }});

    window.addEventListener('load', () => {{
      initCamera();
      updateVoiceEngine();
      if (props.shouldSpeak) {{
        speakCopy();
      }}
    }});

    setStatus(props.systemState);
    renderFeedback();
    renderRawText();
    updateStatusText();
    updateVoiceUI();
    if (!computedVoiceSupport) {{
      const note = document.getElementById('voice-note');
      const toggle = document.getElementById('voice-toggle');
      note.textContent = "Voice control not supported in this browser.";
      toggle.classList.add('disabled');
      toggle.disabled = true;
      if (props.voiceSupported) {{
        setTimeout(() => sendEvent({{ type: 'voice_unsupported' }}), 100);
      }}
    }}
    updateAnalyzeButton();

    if (props.voiceEnabled) {{
      setTimeout(updateVoiceEngine, 400);
    }}

    if (props.shouldSpeak) {{
      setTimeout(speakCopy, 600);
    }}

    if (Streamlit && Streamlit.setComponentReady) {{
      Streamlit.setComponentReady();
      Streamlit.setFrameHeight(document.body.scrollHeight);
    }}
  </script>
</body>
</html>
"""
    template = template.replace("{{", "{").replace("}}", "}")
    return template.replace("__PROPS_JSON__", props_json)


def init_state() -> None:
    st.session_state.setdefault("system_state", "ready")
    st.session_state.setdefault("feedback", None)
    st.session_state.setdefault("raw_text", "")
    st.session_state.setdefault("voice_enabled", False)
    st.session_state.setdefault("voice_supported", True)
    st.session_state.setdefault("last_event_id", None)
    st.session_state.setdefault("last_spoken_copy", "")
    st.session_state.setdefault("status_text", "Say \"analyze\" or press the Analyze button to capture.")


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

    if (
        st.session_state.get("feedback")
        and st.session_state["feedback"].get("coachingCopy")
        and st.session_state["feedback"]["coachingCopy"] != st.session_state.get("last_spoken_copy")
    ):
        props["shouldSpeak"] = True
        st.session_state["last_spoken_copy"] = st.session_state["feedback"]["coachingCopy"]

    component_html = build_component_html(props)

    import streamlit.components.v1 as components

    event_json = components.html(component_html, height=900, key="asana-sense-holo")

    if not event_json:
        return

    try:
        event = json.loads(event_json)
    except json.JSONDecodeError:
        st.warning("Received malformed event from UI component.")
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
        st.session_state["system_state"] = "listening" if st.session_state["voice_enabled"] else "ready"
        st.experimental_rerun()

    if event_type == "camera_error":
        st.session_state["system_state"] = "error"
        st.session_state["status_text"] = "Camera access failed. Please allow camera permissions and reload."
        st.experimental_rerun()

    if event_type == "voice_unsupported":
        st.session_state["voice_supported"] = False
        st.session_state["voice_enabled"] = False
        st.session_state["system_state"] = "ready"
        st.experimental_rerun()

    if event_type == "voice_error":
        st.session_state["system_state"] = "error"
        st.session_state["voice_enabled"] = False
        st.session_state["status_text"] = "Voice recognition failed. You can still click Analyze."
        st.experimental_rerun()

    if event_type == "capture_error":
        st.warning("Unable to capture video frame. Try again.")
        st.session_state["system_state"] = "error"
        st.experimental_rerun()

    if event_type == "voice_transcript":
        transcript = event.get("transcript", "")
        if transcript:
            st.toast(f"Heard: {transcript}")
        return

    if event_type == "capture":
        image_base64 = event.get("imageBase64")
        if not image_base64:
            st.warning("No image data received from capture.")
            return
        st.session_state["system_state"] = "processing"
        st.session_state["status_text"] = "Analyzing pose..."
        with st.spinner("Analyzing pose with Gemini..."):
            try:
                feedback, raw_text = analyze_pose(image_base64, None)
            except RuntimeError as exc:  # covers Gemini + parse errors
                st.error(str(exc))
                st.session_state["system_state"] = "error"
                st.experimental_rerun()
                return
            except ValueError as exc:
                st.error(str(exc))
                st.session_state["system_state"] = "error"
                st.experimental_rerun()
                return
        st.session_state["feedback"] = feedback
        st.session_state["raw_text"] = raw_text
        st.session_state["system_state"] = "listening" if st.session_state["voice_enabled"] else "ready"
        st.session_state["status_text"] = "Say \"analyze\" or press Analyze to capture."
        st.session_state["last_processed_capture_id"] = event.get("eventId")
        st.experimental_rerun()


if __name__ == "__main__":
    main()
