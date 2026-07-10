"""Typed configuration schema for Iris.

Every configurable aspect of the app is declared here as a Pydantic model.
This gives us validation, sane defaults, and autocompletion everywhere the
settings object is used, instead of passing raw dicts around.

New sections should be added here as their corresponding feature is built
(e.g. VoiceSettings once wake-word detection lands), not before.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class LoggingSettings(BaseModel):
    """Controls application-wide logging behavior."""

    level: str = Field(default="INFO", description="Root log level.")
    console: bool = Field(default=True, description="Mirror logs to stdout.")
    file: bool = Field(default=True, description="Write logs to a rotating file.")
    max_bytes: int = Field(default=2_000_000, description="Max size per log file before rotation.")
    backup_count: int = Field(default=5, description="Number of rotated log files to keep.")


class AuraSettings(BaseModel):
    """Placeholder settings for the Aura visual system.

    Aura rendering itself is not implemented until a later milestone; this
    section exists now so the config schema doesn't need breaking changes
    when it is.
    """

    enabled: bool = Field(default=True, description="Whether Aura overlay is active.")
    theme: str = Field(default="default", description="Name of the active Aura theme.")


class VoiceSettings(BaseModel):
    """Wake word / microphone settings.

    `wake_word_model` accepts either a bundled stock model name (e.g.
    "hey_jarvis", used as a placeholder during development) or a full path
    to a custom-trained `.onnx` model (e.g. a "Hey Iris" model trained via
    https://openwakeword.com/train). Swapping between them requires no code
    changes — see `voice/wake_word.py:resolve_model_path`.
    """

    wake_word_model: str = Field(
        default="hey_jarvis",
        description="Stock model name or path to a custom .onnx wake word model.",
    )
    detection_threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Minimum confidence score to consider the wake word heard.",
    )
    consecutive_frames_required: int = Field(
        default=2,
        ge=1,
        description="Consecutive frames above threshold needed to confirm detection.",
    )
    cooldown_seconds: float = Field(
        default=1.5,
        ge=0.0,
        description="Seconds to suppress further detections after one fires, so one utterance = one trigger.",
    )
    input_device: str | int | None = Field(
        default=None,
        description="Microphone device name/index to use. None = system default.",
    )


class SpeechSettings(BaseModel):
    """Speech-to-text (Faster-Whisper) and utterance-capture settings.

    Faster-Whisper downloads model weights from Hugging Face Hub on first
    use per `model_size`, then caches them locally — see
    `speech/transcriber.py` and `docs/DECISIONS.md`.
    """

    model_size: str = Field(
        default="small",
        description="Faster-Whisper model size (e.g. tiny, base, small, medium, large-v3).",
    )
    device: str = Field(
        default="auto",
        description="Inference device: 'auto', 'cpu', or 'cuda'.",
    )
    compute_type: str = Field(
        default="default",
        description="Faster-Whisper compute type (e.g. 'default', 'int8', 'float16').",
    )
    language: str | None = Field(
        default="en",
        description="Force a language code, or None to auto-detect per utterance.",
    )
    silence_rms_threshold: float = Field(
        default=300.0,
        ge=0.0,
        description="RMS energy below which a frame is considered silence.",
    )
    end_silence_seconds: float = Field(
        default=1.0,
        ge=0.0,
        description="Seconds of silence after speech that ends an utterance.",
    )
    initial_timeout_seconds: float = Field(
        default=3.0,
        ge=0.0,
        description="Seconds to wait for speech to start before giving up (e.g. accidental wake word).",
    )
    max_duration_seconds: float = Field(
        default=10.0,
        ge=0.0,
        description="Absolute cap on utterance length, regardless of silence detection.",
    )


class LLMSettings(BaseModel):
    """Local LLM (llama.cpp via llama-cpp-python) settings.

    Weights are fetched from Hugging Face Hub via `repo_id`/`filename` on
    first use and cached locally, same download-once pattern as
    `SpeechSettings.model_size` — see `llm/engine.py` and
    `docs/DECISIONS.md`. Set `local_model_path` to bypass the Hub entirely
    and load a `.gguf` file directly (e.g. a manually-downloaded larger
    model for the RTX 3070 Ti target).
    """

    repo_id: str = Field(
        default="Qwen/Qwen2.5-0.5B-Instruct-GGUF",
        description="Hugging Face repo to pull GGUF weights from, if local_model_path is unset.",
    )
    filename: str = Field(
        default="qwen2.5-0.5b-instruct-q4_k_m.gguf",
        description="GGUF filename within repo_id to download.",
    )
    local_model_path: str | None = Field(
        default=None,
        description="Path to a local .gguf file. Overrides repo_id/filename when set.",
    )
    n_ctx: int = Field(default=4096, ge=512, description="Context window size, in tokens.")
    n_gpu_layers: int = Field(
        default=-1,
        description=(
            "Number of model layers to offload to GPU. -1 = all layers "
            "(recommended when VRAM allows)."
        ),
    )
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Sampling temperature.")
    max_tokens: int = Field(
        default=512, ge=1, description="Maximum tokens to generate per response."
    )
    system_prompt: str = Field(
        default=(
            "You are Iris, a concise local AI desktop copilot. Keep answers short "
            "and to the point unless the user asks for more detail."
        ),
        description="System prompt prepended to every generation call.",
    )


class VisionSettings(BaseModel):
    """Screen capture + vision model settings (Milestone 5).

    Privacy is the default in two ways: `vision/capture.py`'s
    `ScreenCapture` returns an in-memory image and nothing is written to
    disk unless `save_debug_screenshots` is explicitly turned on, and the
    whole feature (capture + captioning + folding into the LLM prompt) is
    off by default until `enabled` is turned on -- see `docs/DECISIONS.md`.
    """

    enabled: bool = Field(
        default=False,
        description=(
            "Master switch for screen-context awareness. When false (the "
            "default), Iris never captures the screen at all -- opt-in, "
            "not opt-out. When true, a screenshot is captured and captioned "
            "alongside every voice/debug query and folded into the LLM prompt."
        ),
    )
    monitor_index: int = Field(
        default=0,
        ge=0,
        description=(
            "Which monitor to capture, per `mss`'s numbering. 0 = the "
            "virtual bounding box of *all* monitors combined; 1, 2, ... "
            "select an individual monitor."
        ),
    )
    save_debug_screenshots: bool = Field(
        default=False,
        description=(
            "Developer aid only. When true, each capture is also written "
            "to disk under debug_screenshot_dir for inspection. Off by "
            "default -- screenshots are discarded after use, per Iris's "
            "privacy-by-default principle."
        ),
    )
    debug_screenshot_dir: str | None = Field(
        default=None,
        description=(
            "Directory to write debug screenshots to when "
            "save_debug_screenshots is true. None = "
            "<app data dir>/data/debug_screenshots."
        ),
    )
    repo_id: str = Field(
        default="Xenova/vit-gpt2-image-captioning",
        description="Hugging Face repo to pull ONNX vision-model files from, if local_model_dir is unset.",
    )
    encoder_filename: str = Field(
        default="onnx/encoder_model.onnx",
        description="Encoder ONNX filename within repo_id.",
    )
    decoder_filename: str = Field(
        default="onnx/decoder_model.onnx",
        description="Decoder ONNX filename within repo_id.",
    )
    tokenizer_filename: str = Field(
        default="tokenizer.json",
        description="Fast-tokenizer JSON filename within repo_id.",
    )
    local_model_dir: str | None = Field(
        default=None,
        description=(
            "Path to a local directory containing the encoder/decoder/"
            "tokenizer files. Overrides repo_id-based downloading when set."
        ),
    )
    max_new_tokens: int = Field(
        default=30,
        ge=1,
        description="Maximum tokens to generate per screenshot caption.",
    )


class DebugSettings(BaseModel):
    """Developer-only debug aids. None of this is part of Iris's intended
    end-user UX (which uses Aura + system tray, no visible windows or chat
    boxes) — it exists purely to make development/testing easier before
    voice input is convenient to test with (e.g. during meetings, or
    before a working microphone setup exists). Should default to disabled
    once Iris has real end-user-facing UI.
    """

    enabled: bool = Field(
        default=True,
        description="Show developer debug aids (e.g. text input to simulate voice commands).",
    )


class AppSettings(BaseModel):
    """Top-level application settings.

    This is the object the rest of the app imports and reads from. It is
    constructed by `config.settings.load_settings()`.
    """

    app_name: str = Field(default="Iris")
    version: str = Field(default="0.1.0")
    first_run: bool = Field(default=True, description="Set to False after first successful launch.")

    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    aura: AuraSettings = Field(default_factory=AuraSettings)
    voice: VoiceSettings = Field(default_factory=VoiceSettings)
    speech: SpeechSettings = Field(default_factory=SpeechSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    vision: VisionSettings = Field(default_factory=VisionSettings)
    debug: DebugSettings = Field(default_factory=DebugSettings)
