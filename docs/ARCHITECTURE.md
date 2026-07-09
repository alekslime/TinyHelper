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
├── voice/           Wake word detection, voice activation (future milestone).
├── speech/          Speech-to-text (Faster-Whisper) (future milestone).
├── llm/             Local LLM integration (llama.cpp) (future milestone).
├── vision/           Screen capture + vision model integration (future milestone).
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

## Data flow (target, once all milestones land)

```
Wake word detected (voice/)
        │
        ▼
Aura → LISTENING (aura/controller)
        │
        ▼
Speech captured & transcribed (speech/)
        │
        ▼
Aura → THINKING
        │
        ▼
Screenshot captured (vision/) ── discarded after use unless user saves it
        │
        ▼
Local LLM reasons over transcript + screen context (llm/)
        │
        ▼
Response: voice output + optional visual guidance (overlay/)
        │
        ▼
Aura → IDLE
```

This flow is aspirational — it documents the target architecture, not
current functionality. Update this diagram as each stage is implemented.
