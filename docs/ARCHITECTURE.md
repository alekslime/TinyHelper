# Architecture

## Overview

Iris is a modular, local-first desktop application. Each top-level package
owns one concern and communicates with the others through small, explicit
interfaces rather than reaching into each other's internals.

```
iris/
│
├── app/            Application shell: entry-point wiring, main window(s).
├── aura/            Visual overlay system (independent from AI logic).
│   ├── renderer/    Renderer interface + implementations (currently a no-op).
│   ├── shaders/     GPU shader code for the ambient glow (future milestone).
│   ├── themes/      Theme definitions (colors, glow intensity, etc.) (future).
│   └── animations/  Animation logic for state transitions, guidance cues (future).
├── voice/           Wake word detection (OpenWakeWord) + mic capture. Done.
├── speech/          Speech-to-text (Faster-Whisper) + silence detection. Done.
├── llm/             Local LLM integration (llama.cpp). Done.
├── vision/           Screen capture + vision model integration. Done, opt-in.
├── overlay/         Visual guidance rendering: arrows, highlights, boxes (future).
├── memory/          Conversation memory / SQLite persistence (future milestone).
├── automation/      Future mouse/keyboard automation. Out of scope for MVP.
├── config/          Typed settings schema, YAML loading, path definitions.
├── utils/           Cross-cutting utilities (currently: logging).
├── assets/          Static assets (icons, fonts, bundled resources).
├── docs/            This documentation.
├── tests/           Test suite.
└── main.py          Application entry point.
```

## Key design decisions

### Aura is independent from AI logic

Nothing in `voice/`, `llm/`, or `vision/` ever imports from `aura/renderer`
directly. All communication goes through `aura.controller.AuraController`,
which exposes a small state-based API (`set_state(AuraState.THINKING)`, etc.).
This means:

- Aura's rendering implementation can change completely (e.g. from a no-op
  to a real GPU shader renderer) without touching any other module.
- Community-created Aura themes can eventually be swapped in without
  touching application logic.

### Renderer interface, not a concrete renderer, ships first

`aura/renderer/base.py` defines the `AuraRenderer` abstract interface.
`aura/renderer/null_renderer.py` is the only implementation so far — it logs
what it would do instead of rendering anything. This lets the rest of the
app (state transitions, the controller, main.py wiring) be built and tested
now, and the real GPU-rendered glow can be dropped in later behind the same
interface.

### Config: bundled defaults + user overrides

`config/default_config.yaml` is version-controlled and ships with the repo.
On first run, `config/settings.py` writes a user-editable copy to
`%APPDATA%/Iris/config/config.yaml` (or a local `.iris_data/` folder on
non-Windows dev machines). User values override defaults; both are merged
and validated against the `AppSettings` Pydantic schema in
`config/schema.py` before anything else in the app touches them.

### Heavy dependencies are optional extras

`pyproject.toml` keeps `faster-whisper`, `llama-cpp-python`, `mss`,
`opencv-python`, `onnxruntime-gpu`, and `pywin32` as optional extras
(`speech`, `llm`, `vision`, `windows`) rather than core dependencies. They
get installed as the milestones that need them are built, keeping the
environment lean during early development.

This is enforced, not just documented: `main.py` imports `voice.service`
inside a `try/except ImportError` block, so Iris still launches correctly
with only core dependencies installed — voice activation is simply
unavailable in that case, logged as a warning rather than a crash.

### Voice module structure (Milestone 2)

`voice/` is split into three layers, each independently testable:

- `voice/audio_stream.py` — `MicrophoneStream`: raw 16kHz mono audio
  capture via `sounddevice`. Knows nothing about wake words.
- `voice/wake_word.py` — `WakeWordDetector`: wraps OpenWakeWord's `Model`.
  Takes audio frames, calls back on detection. Knows nothing about
  microphones or Qt.
- `voice/service.py` — `VoiceActivationService`: wires the above two
  together and owns their lifecycle (`start()`/`stop()`). This is the only
  piece `main.py` talks to.

### Wake word detections cross threads via a Qt signal

