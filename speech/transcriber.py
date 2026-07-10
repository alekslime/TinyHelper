"""Local speech-to-text via Faster-Whisper.

Knows nothing about microphones, silence detection, or wake words — takes
raw audio, returns text. `speech/listening_session.py` handles buffering
the right audio to hand this; `voice/service.py`/`main.py` decide when to
call it.

Faster-Whisper downloads model weights from Hugging Face Hub on first use
per model size, then caches them locally (in the default Hugging Face
cache directory) for every run after that — this is a one-time setup
download, not runtime cloud inference, same category as the wake word
model download in `voice/wake_word.py`. See `docs/DECISIONS.md`.
"""

from __future__ import annotations

import logging

import numpy as np
from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)

DEFAULT_MODEL_SIZE = "small"
DEFAULT_DEVICE = "auto"
DEFAULT_COMPUTE_TYPE = "default"


def int16_to_float32(audio: np.ndarray) -> np.ndarray:
    """Convert int16 PCM audio (as produced by MicrophoneStream) to the
    normalized float32 format Faster-Whisper expects.
    """
    return audio.astype(np.float32) / 32768.0


class Transcriber:
    """Wraps a Faster-Whisper `WhisperModel` for one-shot transcription of
    a buffered audio clip (as opposed to true streaming transcription,
    which is out of scope for this milestone).
    """

    def __init__(
        self,
        model_size: str = DEFAULT_MODEL_SIZE,
        device: str = DEFAULT_DEVICE,
        compute_type: str = DEFAULT_COMPUTE_TYPE,
        language: str | None = "en",
    ) -> None:
        self._language = language

        logger.info(
            "Loading Faster-Whisper model '%s' (device=%s, compute_type=%s) — "
            "first run downloads weights from Hugging Face Hub, cached after that...",
            model_size,
            device,
            compute_type,
        )
        try:
            self._model = WhisperModel(model_size, device=device, compute_type=compute_type)
        except Exception as exc:
            raise RuntimeError(
                f"Could not load Faster-Whisper model '{model_size}'. This requires an "
                "internet connection the first time it's used to download model weights. "
                f"Underlying error: {exc}"
            ) from exc

        logger.info("Faster-Whisper model '%s' ready.", model_size)

    def transcribe(self, audio_int16: np.ndarray) -> str:
        """Transcribe a buffered clip of int16 mono audio and return the text.

        Returns an empty string if no speech was recognized (e.g. the clip
        was silence or noise only).
        """
        if audio_int16.size == 0:
            return ""

        audio_float32 = int16_to_float32(audio_int16)
        segments, info = self._model.transcribe(audio_float32, language=self._language)
        text = " ".join(segment.text.strip() for segment in segments).strip()

        logger.debug(
            "Transcribed %.2fs of audio (detected language=%s, prob=%.2f): %r",
            audio_int16.size / 16_000,
            info.language,
            info.language_probability,
            text,
        )
        return text
