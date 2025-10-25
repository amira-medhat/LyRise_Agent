# Testing Guide - Whisper + Edge-TTS Version

## Quick Start

### 1. Install Dependencies
```bash
cd whisper_version/dialogflow_version
pip install -r requirements.txt
```

### 2. Set Up Environment
Edit `.env` and add your Groq API key:
```
GROQ_API_KEY="gsk_your_actual_key_here"
```

Get your free API key from: https://console.groq.com/

### 3. Run the Application
```bash
python app.py
```

The app will start on `http://localhost:5000`

## Testing Features

### Text Input (Type)
1. Type a message in the text box
2. Press Enter or click Send button
3. Response will be displayed and spoken

### Voice Input (Speak)
1. Click the microphone button
2. Allow microphone access when prompted
3. Speak your message
4. Click Stop when done
5. Audio is transcribed and processed
6. Response is displayed and spoken

### Test Queries
Try these sample queries:

**List Schedules:**
- "Show me Dr. Smith's schedule for tomorrow"
- "What slots are available on Monday?"

**Book Appointment:**
- "Book an appointment with Dr. Johnson"
- "I want to see Dr. Brown tomorrow at 2 PM"

**Cancel Appointment:**
- "Cancel my appointment with Dr. Smith"
- "I need to cancel tomorrow at 3 PM"

## Troubleshooting

### Microphone Not Working
- Check browser permissions (Chrome/Edge recommended)
- Ensure HTTPS or localhost (required for MediaRecorder)
- Check if another app is using the microphone

### Transcription Errors
- Verify GROQ_API_KEY is set correctly in `.env`
- Check internet connection
- Ensure audio is clear and not too short

### TTS Not Playing
- Check browser audio settings
- Verify `/synthesize` endpoint is working
- Check browser console for errors

### API Rate Limits
Groq free tier limits:
- 30 requests per minute
- 14,400 requests per day

## API Endpoints

### POST /transcribe
**Input:** Audio file (multipart/form-data)
**Output:** `{"text": "transcribed text"}`

### POST /synthesize
**Input:** `{"text": "text to speak"}`
**Output:** MP3 audio file

### POST /chat
**Input:** `{"message": "user message", "session_id": "uuid"}`
**Output:** `{"reply": "agent response", "session_id": "uuid"}`

## Browser Compatibility

✅ **Supported:**
- Chrome 49+
- Edge 79+
- Firefox 25+
- Safari 14.1+

❌ **Not Supported:**
- Internet Explorer
- Older mobile browsers

## Performance Notes

- **Transcription:** ~1-3 seconds (depends on audio length)
- **TTS Generation:** ~0.5-2 seconds
- **Total Response Time:** ~2-5 seconds

## Security Notes

- Microphone access requires user permission
- Audio is sent to Groq servers for transcription
- TTS is generated server-side (no external API)
- Session IDs stored in localStorage
