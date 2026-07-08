"""
Speech-to-Text and Text-to-Speech handling using OpenAI Whisper and TTS.
"""
import os
from typing import Optional
from openai import OpenAI
from .utils.logger import logger

# Lazy initialization - client will be created when needed
_client = None

def get_openai_client():
    """Get or create OpenAI client with API key from environment."""
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set. Make sure .env file is loaded.")
        _client = OpenAI(api_key=api_key)
    return _client


async def transcribe_audio(audio_url: str) -> str:
    """
    Transcribe audio from URL using OpenAI Whisper.
    
    Args:
        audio_url: URL to the audio file
        
    Returns:
        Transcribed text
    """
    try:
        logger.info(f"Transcribing audio from URL: {audio_url}")
        
        # Download audio from Twilio URL
        import httpx
        async with httpx.AsyncClient() as http_client:
            response = await http_client.get(audio_url)
            response.raise_for_status()
            audio_data = response.content
        
        # Save temporarily for Whisper
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_file:
            tmp_file.write(audio_data)
            tmp_path = tmp_file.name
        
        try:
            # Transcribe using Whisper
            client = get_openai_client()
            with open(tmp_path, "rb") as audio_file:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="en"
                )
            
            text = transcript.text.strip()
            logger.info(f"Transcription successful: {text[:100]}...")
            return text
            
        finally:
            # Clean up temp file
            os.unlink(tmp_path)
            
    except Exception as e:
        logger.error(f"Error transcribing audio: {str(e)}")
        raise


def generate_speech_response(text: str, voice: str = "alloy") -> str:
    """
    Generate speech from text using OpenAI TTS.
    Returns the TwiML format for Twilio to play the audio.
    
    Args:
        text: Text to convert to speech
        voice: Voice to use (alloy, echo, fable, onyx, nova, shimmer)
        
    Returns:
        TwiML XML string for Twilio
    """
    try:
        logger.info(f"Generating speech for text: {text[:100]}...")
        
        # Generate audio using OpenAI TTS
        client = get_openai_client()
        response = client.audio.speech.create(
            model="tts-1",
            voice=voice,
            input=text
        )
        
        # Save audio to temporary location or serve via endpoint
        # For now, we'll return TwiML that points to an endpoint serving this audio
        # In production, you'd upload this to a CDN or serve via FastAPI endpoint
        
        audio_url = f"/audio/{hash(text)}.mp3"  # Placeholder - implement audio serving endpoint
        
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Joanna">{text}</Say>
</Response>"""
        
        # Alternative: Use Twilio's <Say> with SSML or serve audio file
        # For better quality, serve the generated MP3 via an endpoint
        return twiml
        
    except Exception as e:
        logger.error(f"Error generating speech: {str(e)}")
        # Fallback to Twilio's built-in TTS
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Joanna">{text}</Say>
</Response>"""


