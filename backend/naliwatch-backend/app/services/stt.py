"""Speech to text. Claude does not transcribe audio, so transcribe first and classify the text after."""
import io

from ..config import settings


def transcribe(audio: bytes, filename: str = "voice.ogg") -> str:
    if settings.stt_provider == "whisper":
        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key)
        f = io.BytesIO(audio)
        f.name = filename
        return client.audio.transcriptions.create(model="whisper-1", file=f).text
    if settings.stt_provider == "bhashini":
        # Needs ULCA credentials and a pipeline id from Bhashini; wire it here once the team has an account.
        raise NotImplementedError("Bhashini adapter not implemented yet")
    raise RuntimeError("speech to text is not configured (STT_PROVIDER=none)")
