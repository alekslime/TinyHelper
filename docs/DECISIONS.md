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

## 2026-07-09 — Speech-to-text failure must not disable wake word detection

**Decision:** `VoiceActivationService` catches any exception from loading
the Faster-Whisper model and continues with `self._transcriber = None`
rather than letting construction fail. Wake word detection has zero
dependency on transcription working — an utterance just gets discarded
(logged as a warning) if the transcriber isn't available.

**Why:** These are two independently-failing external dependencies (a
downloaded wake word model vs. downloaded Whisper weights), and a failure
in one has no logical reason to take down the other. Coupling them would
have been a regression from Milestone 2, where wake word detection already
had its own independent graceful-degradation path.

---

## 2026-07-09 — Mode-based frame routing, one microphone stream

**Decision:** `VoiceActivationService` owns a single `MicrophoneStream` and
routes each incoming frame to either the wake word detector or the active
`ListeningSession`, based on internal state — never both, and never two
separate audio streams.

**Why:** Opening two simultaneous `InputStream`s to the same audio device
is wasteful and can cause device-contention issues on some platforms/drivers.
Since wake word listening and utterance capture are mutually exclusive in
time (you're never doing both at once), a single stream with mode-based
routing is simpler and more robust than coordinating two streams.

---

## 2026-07-09 — Transcription runs on a dedicated worker thread, not the audio thread

**Decision:** Once a `ListeningSession` finishes, `VoiceActivationService`
immediately clears it (so the audio callback goes back to routing frames
to the wake word detector without gap) and hands the captured audio to a
new `threading.Thread` for transcription, rather than calling
`Transcriber.transcribe()` directly from the audio callback.

**Why:** `sounddevice`'s audio callback must return quickly — a Faster-Whisper
transcription call can take anywhere from under a second to several
seconds depending on hardware and model size (particularly relevant given
this project's range of target/dev hardware, from an RTX 3070 Ti down to a
Quadro M3000M laptop). Blocking the audio callback for that long would
drop incoming audio, potentially missing the very next wake word.
Transcription results are delivered back to the Qt main thread via
`app/transcript_bridge.py`, following the same pattern established for
wake word detections in `docs/DECISIONS.md`'s earlier entry on threading.


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

---

## 2026-07-10 — A debug text input drives the same pipeline as real voice, gated behind config

**Decision:** `app/main_window.py`'s `MainWindow` optionally shows a text
input (behind `debug.enabled` in config, default `True` during early
development). Submitting text emits a Qt signal that `main.py` wires to
call the exact same `on_wake_word_detected()` / `on_transcribed()`
handlers real voice input triggers — not a separate code path.

**Why:** Testing voice input requires speaking out loud, which isn't
practical during meetings or in shared spaces, and will matter even more
once Milestone 4 adds an LLM to test prompts against. Routing debug text
through the *same* handlers (rather than a parallel debug-only code path)
means this is also a regression-testing aid — if debug text input produces
different behavior than voice would, that's a real bug, not divergent
behavior to reconcile separately.

**Why gated behind config, not just always-on:** The project's UX
philosophy explicitly rules out chat windows and visible app windows as
part of Iris's real interaction model (Aura + system tray only). This
debug panel deliberately violates that for development convenience — the
config flag makes it easy to turn off (or the whole panel easy to delete)
once real end-user UX exists, and makes clear in code and docs that this
was never meant to be the shipped experience.

---

## 2026-07-10 — LLM loaded via `Llama.from_pretrained`, same download-and-cache pattern as Whisper

**Decision:** `llm/engine.py`'s `LLMEngine` downloads its GGUF model
from Hugging Face Hub via `llama_cpp.Llama.from_pretrained(repo_id,
filename, ...)` by default, caching it locally after the first run — same
one-time-setup-download pattern as `speech/transcriber.py`'s Faster-Whisper
model. `config.yaml`'s `llm.local_model_path` can override this with a path to
an already-downloaded local `.gguf` file instead, for swapping between
models on disk without touching config defaults.

**Why:** Consistency with the existing speech-to-text pattern, and it
means picking a different/better model later is a one-line config change
in either direction (repo_id/filename, or a local path), not a code
change. Requires `huggingface_hub` as an added dependency in the `llm`
extras group.

---

## 2026-07-10 — Default model picked for "small and working," not final quality

**Decision:** Milestone 4 ships with `Qwen/Qwen2.5-0.5B-Instruct-GGUF`
(`Q4_K_M` quantization, ~1GB) as the default `llm.repo_id`/`llm.filename`.

**Why:** The immediate goal was getting the full wake-word → transcribe →
generate → display pipeline working end-to-end, not picking the best
model the target 8GB-VRAM RTX 3070 Ti could run — a 0.5B model comfortably
fits on both the 3070 Ti and the weaker dev laptop, downloads quickly, and
is enough to prove the pipeline. Response quality was explicitly
deprioritized for this milestone; swapping to a larger/better model once
real-hardware testing shows available headroom is a one-line config
change (see the `from_pretrained` decision above), not a code change.

---

## 2026-07-10 — LLM generation runs on a dedicated worker thread, same as transcription

**Decision:** `main.py`'s `on_transcribed()` hands the transcript to a new
`threading.Thread` calling `LLMEngine.generate()`, rather than calling
it directly. The result (or error) reaches the Qt main thread via
`app/llm_bridge.py`'s `LLMResponseBridge`, the same signal-bridge
pattern as `WakeWordBridge`/`TranscriptBridge`.

**Why:** Generation can take anywhere from under a second to several
seconds depending on hardware and model size — blocking the Qt main
thread for that long would freeze the (currently placeholder) UI and any
future Aura rendering. Aura stays in THINKING for the duration and moves
to IDLE (or ERROR, on failure) only once the bridge delivers a result.

---

## 2026-07-10 — LLM load/dependency failure degrades gracefully, doesn't crash the app

**Decision:** `main.py` imports `llm.generator` inside a
`try/except ImportError` (same pattern as `voice.service`), and separately
catches `RuntimeError` from `LLMEngine`'s constructor (model load
failure). Either way, `llm_generator` is left `None` and `on_transcribed()`
shows a fallback message in the window instead of attempting generation.

