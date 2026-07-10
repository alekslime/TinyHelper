# Roadmap

Iris is built one milestone at a time. Each milestone must build/run
successfully before the next begins. This roadmap is a living document —
update it as milestones complete or priorities shift.

## Milestone 1 — Project Scaffolding ✅ COMPLETE

- [x] Initialize repository
- [x] Create project folder structure
- [x] Configure dependency management (`pyproject.toml`, optional extras)
- [x] Configuration system (`config/`)
- [x] Logging (`utils/logger.py`)
- [x] Main application entry point (`main.py`)
- [x] Minimal PySide6 application launches
- [x] Aura placeholder renderer interface (structure only, no rendering)
- [x] Documentation files

## Milestone 2 — Wake Word Detection ✅ COMPLETE

- [x] Integrate OpenWakeWord
- [x] Microphone input handling
- [x] Wake word triggers Aura → LISTENING state transition
- [x] Configurable wake word / sensitivity in settings

## Milestone 3 — Speech-to-Text ✅ COMPLETE

- [x] Integrate Faster-Whisper for local transcription
- [x] Capture audio after wake word, transcribe locally
- [x] Handle silence detection / end-of-utterance

## Milestone 4 — Local LLM Integration ✅ COMPLETE

- [x] Integrate llama.cpp via llama-cpp-python
- [x] Model selection appropriate for 8GB VRAM (RTX 3070 Ti)
- [x] Basic prompt/response loop (text only, no vision yet)

## Milestone 5 — Screen Capture + Vision (planned)

- [ ] Integrate MSS for screenshot capture
- [ ] Vision model integration (ONNX Runtime)
- [ ] Screenshot discarded after use by default (privacy requirement)

## Milestone 6 — Aura Rendering (planned)

- [ ] Real GPU-rendered ambient edge glow (replaces `NullAuraRenderer`)
- [ ] State-based color transitions (idle/listening/thinking/waiting/error)
- [ ] Smooth fade in/out, no sharp edges, no neon/pulsing

## Milestone 7 — Visual Guidance (planned)

- [ ] Overlay rendering: circles, arrows, highlights, bounding boxes, labels
- [ ] Triggered by LLM/vision reasoning about screen content

## Milestone 8 — Voice Responses (planned)

- [ ] Local text-to-speech output

## Milestone 9 — Conversation Memory (planned)

- [ ] SQLite-backed conversation history
- [ ] Retrieval for follow-up context

## Milestone 10 — Settings UI (planned)

- [ ] User-facing settings screen (wraps `config/` system)

## Later / Out of scope for MVP

- Mouse/keyboard automation (`automation/`)
- Aura theming system for community-created themes
- Mobile support
- Optional cloud integrations

## Notes

- Milestone order may shift based on what proves hardest/easiest in practice.
- Each milestone should end with a working build and an updated `HANDOFF.md`.
