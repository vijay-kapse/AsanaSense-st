# AsanaSense

A single Streamlit app that mirrors the premium “Perfect Your Pose” hero, streams the webcam, captures snapshots (manually or by voice wake word), and sends them to Google Gemini for coaching feedback.

## Features
- Glassmorphism hero with live camera frame, animated VoicePulse control, and Gemini-powered Feedback card
- Voice controls via the browser Web Speech API (say “analyze” to trigger a capture)
- Speech synthesis reads Gemini’s coaching copy aloud while the card displays the same guidance
- Inline JSON parsing + error handling so malformed Gemini responses surface clearly

## Getting started
1. Install dependencies
   ```bash
   pip install -r requirements.txt
   ```
2. Set your Gemini API key (either in Streamlit secrets or the environment)
   ```bash
   export GOOGLE_API_KEY="your_api_key"
   ```
   On Streamlit Cloud, add `GOOGLE_API_KEY` under **Secrets**.
3. Run the app
   ```bash
   streamlit run app.py
   ```

Grant camera and microphone access in the browser tab. The voice control button enables the wake word listener; the UI also works with the **Analyze Pose** button if voice is disabled or unsupported.

## Deployment notes
- The app is Streamlit-native—no separate backend to host. Deploy by pushing to a repo and pointing Streamlit Cloud at `app.py`.
- Gemini responses must stay in the expected JSON schema. If parsing fails, an error surfaces in-app so you can adjust the prompt.
- Speech recognition relies on Chrome/Edge (Web Speech API). Unsupported browsers disable the voice toggle automatically.
- Gemini usage incurs API costs; consider rate limiting or caching on busy deployments.