`sounddevice`'s audio callback runs on a background thread. `main.py`
bridges detections onto Qt's main thread via `app/wake_word_bridge.py`'s
`WakeWordBridge`, a `QObject` with a `Signal`. Qt automatically queues
cross-thread signal emissions for delivery on the receiving object's
thread, which is the standard, safe way to get data from a worker thread
to the GUI thread. See `docs/DECISIONS.md` for why this matters even though
`NullAuraRenderer` doesn't touch Qt/GPU resources yet.

### Speech module structure (Milestone 3)

`speech/` mirrors `voice/`'s independently-testable-layers pattern:

- `speech/listening_session.py` — `ListeningSession`: buffers audio frames
  for one utterance, uses RMS-based silence detection to know when the
  user stopped talking. Knows nothing about transcription or wake words.
- `speech/transcriber.py` — `Transcriber`: wraps Faster-Whisper. Takes
  buffered audio, returns text. Knows nothing about microphones or timing.

`voice/service.py`'s `VoiceActivationService` now orchestrates the full
pipeline: it owns the single `MicrophoneStream` and routes each frame to
either the wake word detector (normal listening) or the active
`ListeningSession` (capturing an utterance), based on internal mode state.
When a session finishes, the captured audio is handed to a background
thread for transcription — never the audio callback thread — and the
result reaches Qt's main thread via `app/transcript_bridge.py`, the same
signal-bridge pattern as wake word detections.

### LLM module structure (Milestone 4)

`llm/` follows the same single-responsibility pattern as `voice/`/`speech/`:

- `llm/engine.py` — `LLMEngine`: wraps a llama.cpp `Llama` instance
  (via `llama-cpp-python`) for single-turn prompt/response. Knows nothing
  about transcripts, Aura, or threading — takes text in, returns text out.

`main.py` hands each transcript to `LLMEngine.generate()` on a
dedicated worker thread (never the audio callback or Qt main thread — see
`docs/DECISIONS.md`), with the result delivered back to the main thread
via `app/llm_bridge.py`'s `LLMResponseBridge`, the same
signal-bridge pattern used for wake word detections and transcripts.
There is no conversation memory yet (Milestone 9) — each call is
independent, seeded only with a system prompt.

### Vision module structure (Milestone 5)

`vision/` follows the same single-responsibility, independently-testable-
layers pattern as `voice/`/`speech/`/`llm/`:

- `vision/capture.py` — `ScreenCapture`: wraps `mss` for a single
  screenshot. Knows nothing about vision models, the LLM, or Aura. Never
  writes to disk unless the caller opts into `capture_and_maybe_save()`.
- `vision/model.py` — `VisionModel`: wraps two ONNX Runtime sessions
  (a ViT encoder + a GPT-2 decoder) plus a `tokenizers` `Tokenizer`, for
  single-image captioning (`describe(image) -> str`). Knows nothing about
  screen capture, transcripts, or Aura — takes an image in, returns a
  caption out. Weights are downloaded from Hugging Face Hub on first use
  and cached, same pattern as `llm/engine.py` and `speech/transcriber.py`.

Unlike `llm/engine.py`, screen-context awareness is **also** gated behind
`settings.vision.enabled` (default `false`) in `main.py`, independent of
whether the `vision` extra is installed — see `docs/DECISIONS.md`. When
enabled, `main.py`'s LLM worker thread captures a screenshot, captions it,
and prepends the caption to the prompt text before calling
`LLMEngine.generate()` — `llm/engine.py` itself is untouched.

### Data flow (current, as of Milestone 5 part 2)

```
Wake word detected (voice/wake_word.py)
        │
        ▼
Aura → LISTENING (via app/wake_word_bridge.py)
        │
        ▼
Audio buffered until silence (speech/listening_session.py)
        │
        ▼
Transcribed on a background thread (speech/transcriber.py)
        │
        ▼
Aura → THINKING (via app/transcript_bridge.py)
        │
        ▼
[If vision.enabled] Screenshot captured + captioned on the same
background thread (vision/capture.py, vision/model.py), folded into
the prompt text
        │
        ▼
LLM generates a response on a background thread (llm/engine.py)
        │
        ▼
Response shown in the placeholder window (via app/llm_bridge.py)
        │
        ▼
Aura → IDLE
```

Once Milestones 6-8 land, this extends to: real Aura rendering
(Milestone 6) → optional visual guidance (Milestone 7) → voice response
(Milestone 8) → back to IDLE. Update this diagram as each stage is
implemented.

