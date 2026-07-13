"""Iris application entry point.

Responsible only for wiring things together:
    1. Load configuration.
    2. Set up logging.
    3. Construct the (placeholder, no-op) Aura controller.
    4. Construct voice activation (microphone + wake word detection +
       speech-to-text) and bridge its events onto the Qt main thread.
    5. Construct the local LLM engine and bridge its results onto the Qt
       main thread.
    6. If enabled, construct screen capture + a vision model, so each
       query can be augmented with a caption of the current screen.
    7. Launch the Qt application and a minimal window.

No feature logic belongs here — this file should stay small forever.
"""

from __future__ import annotations

import logging
import sys
import threading

from PySide6.QtWidgets import QApplication

from app.llm_bridge import LLMResponseBridge
from app.main_window import MainWindow
from app.transcript_bridge import TranscriptBridge
from app.wake_word_bridge import WakeWordBridge
from aura.controller import AuraController
from aura.renderer.glow_renderer import GlowAuraRenderer
from aura.renderer.null_renderer import NullAuraRenderer
from aura.states import AuraState
from config.settings import get_settings
from utils.logger import setup_logging

logger = logging.getLogger(__name__)

# `voice.service` depends on the optional "speech" extras (openwakeword,
# sounddevice, faster-whisper) — see pyproject.toml and docs/DECISIONS.md.
# Import it defensively so Iris still launches with just the core
# dependencies installed; voice activation is simply unavailable in that case.
try:
    from voice.service import VoiceActivationService

    _VOICE_AVAILABLE = True
except ImportError:
    VoiceActivationService = None  # type: ignore[assignment,misc]
    _VOICE_AVAILABLE = False

# `llm.engine` depends on the optional "llm" extra (llama-cpp-python) — see
# pyproject.toml and docs/DECISIONS.md. Same defensive-import treatment as
# voice, above — Iris still launches without it, just without generated
# responses.
try:
    from llm.engine import LLMEngine

    _LLM_AVAILABLE = True
except ImportError:
    LLMEngine = None  # type: ignore[assignment,misc]
    _LLM_AVAILABLE = False

# `vision.capture` / `vision.model` depend on the optional "vision" extra
# (mss, onnxruntime, huggingface_hub, tokenizers) — see pyproject.toml and
# docs/DECISIONS.md. Same defensive-import treatment as voice/llm above —
# Iris still launches without it, just without screen-context awareness.
# Screen capture is additionally gated behind `settings.vision.enabled`
# (opt-in, off by default) even when the extra IS installed — see
# `config/schema.py:VisionSettings`.
try:
    from vision.capture import ScreenCapture
    from vision.model import VisionModel
    from vision.ocr import OCRReader

    _VISION_AVAILABLE = True
except ImportError:
    ScreenCapture = None  # type: ignore[assignment,misc]
    VisionModel = None  # type: ignore[assignment,misc]
    OCRReader = None  # type: ignore[assignment,misc]
    _VISION_AVAILABLE = False


