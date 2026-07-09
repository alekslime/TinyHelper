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
    input_device: str | int | None = Field(
        default=None,
        description="Microphone device name/index to use. None = system default.",
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
