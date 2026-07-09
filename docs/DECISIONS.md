# Decisions

A log of notable architectural and design decisions, why they were made,
and what alternatives were considered. Add an entry whenever a decision is
made that a future session (or contributor) would otherwise have to
re-derive or might accidentally reverse.

---

## 2026-07-09 — Aura communicates via a controller + state enum, not direct calls

**Decision:** All Aura state changes go through `AuraController.set_state(AuraState.X)`.
No module outside `aura/` imports a renderer directly.

**Why:** The project requires Aura to remain "completely independent from
the AI logic" and support a future community theming system. A thin,
state-based interface is the smallest contract that achieves this — any
future renderer just needs to implement `AuraRenderer` and react to five
enum values.

**Alternative considered:** Event bus / pub-sub system. Rejected for now as
over-engineering at this stage — a direct controller call is simpler to
reason about with only one consumer (the renderer) so far. Revisit if
multiple independent listeners to Aura state emerge (e.g. logging,
telemetry, a future settings UI showing live state).

---

## 2026-07-09 — `NullAuraRenderer` ships before any real rendering

**Decision:** Milestone 1 ships an abstract `AuraRenderer` interface and a
no-op `NullAuraRenderer` implementation, not a real GPU renderer.

**Why:** Per the project's incremental development workflow, Milestone 1's
scope is explicitly "placeholder renderer interface... no rendering yet."
This lets every later milestone (voice, LLM, vision) integrate against a
stable Aura API immediately, without blocking on the more complex GPU
rendering work planned for Milestone 6.

---

## 2026-07-09 — Config: bundled defaults + user override file, not env vars

**Decision:** Configuration is YAML-based: a version-controlled
`config/default_config.yaml` plus a user-editable file written to
`%APPDATA%/Iris/config/config.yaml` on first run. No environment-variable
based configuration for user-facing settings.

**Why:** Iris is a desktop app for non-technical end users (eventually), not
a server process — a human-editable YAML file in a discoverable location
fits that model better than env vars. `%APPDATA%` is the idiomatic Windows
location for per-user application data.

**Alternative considered:** A single config file with no default/override
split. Rejected because it makes it impossible to distinguish "user
intentionally changed this" from "this is just the shipped default," which
matters once we build a settings UI (Milestone 10) that needs to show
users what they've customized.

---

## 2026-07-09 — Wake word detections cross threads via a Qt signal, not a direct call

**Decision:** `voice/service.py`'s `VoiceActivationService` reports
detections through a plain callback, but `main.py` wires that callback to
`app/wake_word_bridge.py`'s `WakeWordBridge.report_detection`, which emits a
Qt `Signal`. The actual state change (`AuraController.set_state(...)`)
happens in a slot connected to that signal, which Qt delivers on the main
thread.