**Why:** Consistent with the project's established failure-isolation
philosophy (see the Milestone 3 entry on transcriber load failure not
disabling wake word detection): a missing extra or a failed model
download/load should degrade the specific feature it affects, not take
down the whole app. Voice input still works and gets logged even with no
LLM available.

---

## 2026-07-10 — Screen capture opens a fresh `mss` context per call

**Decision:** `vision/capture.py`'s `ScreenCapture.capture()` opens and
closes its own `mss.mss()` context on every call rather than holding one
open for the object's lifetime.

**Why:** Screen capture in Iris is occasional — triggered per user query,
not continuous (see the README's "no continuous screen or audio
monitoring" privacy principle) — so the small per-call setup cost isn't
worth the complexity of managing a long-lived native handle across calls
and threads. Matches the project's general bias toward simple, obviously-
correct code over premature optimization.

## 2026-07-10 — Screenshots are in-memory only unless a debug flag is set

**Decision:** `ScreenCapture.capture()` never touches disk. Writing a
screenshot to disk only happens via the separate
`capture_and_maybe_save()` method, gated by `vision.save_debug_screenshots`
in config (default `false`).

**Why:** Enforces the "screenshots are analyzed and discarded unless you
explicitly choose to keep one" privacy principle in code, not just docs —
the default path (whatever Milestone 5's vision model integration ends up
calling) can't accidentally start persisting screenshots without an
explicit config change.

---

## 2026-07-10 — Screen-context awareness is opt-in (`vision.enabled`, default `false`)

**Decision:** A new `VisionSettings.enabled` flag (default `false`) gates
the entire screen-context feature in `main.py` — screenshot capture,
captioning, and folding into the LLM prompt all happen only if it's `true`,
independent of whether the `vision` extra is installed.

**Why:** Everything else in Iris so far only reacts to explicit voice/debug
input. Screen capture is qualitatively different — even though each
capture is triggered per-query and never continuous (see the earlier
`mss` context-manager entry), it's still reading whatever is on screen,
which may include far more sensitive content than a spoken question would.
Defaulting to `false` means installing `pip install -e ".[vision]"` alone
never causes a screenshot to be taken; a user has to explicitly turn the
feature on in config. This mirrors `debug.enabled`'s "off until you choose
it" shape, but for a privacy reason rather than a dev-convenience one.

---

## 2026-07-10 — Image captioning via ONNX Runtime + a non-merged decoder

**Decision:** `vision/model.py`'s `VisionModel` uses
`Xenova/vit-gpt2-image-captioning`'s ONNX export: a ViT encoder run once
per screenshot, then a **non-merged** GPT-2 decoder (`decoder_model.onnx`,
no past-key-value cache) called once per generated token, recomputing over
the whole sequence-so-far each time.

**Why:** The "merged" decoder export some tools produce accepts a
`use_cache_branch` flag plus a full set of `past_key_values` tensors on
every call — meaningfully more complex request-building for real, but
mostly hollow correctness risk in this codebase's untested-on-real-hardware
state (see "Known issues"). Captions here are short (`max_new_tokens`
defaults to 30), so the O(n²) recompute cost of the plain decoder is
negligible for a single interactive query. Same "small and working over
clever and fragile" reasoning as Milestone 4's default LLM pick — revisit
if real-hardware timing shows captioning is a bottleneck.

**Also decided:** id↔text conversion uses the standalone `tokenizers`
package (`Tokenizer.from_file(tokenizer.json)`) rather than pulling in all
of `transformers` for one `decode()` call — `transformers` would drag in a
much larger dependency tree for functionality `tokenizers` already covers
by itself. Image preprocessing (resize to 224×224, normalize with
mean/std 0.5) is similarly hand-rolled from the source model's
`preprocessor_config.json` rather than using `transformers`'s
`AutoImageProcessor`.

---

## 2026-07-10 — Aura's real glow is QPainter gradients, not a custom GPU shader

**Decision:** `aura/renderer/glow_renderer.py`'s `GlowAuraRenderer` paints
the ambient edge glow with `QPainter`/`QLinearGradient`/`QRadialGradient`
on a plain (software-backed) `QWidget`, not a `QOpenGLWidget` with hand-
written shader code, even though `docs/ROADMAP.md` originally described
this milestone as "GPU-rendered."

**Why:** Qt's raster/GPU backend already accelerates `QPainter` drawing
under the hood on real hardware, and a soft multi-stop gradient glow is
well within what it handles smoothly — a custom shader pipeline would add
real complexity (a `QOpenGLWidget`, GLSL source, buffer/uniform
management) for a visual result a gradient-based approach already
achieves. Verified for real in this sandbox (offscreen Qt): rendered each
`AuraState`'s glow to a PNG and confirmed via pixel sampling that color
intensity peaks at the corners/edges and fades to fully transparent by
the screen center, with no visible seam between adjacent edge bands
(`QPainter.CompositionMode_Plus` blends the overlapping edge/corner
gradients additively). Revisit only if real-hardware testing shows a
performance problem a pure `QPainter` approach can't solve.

**Also decided:** the overlay window is frameless, always-on-top, and
click-through (`Qt.WA_TransparentForMouseEvents`) so it never intercepts
input meant for whatever the user is actually working in — consistent
with Iris being a background copilot, not a foreground app that steals
focus.

**Known limitation:** the overlay only covers the *primary* screen's
geometry, not the combined virtual geometry of all monitors — real
multi-monitor spanning is a follow-up, not yet implemented. See
`docs/TODO.md`.

---

## 2026-07-10 — Screen context is folded into the prompt as a bracketed prefix

**Decision:** When screen context is available, `main.py` builds the LLM
prompt as `"[Current screen shows: {caption}]\n\nUser: {text}"` rather
than, say, a separate system-prompt field or a structured multi-message
payload.

**Why:** `LLMEngine.generate()` is deliberately a single-string-in,
single-string-out interface (see the Milestone 4 entries above) — keeping
it that way means the vision feature didn't require touching
`llm/engine.py` at all, just the prompt text assembled in `main.py` before
calling it. This is a simple starting point, not a final answer — revisit
once real screenshots/captions are seen on real hardware and it's clear
whether the LLM actually makes good use of a bracketed caption versus
needing a more structured format or an explicit system-prompt change.

---

## 2026-07-11 — Restyled the glow from a wide soft wash to a thin neon border

**Decision:** After the user ran Milestone 6 on real hardware, the 140px-
deep soft gradient (from the previous decision above) read as a faint
blue haze rather than a visible border, and didn't match the punchy,
uniform neon-strip look the user wanted (reference: a saturated
cyan/teal bias-light border of consistent thickness on all four edges).
Restyled `glow_renderer.py` to layer two elements instead of one wide
gradient: a thin, near-solid, saturation-boosted "core" line (5px,
alpha 235) right at the edge, plus a much shorter bloom band (70px, down
from 140px) for soft falloff around it. Added a `_vivid()` helper that
pushes every state color to near-max HSV saturation/value before
painting, so the border reads as neon rather than the flatter tones used
elsewhere in the app.

**Why not just make the existing gradient more opaque:** a wider, more
opaque wash would still look like a tinted haze covering a large
fraction of the screen, not a border. The user's reference image was
specifically a thin outline with heavy blur concentrated close to the
edge — that's a different shape (core + short bloom), not just a
stronger version of the same wide gradient.

**Verification:** re-rendered each `AuraState` offscreen and visually
confirmed (via saved PNGs) the border now appears as a thin, saturated
line consistent on all four edges, with a much tighter falloff than
before. **Not yet confirmed over real desktop content** — real-hardware
re-check is in `docs/TODO.md`.

**Known follow-up:** `CORE_WIDTH`, `CORE_ALPHA`, `GLOW_DEPTH`, and
`GLOW_EDGE_ALPHA` are still eyeballed constants, not tuned against a real
display — may need adjustment once seen for real, particularly since the
previous round of hand-tuned constants (the 140px version) also needed
revision after real-hardware feedback.
