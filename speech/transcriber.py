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

# Substrings seen in ctranslate2/faster-whisper errors when a CUDA-capable
# GPU was detected (so device="auto" picked "cuda") but the actual CUDA
# runtime libraries aren't loadable at inference time -- e.g. a GPU driver
# is installed but the CUDA/cuBLAS/cuDNN redistributables aren't, or are
# the wrong major version. This is a *runtime* failure, not a load-time
# one: `WhisperModel(...)` succeeds, and the crash only happens on the
# first real `.transcribe()` call, inside ctranslate2's C++ layer -- so it
# can't be caught at __init__ time, only here.
_CUDA_RUNTIME_ERROR_MARKERS = ("cublas", "cudnn", "cuda", "nvcuda")


def _looks_like_cuda_runtime_failure(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(marker in message for marker in _CUDA_RUNTIME_ERROR_MARKERS)


def int16_to_float32(audio: np.ndarray) -> np.ndarray:
    """Convert int16 PCM audio (as produced by MicrophoneStream) to the
    normalized float32 format Faster-Whisper expects.
    """
    return audio.astype(np.float32) / 32768.0


class Transcriber:
    """Wraps a Faster-Whisper `WhisperModel` for one-shot transcription of
    a buffered audio clip (as opposed to true streaming transcription,
    which is out of scope for this milestone).

    Auto-recovers from a broken CUDA runtime: if the GPU path fails on
    first use (see `_looks_like_cuda_runtime_failure`), permanently
    switches to CPU and retries, rather than failing every single
    utterance forever with the same error. See docs/DECISIONS.md.
    """

    def __init__(
        self,
        model_size: str = DEFAULT_MODEL_SIZE,
        device: str = DEFAULT_DEVICE,
        compute_type: str = DEFAULT_COMPUTE_TYPE,
        language: str | None = "en",
    ) -> None:
        self._language = language
        self._model_size = model_size
        self._compute_type = compute_type
        self._fell_back_to_cpu = False

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

    def _reload_on_cpu(self) -> None:
        logger.warning(
            "Faster-Whisper's CUDA path failed at runtime (GPU detected but its CUDA "
            "libraries aren't loadable — driver/runtime mismatch or missing redistributables). "
            "Falling back to CPU for the rest of this session. Transcription will be slower "
            "but should stop failing."
        )
        self._model = WhisperModel(self._model_size, device="cpu", compute_type="int8")
        self._fell_back_to_cpu = True
        logger.info("Faster-Whisper model '%s' reloaded on CPU.", self._model_size)

    def transcribe(self, audio_int16: np.ndarray) -> str:
        """Transcribe a buffered clip of int16 mono audio and return the text.

        Returns an empty string if no speech was recognized (e.g. the clip
        was silence or noise only).
        """
        if audio_int16.size == 0:
            return ""

        audio_float32 = int16_to_float32(audio_int16)

        try:
            text = self._run_transcription(audio_float32)
        except Exception as exc:
            if self._fell_back_to_cpu or not _looks_like_cuda_runtime_failure(exc):
                # Either already on CPU (so this is some other failure and
                # retrying won't help) or not a CUDA-shaped error at all —
                # let the caller's existing graceful-degradation handling
                # (voice/service.py logs and returns to idle) take over.
                raise
            self._reload_on_cpu()
            text = self._run_transcription(audio_float32)

        return text

    def _run_transcription(self, audio_float32: np.ndarray) -> str:
        segments, info = self._model.transcribe(audio_float32, language=self._language)
        text = " ".join(segment.text.strip() for segment in segments).strip()

        logger.debug(
            "Transcribed %.2fs of audio (detected language=%s, prob=%.2f): %r",
            audio_float32.size / 16_000,
            info.language,
            info.language_probability,
            text,
        )
        return text
