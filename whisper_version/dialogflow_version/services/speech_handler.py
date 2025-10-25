import os
import tempfile
from groq import Groq
from gtts import gTTS
from dotenv import load_dotenv

load_dotenv()

class SpeechHandler:
    def __init__(self):
        self.groq_client = Groq(api_key=os.getenv('GROQ_API_KEY'))
        self.tts_voice = "en-US-AriaNeural"
    
    def transcribe_audio(self, audio_file):
        """Transcribe audio using Groq Whisper API."""
        try:
            transcription = self.groq_client.audio.transcriptions.create(
                file=(audio_file.filename, audio_file.read(), audio_file.content_type),
                model="whisper-large-v3",
                language="en"
            )
            return transcription.text
        except Exception as e:
            raise Exception(f"Transcription failed: {str(e)}")
    
    def synthesize_speech(self, text):
        """Generate speech from text using gTTS."""
        try:
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
            temp_path = temp_file.name
            temp_file.close()
            
            tts = gTTS(text=text, lang='en', slow=False)
            tts.save(temp_path)
            return temp_path
        except Exception as e:
            raise Exception(f"Speech synthesis failed: {str(e)}")
