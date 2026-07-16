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

## Milestone 5 — Screen Capture + Vision ✅ COMPLETE

- [x] Integrate MSS for screenshot capture
- [x] Vision model integration (ONNX Runtime) — image captioning folded into the LLM prompt
- [x] Screenshot discarded after use by default (privacy requirement) — and the whole
      feature is opt-in via `vision.enabled` (default `false`), not just non-persistent

## Milestone 6 — Aura Rendering ✅ COMPLETE

- [x] Real rendered ambient edge glow (`aura/renderer/glow_renderer.py`'s
      `GlowAuraRenderer`), replacing `NullAuraRenderer` as the default
      — built with QPainter gradients rather than a literal custom GPU
      shader; see docs/DECISIONS.md for why that still meets this
      milestone's intent.
- [x] State-based color transitions (idle/listening/thinking/waiting/error)
- [x] Smooth fade in/out, no sharp edges, no neon/pulsing — colors
      cross-fade once per state change (350ms) and then sit still

## Milestone 7 — Visual Guidance ✅ CODE-COMPLETE (pending real-hardware pass on B.4)

- [x] Overlay rendering — a single flashed rectangle outline (not the
      original circles/arrows/labels scope; see docs/DECISIONS.md for
      why the simpler design was chosen)
- [x] Triggered by LLM/vision reasoning about screen content —
      `VisionModel.locate()`, wired into `main.py`'s query flow
- [x] Early-dismiss on the next query or a ~4s cursor dwell (Part B.4)

## Milestone 8 — Voice Responses ✅ COMPLETE (confirmed on real hardware)

- [x] Local text-to-speech output (Piper, via `piper-tts`) — see
      `docs/DECISIONS.md` and `HANDOFF.md`'s Session 7 for the
      "the previous zip didn't actually contain this" story, and
      Session 8 for the real-hardware bug (`synthesize_wav()`'s call
      shape) found and fixed. Confirmed end-to-end on real hardware
      (Windows, RTX 3070 Ti): LLM, vision, OCR, wake word, Whisper, and
      TTS all load and run correctly, real audio plays.

## Milestone 9 — Conversation Memory (in progress)

- [x] **Part A: SQLite-backed conversation history** — each
      query/response turn persisted to a local SQLite database as it
      happens. See `memory/store.py`'s `ConversationStore`,
      `MemorySettings` in `config/schema.py`, and `HANDOFF.md`'s
      Session 9 entry. Confirmed on real hardware (Windows, RTX 3070 Ti):
      `%APPDATA%\Iris\data\conversations.db` created, 3 real turns
      persisted and read back correctly, in order.
- [ ] Part B: retrieval for follow-up context (not started — separate
      session, deliberately out of scope for Part A)

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