**Why:** `sounddevice`'s audio callback (and therefore `WakeWordDetector.process_frame`)
runs on a background thread, not Qt's main thread. Touching Qt objects — or,
later, GPU rendering resources in a real Aura renderer — from a non-main
thread is unsafe. A Qt signal/slot connection across threads is
automatically queued by Qt's event loop, which is the standard, correct way
to marshal data from a worker thread to the GUI thread. This was worth
doing now (`NullAuraRenderer` doesn't actually touch Qt/GPU resources yet)
because it establishes the right pattern before Milestone 6 makes getting
this wrong an actual bug instead of a latent one.

**Alternative considered:** Direct callback call from the audio thread
straight into `AuraController`. Would work today since `NullAuraRenderer` is
a no-op, but would silently become a threading bug the moment a real Qt- or
GPU-backed renderer lands, and would likely be non-obvious to debug at that
point (intermittent crashes/corruption rather than a clear error).

---

## 2026-07-09 — Voice activation fails gracefully, never crashes the app

**Decision:** `VoiceActivationService.start()` catches any exception from
starting the microphone stream, logs it, and returns `False` rather than
letting the exception propagate. `main.py` checks this return value and
continues running (with Aura set to `ERROR` state) instead of exiting.
Additionally, `main.py` imports `voice.service` in a `try/except ImportError`
block, so Iris still launches with only core dependencies installed (no
`speech` extras) — voice activation is just unavailable in that case.

**Why:** Microphone availability is inherently unreliable — no device
present, OS permission denied, device in use by another app, or (during
early development) the optional `speech` extras simply not installed yet.
None of these should be able to take down the whole application, especially
given the project's broader trajectory toward vision, LLM, and automation
features that don't depend on voice input at all.

**Alternative considered:** Let it crash and rely on the user reading the
traceback. Rejected — Iris is meant to feel like part of the OS, and a
background convenience feature shouldn't be able to take the whole app down
just because a peripheral acted up.

---

## 2026-07-09 — Stock wake word models are downloaded once, not bundled

**Decision:** `voice/wake_word.py:resolve_model()` calls OpenWakeWord's
`download_models()` for stock model names (e.g. `"hey_jarvis"`), which
fetches the model files from GitHub release assets on first use and caches
them locally (inside the installed `openwakeword` package's
`resources/models/` directory) for every run after that.

**Why:** As of openWakeWord 0.6.0, stock models are no longer bundled in
the pip package at all (earlier versions did bundle them, which is what an
earlier version of this file assumed — see "known issues" history in past
`HANDOFF.md` entries for the bug this caused). There is no way to get a
stock model without either this download step or manually placing files
ourselves, so this is not a design choice we could avoid, only one we
needed to handle gracefully (clear error message, wrapped in `RuntimeError`,
if the download fails).

**Nuance for the "offline-first" principle:** This is a one-time setup
asset download, not runtime cloud inference — comparable to downloading LLM
model weights before local inference. It requires internet on the very
first run only; every run after that is fully offline, reading from the
local cache. Once a custom-trained "Hey Iris" model replaces the stock
placeholder, this download path won't be exercised at all (custom models
are loaded directly from a user-provided file path).

---

## 2026-07-09 — Wake word detection needs a cooldown, not just consecutive-frame confirmation

**Decision:** `WakeWordDetector` suppresses further detections for a given
model for `cooldown_seconds` (default 1.5s) after firing once, in addition
to the existing consecutive-frames-above-threshold confirmation.

**Why:** Real-microphone testing (on the actual Windows target machine)
surfaced that a single spoken "Hey Jarvis" produced 3-4 separate detection
callbacks, not one. Root cause: a spoken wake word stays above the
confidence threshold for roughly 0.5-1 second — many more frames than the
`consecutive_frames_required` streak needs to fire — so the streak
re-crosses the confirmation count repeatedly within one utterance.
Consecutive-frame confirmation solves a different problem (rejecting
single-frame noise spikes) and doesn't address this one. Verified the fix
directly: the same real audio clip produced 3 detections with cooldown
disabled and exactly 1 with it enabled.

**Alternative considered:** Requiring a much longer consecutive-frame
streak instead of a time-based cooldown. Rejected — this conflates two
different concerns (noise rejection vs. duplicate suppression) and would
make the noise-rejection threshold uncomfortably coupled to how long
utterances happen to last, which varies by speaker and phrase.


---

## 2026-07-09 — Heavy ML dependencies as optional `pyproject.toml` extras

**Decision:** `faster-whisper`, `llama-cpp-python`, `mss`, `opencv-python`,
`onnxruntime-gpu`, `pywin32` are declared under `[project.optional-dependencies]`,
not core `dependencies`.

**Why:** These are large, sometimes platform/hardware-sensitive packages
(e.g. `onnxruntime-gpu` needs a matching CUDA setup). Installing them all
upfront before the milestones that use them exist would slow down early
development iteration and make it harder to isolate install issues to the
specific feature being built.
