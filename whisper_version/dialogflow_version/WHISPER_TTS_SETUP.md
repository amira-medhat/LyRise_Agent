# Whisper + Edge-TTS Integration Guide

## Overview
This version uses **Groq's Whisper API** for speech-to-text and **edge-tts** for text-to-speech, replacing the browser's Web Speech API.

## Architecture

### Backend (Python)
- **Speech Handler** (`services/speech_handler.py`): Manages all speech operations
  - `transcribe_audio()`: Converts audio to text using Groq Whisper
  - `synthesize_speech()`: Converts text to audio using edge-tts

### API Endpoints
1. **POST /transcribe**: Accepts audio file, returns transcribed text
2. **POST /synthesize**: Accepts text, returns audio file (MP3)
3. **POST /chat**: Existing chat endpoint (unchanged)

## Setup Instructions

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Add your Groq API key to `.env`:
```
GROQ_API_KEY="your_groq_api_key_here"
```

Get your API key from: https://console.groq.com/

### 3. Frontend Integration (JavaScript)
The frontend needs to:
1. Record audio using MediaRecorder API
2. Send audio blob to `/transcribe` endpoint
3. Display transcribed text and send to `/chat`
4. Receive response and send to `/synthesize`
5. Play the returned audio

## Key Features

### Whisper (via Groq)
- Model: `whisper-large-v3-turbo`
- Language: English
- Fast and accurate transcription
- Supports various audio formats

### Edge-TTS
- Voice: `en-US-AriaNeural` (female, natural)
- Output: MP3 format
- Free and unlimited
- No API key required

## Advantages Over Web Speech API
1. **Server-side processing**: More reliable and consistent
2. **Better accuracy**: Whisper is state-of-the-art
3. **Cross-browser**: Works on all browsers
4. **Offline capability**: Can be adapted for offline use
5. **Customizable voices**: Many edge-tts voices available

## File Structure
```
whisper_version/dialogflow_version/
├── app.py                          # Main Flask app with endpoints
├── services/
│   ├── speech_handler.py          # NEW: Speech processing logic
│   ├── dialogflow_handler.py      # Dialogflow integration
│   └── ...
├── static/js/
│   └── main.js                     # Frontend (needs audio recording)
├── requirements.txt                # Updated with groq + edge-tts
└── .env                            # Add GROQ_API_KEY here
```

## Frontend Implementation (Completed)
The `static/js/main.js` now uses:
1. **MediaRecorder API** for audio recording
2. **Fetch API** to send audio to `/transcribe`
3. **Audio element** to play responses from `/synthesize`

### Recording Flow:
1. User clicks microphone button
2. Browser requests microphone permission
3. Records audio until user clicks stop
4. Sends audio blob to `/transcribe` endpoint
5. Displays transcribed text
6. Sends text to `/chat` endpoint
7. Receives response and sends to `/synthesize`
8. Plays audio response

## Available Edge-TTS Voices
Change voice in `speech_handler.py`:
- `en-US-AriaNeural` (Female, friendly)
- `en-US-GuyNeural` (Male, professional)
- `en-US-JennyNeural` (Female, assistant)
- `en-GB-SoniaNeural` (British Female)
- And many more...

## Error Handling
Both transcription and synthesis include proper error handling:
- Missing audio file
- API failures
- Invalid text input
- Temporary file management