def main() -> int:
    settings = get_settings()
    setup_logging(settings.logging)

    logger.info("Starting %s v%s", settings.app_name, settings.version)

    app = QApplication(sys.argv)
    app.setApplicationName(settings.app_name)
    app.setApplicationVersion(settings.version)

    # Real Aura rendering (Milestone 6): a soft ambient screen-edge glow,
    # replacing the placeholder NullAuraRenderer. Falls back to
    # NullAuraRenderer on any construction/initialize failure -- same
    # graceful-degradation shape as the LLM/vision pipelines above, since a
    # missing visual is far less important than Iris staying usable at all.
    try:
        renderer = GlowAuraRenderer()
        aura = AuraController(renderer=renderer)
        aura.start()
    except Exception:
        logger.exception("Could not start the Aura glow renderer — falling back to no visuals.")
        aura = AuraController(renderer=NullAuraRenderer())
        aura.start()

    # Bridges: audio/worker threads -> Qt main thread. See
    # app/wake_word_bridge.py, app/transcript_bridge.py, and
    # app/llm_bridge.py.
    wake_word_bridge = WakeWordBridge()
    transcript_bridge = TranscriptBridge()
    llm_bridge = LLMResponseBridge()

    # Loaded eagerly (like the wake word / Whisper models) so the first
    # real utterance isn't delayed by a cold-start model load. Failure here
    # is NOT fatal to the whole app — same graceful-degradation pattern as
    # VoiceActivationService's transcriber load in voice/service.py.
    llm_engine = None
    if _LLM_AVAILABLE:
        try:
            llm_engine = LLMEngine(
                repo_id=settings.llm.repo_id,
                filename=settings.llm.filename,
                local_model_path=settings.llm.local_model_path,
                n_ctx=settings.llm.n_ctx,
                n_gpu_layers=settings.llm.n_gpu_layers,
                system_prompt=settings.llm.system_prompt,
            )
        except RuntimeError:
            logger.exception("Could not load the LLM — continuing without generated responses.")
            llm_engine = None
    else:
        logger.warning(
            "LLM dependencies not installed (pip install -e '.[llm]') — "
            "continuing without generated responses this session."
        )

    # Screen-context awareness (Milestone 5): opt-in via settings.vision.enabled
    # (default False) on top of the usual extra-installed check, so installing
    # the vision extra alone never causes a screenshot to be taken — see
    # docs/DECISIONS.md. Loaded eagerly, same graceful-degradation shape as
    # the LLM above: a failed model load leaves vision_model = None rather
    # than crashing, and _generate_worker simply skips the screen-context step.
    screen_capture = None
    vision_model = None
    ocr_reader = None
    if not settings.vision.enabled:
        logger.info("Screen-context awareness disabled (vision.enabled=false in config).")
    elif _VISION_AVAILABLE:
        screen_capture = ScreenCapture(monitor_index=settings.vision.monitor_index)
        try:
            vision_model = VisionModel(
                repo_id=settings.vision.repo_id,
                model_filename=settings.vision.model_filename,
                mmproj_filename=settings.vision.mmproj_filename,
                local_model_path=settings.vision.local_model_path,
                local_mmproj_path=settings.vision.local_mmproj_path,
                n_ctx=settings.vision.n_ctx,
                n_gpu_layers=settings.vision.n_gpu_layers,
            )
        except RuntimeError:
            logger.exception(
                "Could not load the vision model — continuing without screen context."
            )
            vision_model = None

        # OCR is independent of the scene-description model above -- a
        # failure here (e.g. Tesseract binary not installed) shouldn't take
        # down scene description, and vice versa. See vision/ocr.py.
        if settings.vision.ocr_enabled:
            try:
                ocr_reader = OCRReader(
                    tesseract_cmd=settings.vision.tesseract_cmd,
                    min_confidence=settings.vision.ocr_min_confidence,
                )
            except RuntimeError:
                logger.exception(
                    "Could not load the OCR reader — continuing without verbatim on-screen text."
                )
                ocr_reader = None
    else:
        logger.warning(
            "Vision dependencies not installed (pip install -e '.[vision]') — "
            "continuing without screen context this session."
        )

    def on_wake_word_detected(model_name: str, score: float) -> None:
        # Runs on the main thread (Qt queues the signal delivery for us).
        logger.info("Wake word '%s' detected (score=%.3f) — Aura -> LISTENING", model_name, score)
        aura.set_state(AuraState.LISTENING)

    def _screen_context_likely(text: str) -> bool:
        # Cheap substring check against settings.vision.trigger_keywords,
        # case-insensitive. Deliberately biased toward false triggers over
        # missed ones -- an unneeded screenshot costs latency, a needed one
        # that's skipped costs a wrong/blind answer, which is worse. See
        # config/schema.py:VisionSettings.gate_on_keywords and
        # docs/DECISIONS.md.
        lowered = text.lower()
        return any(keyword in lowered for keyword in settings.vision.trigger_keywords)

    def _build_prompt_with_screen_context(text: str) -> str:
        # Runs on the same worker thread as generation (see _generate_worker).
        # Capture + captioning happen here, not on the Qt main thread, for
        # the same reason LLM generation does — this can take real time
        # (MiniCPM-V-2.6 is CPU-only on the target 8GB-VRAM hardware, see
        # docs/DECISIONS.md). Any failure here is logged and swallowed —
        # screen context is a nice-to-have, never worth failing the whole
        # query over.
        if screen_capture is None or (vision_model is None and ocr_reader is None):
            return text
        if settings.vision.gate_on_keywords and not _screen_context_likely(text):
            logger.debug("Skipping screen context — no trigger keyword in transcript.")
            return text
        try:
            image = screen_capture.capture()
        except Exception:
            logger.exception("Screen capture failed — continuing without screen context.")
            return text

        caption = ""
        if vision_model is not None:
            try:
                caption = vision_model.describe(
                    image,
                    prompt=settings.vision.caption_prompt,
                    max_tokens=settings.vision.max_tokens,
                )
            except Exception:
                logger.exception("Screen captioning failed — continuing without scene description.")

        ocr_text = ""
        if ocr_reader is not None:
            try:
                ocr_text = ocr_reader.read(image)
            except Exception:
                logger.exception("OCR failed — continuing without verbatim on-screen text.")

        if not caption and not ocr_text:
            return text

        context_lines = []
        if caption:
            context_lines.append(f"Screen description: {caption}")
        if ocr_text:
            context_lines.append(f"Verbatim text on screen: {ocr_text}")
        context = "\n".join(context_lines)

        logger.debug("Screen context added to prompt: %r", context)
        return f"[{context}]\n\nUser: {text}"

    def _generate_worker(text: str) -> None:
        # Runs on a dedicated worker thread — never the audio callback
        # thread or the Qt main thread, same reasoning as transcription
        # (see docs/DECISIONS.md). Delivers its result back via llm_bridge.
        assert llm_engine is not None  # only started when it loaded successfully
        try:
            prompt = _build_prompt_with_screen_context(text)
            response = llm_engine.generate(
                prompt,
                max_tokens=settings.llm.max_tokens,
                temperature=settings.llm.temperature,
            )
            if response:
                llm_bridge.report_response(response)
            else:
                llm_bridge.report_failure("LLM returned an empty response.")
        except Exception as exc:
            logger.exception("LLM generation failed.")
            llm_bridge.report_failure(str(exc))

    def on_transcribed(text: str) -> None:
        # Runs on the main thread. Keeps Aura in THINKING while the LLM
        # generates a response on a worker thread; on_llm_response /
        # on_llm_failed bring it back to IDLE (or ERROR) once that's done.
        logger.info('Transcribed: "%s" — Aura -> THINKING', text)
        aura.set_state(AuraState.THINKING)

        if llm_engine is None:
            logger.warning("No LLM available — skipping generation.")
            window.show_response("(No LLM available this session — see logs.)")
            aura.set_state(AuraState.IDLE)
            return

        threading.Thread(target=_generate_worker, args=(text,), daemon=True).start()

    def on_llm_response(text: str) -> None:
        # Runs on the main thread.
        logger.info('LLM response ready (%d chars) — Aura -> IDLE', len(text))
        window.show_response(text)
        aura.set_state(AuraState.IDLE)

    def on_llm_failed(message: str) -> None:
        # Runs on the main thread.
        logger.error("LLM generation failed: %s", message)
        window.show_response(f"(LLM error — see logs: {message})")
        aura.set_state(AuraState.ERROR)

    def on_no_speech_detected() -> None:
        # Runs on the main thread. Wake word fired but nothing was said
        # (or transcription was unavailable) — just go back to idle.
        logger.info("No speech recognized — Aura -> IDLE")
        aura.set_state(AuraState.IDLE)

    wake_word_bridge.detected.connect(on_wake_word_detected)
    transcript_bridge.transcribed.connect(on_transcribed)
    transcript_bridge.no_speech_detected.connect(on_no_speech_detected)
    llm_bridge.response_ready.connect(on_llm_response)
    llm_bridge.generation_failed.connect(on_llm_failed)

    voice_service = None
    if _VOICE_AVAILABLE:
        voice_service = VoiceActivationService(
            voice_settings=settings.voice,
            speech_settings=settings.speech,
            on_wake_word=wake_word_bridge.report_detection,
            on_transcript=transcript_bridge.report_transcript,
        )
        if not voice_service.start():
            logger.warning("Continuing without voice activation this session (see error above).")
            aura.set_state(AuraState.ERROR)
    else:
        logger.warning(
            "Voice activation dependencies not installed (pip install -e '.[speech]') — "
            "continuing without wake word detection this session."
        )

    window = MainWindow(
        app_name=settings.app_name,
        app_version=settings.version,
        debug_enabled=settings.debug.enabled,
    )
    window.show()

    def on_debug_text_submitted(text: str) -> None:
        # Drives the exact same handling path real voice input would:
        # a synthetic "wake word" event, then the typed text as if it were
        # the transcription result. Now also exercises the LLM the same
        # way real voice input would.
        logger.info('Debug text input treated as a voice command: "%s"', text)
        on_wake_word_detected("debug_text_input", 1.0)
        on_transcribed(text)

    window.debug_text_submitted.connect(on_debug_text_submitted)

    exit_code = app.exec()

    if voice_service is not None:
        voice_service.stop()
    aura.stop()
    logger.info("%s exited with code %s", settings.app_name, exit_code)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
