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

---

## 2026-07-11 — Merged core+bloom into one gradient with a feather, and added a slow breathing pulse

**Decision:** Two changes to `glow_renderer.py` after real-hardware
feedback on the thin-core version above: (1) the separate "core"
rectangle and "bloom" rectangle per edge were merged into a single
`QLinearGradient`/`QRadialGradient` with several stops, feathering up
from transparent at the true screen edge over `FEATHER_PX` (12px) to a
peak, then decaying smoothly to transparent by `GLOW_DEPTH`; (2) a
`QTimer`-driven sine wave now continuously scales that peak alpha
between `BREATH_MIN` and `BREATH_MAX` on a `BREATH_PERIOD_S`-second
cycle, repainting on every tick.

**Why:** the two-rectangle version had a visible seam where the core's
inner edge stopped and the bloom continued alone — two independently
authored alpha curves meeting at a boundary rarely lines up smoothly.
A single gradient with intermediate stops avoids that by construction.
Separately, the fully static version (color only changes on state
transition, otherwise pixel-identical every frame) read as flat on a
real display in a way it hadn't in the offscreen previews — a slow
breathing pulse is a common technique for ambient UI elements
specifically to counter that flatness without being distracting.

**Revises:** the original Milestone 6 "no pulsing" constraint (see the
first glow-renderer entry above) is intentionally superseded here, based
on direct user feedback after seeing the static version live. The
distinction that constraint was protecting against — no sharp,
attention-grabbing flashing — still holds; a 4.2-second smooth sine
breath is a different thing than the flashing/pulsing it was written to
avoid.

**Verification:** offscreen only. Rendered the gradient at several fixed
breath values (0.72, 0.86, 1.0) and a cropped corner close-up to confirm
the feather removes the seam and the dim/bright range looks reasonable.
The timer loop itself (real elapsed-time-driven animation) was checked
by evaluating the sine formula at several time offsets, not by watching
it animate live (no real display in this sandbox). **Real-hardware
check still needed** — breathing speed/amplitude may want retuning once
seen for real.

---

## 2026-07-11 — Reverted glow size after pixel-comparing against the user's reference

**Decision:** User asked to size the glow up 10%, then 50%, but reported
no visible difference on real hardware either time. Instead of guessing a
third size, took the user's own reference screenshot and did a pixel-level
comparison (mean absolute RGB difference) against offscreen renders at
70px (the pre-existing size), 105px (+50%), and 200px (+185%). The
original 70px render was by far the closest match (~8 mean diff, vs. ~17
and ~41 for the larger ones) — the size was never actually the problem,
and further "zoom in" requests would have kept moving away from what the
user wanted. Reverted `GLOW_DEPTH`/`FEATHER_PX` to 70/12.

**Lesson carried into the next entry below:** when a tweak is reported as
"no difference" more than once, stop nudging the same parameter in the
same direction — go back to a direct, quantitative comparison against
whatever reference the user has provided, rather than guessing again.

---

## 2026-07-11 — Replaced the gradient-stack technique with a real Gaussian blur

**Decision:** After the size revert above, the user explicitly asked for
a different rendering *technique*, not another parameter adjustment on
the existing one ("try another entire design... this concept but another
thing"). Replaced the hand-authored multi-stop-gradient approach (v1–v3
in `docs/TODO.md`'s Milestone 6 history) with an actual Gaussian blur:

1. Paint a solid-color band (`SEED_BAND_PX` = 55px) along all four edges
   onto an offscreen `QImage`.
2. Blur it with `QGraphicsBlurEffect` (`BLUR_RADIUS_PX` = 90) via a
   `QGraphicsScene`/`QGraphicsPixmapItem`, rendered back into a `QImage`.
3. Cache that blurred *shape* (`_build_blurred_mask()`) — it only depends
   on widget size, so it's rebuilt on resize, not every frame.
4. Each frame/breath-tick, re-tint the cached shape to the current
   color and brightness via `QPainter.CompositionMode_SourceIn`
   (`_tint()`) — cheap, since the expensive blur already happened once.

**Why this counts as a different design, not just a bigger blur radius:**
the previous versions all worked by hand-picking an alpha-vs-distance
curve (linear, then multi-stop) and manually patching corners with radial
gradients to avoid seams. A real blur has no such curve to hand-tune and
no seam problem at corners in the first place — the falloff shape is
whatever the blur kernel naturally produces. Verified via pixel sampling
that the falloff is a smooth bell curve (rises from the edge to a peak
around x≈20-30px, decays smoothly to background by x≈150-200px), with no
seam artifacts, unlike any of the gradient-based versions.

**No new dependency:** `QGraphicsBlurEffect` is part of Qt/PySide6, which
is already a core (non-extra) dependency — unlike, say, doing the blur in
Pillow, which is currently only in the `vision` optional-extra and would
have made the base overlay (which must work with zero extras installed)
depend on it.

**Performance note:** building the blurred mask took ~0.3s for a
1920×1080 image in this sandbox. That only happens once at startup and
on resize (rare for a full-screen overlay), not per frame — per-frame
work is just the cheap re-tint. Not yet measured on real target hardware.

**Verification:** offscreen only, same limitation as every prior entry
in this file — rendered each `AuraState`, pixel-sampled the falloff
curve, and exercised a resize to confirm the mask cache invalidates and
rebuilds at the new size without crashing. **Real-hardware check still
needed**, including whether `BLUR_RADIUS_PX`/`SEED_BAND_PX` need retuning
once seen at real size and viewing distance.

---

## 2026-07-11 — Auto-fallback to CPU when Faster-Whisper's CUDA runtime is broken

**Decision:** First real-hardware log showed `Transcriber` loading
successfully, then every `.transcribe()` call failing with `RuntimeError:
Library cublas64_12.dll is not found or cannot be loaded`. `device="auto"`
had detected the RTX 3070 Ti and picked CUDA, but the machine's CUDA/
cuBLAS runtime wasn't actually loadable at inference time. The existing
try/except around transcription (in `voice/service.py`) stopped this from
crashing the app, but didn't stop it from failing identically on every
subsequent utterance — the wake word would fire, listening would work,
and transcription would silently fail forever.

Added `_looks_like_cuda_runtime_failure()` (string-matches on
cublas/cudnn/cuda/nvcuda in the exception message) and had
`Transcriber.transcribe()` catch exactly that failure shape, reload the
model with `device="cpu", compute_type="int8"`, and retry the same clip
immediately — then remember (`self._fell_back_to_cpu`) to skip straight
to CPU on all future calls rather than re-attempting the broken GPU path
every time. Any other exception shape is re-raised unchanged, so it still
surfaces exactly as before.

**Why catch it here instead of at `WhisperModel.__init__`:** the failure
doesn't happen at load time — `WhisperModel(...)` succeeds even though
the CUDA path is broken, because ctranslate2 only touches the cuBLAS
library on the first actual `.encode()` call inside `.transcribe()`. So
this can only be caught where it actually happens, not proactively at
construction.

**Verification:** `tests/test_transcriber.py`, using a mocked
`WhisperModel` — reproduces the literal error message from the user's
log, confirms the second (CPU) attempt succeeds and returns the expected
text, confirms the CPU reload only happens once (`assert_called_once_with`)
even across two subsequent `.transcribe()` calls, and confirms unrelated
exceptions (e.g. `ValueError`) are re-raised without triggering a
pointless reload. **Not yet re-run on the actual machine that hit this**
— that's the natural next real-hardware check.

---

## 2026-07-11 — Backfill missing keys into an existing user `config.yaml` instead of only ever writing it once

**Decision:** Real-hardware check showed the user's `%APPDATA%/Iris/
config/config.yaml` was only 17 lines — missing the entire `speech`,
`llm`, `vision`, and `debug` sections, plus `voice.cooldown_seconds`.
Root cause: `load_settings()` only wrote the user config file inside
`if not USER_CONFIG_FILE.exists()`. That file was created by an early
run of Iris, before those sections/fields existed in `config/schema.py`.
Because the file's mere existence skipped the write branch on every
later run, it stayed frozen at that old shape permanently, no matter how
much the schema grew afterward.

This didn't break runtime behavior — `load_settings()` deep-merges
bundled defaults *under* the user file, so e.g. `vision.enabled` still
correctly resolved to `False` even without a `vision:` key on disk. But
it meant the user had no `vision:` section to actually edit when they
wanted to turn it on, with no indication anything was missing.

Added `_backfill_missing()`: recursively walks the bundled defaults and
adds any key absent from the user's raw dict, at any nesting depth,
without touching or reordering keys the user already has (including
values that differ from the current default, e.g. a customized
`detection_threshold`). `load_settings()` now calls this on every run
(not just first run) when the user file already exists, and only
rewrites the file if something was actually missing — so an up-to-date
file is never needlessly rewritten.

**Why not just always overwrite with `settings.model_dump()`:** that
would silently discard any user customization that isn't itself a valid
override of a *current* default field name — e.g. renamed/removed keys —
and would reformat the whole file (losing edit history/diffs) on every
single launch even when nothing changed. Backfill-only is a strict
superset of "keep what the user has, add what's new."

**Verification:** `tests/test_settings.py` — unit tests for
`_backfill_missing` (new top-level section added, new nested field added
while an existing sibling value is preserved untouched, no-op when
nothing is missing) plus two `load_settings()` integration tests against
real files under `tmp_path` (schema.py/paths.py patched out): one
reproducing the exact bug (an old file missing `vision` entirely gains
it, while a customized `aura.theme` survives), one confirming an
up-to-date file is left byte-for-byte untouched. All pass.

## Vision gated behind trigger keywords, not always-on (2026-07-13)

**Problem:** Milestone 5's screen-context awareness (`vision.enabled`)
captured and captioned the screen on *every* transcribed/debug query, once
turned on. Confirmed working on real hardware, but MiniCPM-V-2.6 is
CPU-only on the 3070 Ti (no spare VRAM alongside the main LLM) and 8B
params, so every query paid real captioning latency even when the query
had nothing to do with the screen.

**Options considered:**
(a) A keyword heuristic on the transcribed text ("screen", "this", "here",
"see", "look") before capturing.
(b) An explicit trigger phrase the user says to opt in per-query (e.g.
"look at my screen").

**Chosen: (a), keyword heuristic.** No new voice UX to teach the user (a
trigger *phrase* the user has to remember and say correctly adds friction
Iris's design otherwise avoids), and it degrades gracefully — a query that
happens to mention "screen" but doesn't need visual context just costs one
unnecessary capture, not a missed one. Implemented as
`VisionSettings.trigger_keywords` (config-driven, same pattern as every
other tunable in the app), checked via case-insensitive substring match in
`main.py`'s `_build_prompt_with_screen_context()` before
`screen_capture.capture()` is called at all. Empty list disables gating
entirely (old always-on behavior), for anyone who wants it back.

**Not yet tuned against real usage** — the default keyword list is a
reasonable starting guess, not validated against how people actually
phrase screen-related questions. Revisit if real usage shows obvious
false negatives (a screen question that doesn't hit any keyword) or false
positives (a keyword firing on unrelated queries) once used for real.

## Bundled default_config.yaml's vision section resynced to schema (2026-07-13)

`config/default_config.yaml`'s `vision:` section still had the original
ONNX/Xenova captioning fields from Milestone 5's first pass, never updated
when `vision/model.py` moved to the moondream2/MiniCPM-V-2.6 GGUF approach
(see the Milestone 5 entry above and `docs/TODO.md`). This was harmless at
runtime — Pydantic silently ignores unknown yaml keys and falls back to
`VisionSettings`' schema defaults for anything missing — but left the
bundled yaml actively misleading for anyone who opened it expecting to
tune the vision model. Resynced to the current GGUF-based fields
(`repo_id`, `model_filename`, `mmproj_filename`, `local_model_path`,
`local_mmproj_path`, `n_ctx`, `n_gpu_layers`, `max_tokens`,
`caption_prompt`) plus the new `trigger_keywords`, `ocr_enabled`,
`ocr_min_confidence`, `tesseract_cmd`. No schema change — `config/schema.py`
was already correct; only the bundled yaml was stale.

## Milestone 7: Aura morphs to trace a target box, not a generic overlay layer (2026-07-13)

**Original framing (mine, going in):** a general-purpose overlay renderer
drawing arbitrary shapes (circles, arrows, bounding boxes, labels) on top
of screen content, separate from the Aura edge glow.

**Actual design (settled through direct back-and-forth):** narrower and
more specific to Iris's existing visual language. Instead of a new
overlay layer, the existing full-screen ambient edge glow
(`GlowAuraRenderer`, Milestone 6) itself morphs so its outline traces the
bounding box of a single target UI element, then eases back to the
full-screen edge. One box at a time — not a general shape/annotation
system. This reuses Milestone 6's blur-based glow technique and its
`QVariantAnimation` cross-fade pattern, rather than introducing a second,
unrelated rendering system alongside it.

**Why this over the generic-overlay framing:** it's a smaller, more
coherent addition — no new renderer, no new visual language, just an
extension of the geometry Aura already draws. It also reads more clearly
to the end user: the glow they already associate with Iris's state is the
same thing pointing at what it's talking about, instead of a second,
separate visual element appearing on top.

**Structured output, not a regex-parsed single line:** `VisionModel.locate()`
uses `LlamaGrammar.from_json_schema()` (built into `llama-cpp-python`,
same dependency `vision/model.py` and `llm/engine.py` already use — no
new library) to force `{"found": bool, "label": str, "x": int, "y": int,
"w": int, "h": int}` at the token level. Considered a simpler
regex-parsed free-text approach first (matches this project's usual
"smallest thing that works" bias — see the Milestone 4/6 entries above),
but a single box is exactly the shape structured output is good at, and
the grammar dependency was already one import away — not the larger lift
a multi-shape JSON schema would have been.

**Percent coordinates, not pixels:** the vision model reasons over its
own resized input image, not the caller's actual screen resolution — it
has no way to reliably output real pixel coordinates. `x`/`y`/`w`/`h` are
0-100 (percent of the screenshot); `main.py` will convert to real pixels
using the known screen-capture geometry when wiring this into the
renderer (Part B.3).

**`found=False` and a parse failure are one case, not two:** originally
asked "what happens on a malformed/missing annotation" expecting to
distinguish a genuine parse glitch from the model correctly finding
nothing — settled on treating both identically (red `AuraState.ERROR` +
asking the user if they want to try again), since from the user's
perspective both are "nothing to show right now," and a single failure
path is simpler to build and reason about than two.

**Grammar constrains structure, not semantics** — worth restating since
it's easy to over-trust: llama.cpp's grammar guarantees the *shape* of
the output (valid JSON matching the schema), not that the box is
*correct* (e.g. it could still report `found=True` with a box that
doesn't correspond to anything real, or numerically valid but nonsensical
bounds like `x=90, w=50`). Part B.3's wiring needs to sanity-check/clamp
the box before using it, not treat `locate()`'s output as ground truth
just because it parsed.

**Verification status:** `VisionModel.locate()`'s grammar-building and
JSON-parsing logic is covered by 6 real tests in
`tests/test_vision_model.py` (mocked `Llama.create_chat_completion`, not
mocked parsing logic — same pattern as `test_llm_engine.py`). **Not yet
run against the real model** — this sandbox has no GPU/model weights to
actually run MiniCPM-V-2.6 inference. Real-hardware verification needs to
confirm the grammar produces not just valid JSON but *sensible* boxes on
real screenshots, per the "constrains structure, not semantics" note
above.

**Part B.2 (renderer generalization) reuses Milestone 6's mask/animation
machinery rather than introducing new ones:** `_build_blurred_mask()`
already took a canvas size and drew 4 edge bands into it; it now also
takes a `target_rect` and draws those same 4 bands along *that* rect's
edges instead of the canvas's own, so it's the exact same function doing
the exact same drawing — just parameterized. The geometry morph
(`_rect_animation`) mirrors the existing color cross-fade
(`_animation`/`TRANSITION_MS`) almost exactly, down to reusing
`QEasingCurve.Type.OutCubic`, deliberately, rather than inventing a new
animation shape for what's conceptually the same "ease from A to B"
pattern. The two animations are kept as separate `QVariantAnimation`
instances with separate durations (`BOX_TRANSITION_MS` = 600ms vs.
`TRANSITION_MS` = 500ms) since color and geometry are orthogonal and
there's no reason a state change and a target-box change should be
forced to animate at the same speed.

**Clamping lives in the renderer, not the caller:** `_clamp_target_rect()`
sits inside `GlowAuraRenderer` rather than being pushed onto whatever
calls `show_target_box()` (Part B.3's `main.py` wiring, eventually).
Reasoning: `AuraRenderer.show_target_box()`'s contract is explicitly
"coordinates are untrusted" (see its docstring in `base.py`) — the
renderer is the one thing that actually knows the legal bounds (its own
`_screen_rect`, `MIN_BOX_SIZE_PX`), so it's the natural place to enforce
them, and it means *any* future caller (not just Part B.3's `locate()`
wiring) gets the same safety for free rather than having to remember to
clamp before calling.

## Milestone 7 Part B.3: locate() bypasses normal LLM generation entirely (2026-07-14)

A locate-triggered query ("where is the save button") does not also go
through `llm_engine.generate()` -- `_locate_worker()` in `main.py` calls
`VisionModel.locate()` and, on success, replies with a short templated
"Found it -- {label}." rather than handing the vision model's answer to
the text LLM to rephrase or comment on. Reasoning: `locate()`'s
structured output already *is* the answer to "where is X" (a box to
point at) -- running it through the text LLM afterward would add a
second real-time CPU-bound inference pass (Qwen2.5, on top of the
already-slow MiniCPM-V call) for a response that's mostly decorative.
Revisit if user feedback wants a more conversational reply than the
template -- `on_target_found()`/`on_target_not_found()` are the only two
places that would need to change.

**A separate `locate_trigger_keywords` setting, not reuse of
`trigger_keywords`.** The existing `vision.trigger_keywords` decides "does
this query care about the screen at all" (gating caption+OCR context
folded into the LLM prompt). Part B.3 needed a different, more specific
question: "does this query want Iris to point at something." Reusing
`trigger_keywords` for both would mean every screen-context query (e.g.
"what's on my screen") would also attempt `locate()`, which doesn't make
sense for a query with no specific target. The two lists are checked
independently in `on_transcribed()` -- a locate match doesn't require also
matching `trigger_keywords`, and vice versa.

**Percent→pixel conversion uses the *captured* monitor's geometry, not
Aura's screen geometry.** `ScreenCapture` gained a `monitor_geometry`
property (mss's own `left`/`top`/`width`/`height` dict for whatever
`capture()` last grabbed) specifically so `_locate_worker()` converts
`locate()`'s percent output using the region that was *actually*
screenshotted -- not `GlowAuraRenderer`'s own `_screen_rect` (primary
screen only, see its Milestone 6 note), which could be a different
monitor or a different combined-virtual-screen size depending on
`vision.monitor_index`. `GlowAuraRenderer.show_target_box()`'s existing
clamping (Part B.2) is the safety net if the two disagree on a
multi-monitor setup -- the box lands somewhere legal on Aura's actual
overlay screen even if not pixel-perfect on a different monitor than the
one that was captured. Properly aligning Aura's overlay to match
`vision.monitor_index` (rather than always the primary screen) is a
known follow-up, not solved here -- see `docs/TODO.md`.

**Fixed vision config drift while here.** `config/schema.py` /
`config/default_config.yaml`'s `vision.repo_id` / `model_filename` /
`mmproj_filename` / `n_ctx` still had moondream2's values from before
`vision/model.py`'s MiniCPM-V-2.6 rework -- a real, pre-existing bug
(not introduced this session) that this session's testing surfaced
while double-checking `VisionModel`'s config path for the `locate()`
wiring. Left as `vision/model.py`'s own `DEFAULT_*` constants describe
it (openbmb/MiniCPM-V-2_6-gguf, ggml-model-Q4_K_M.gguf,
mmproj-model-f16.gguf, n_ctx=4096) -- see that module's docstring for
why pairing the wrong weights with `MiniCPMv26ChatHandler` fails
*silently* (garbage embeddings, not an error) rather than loudly, which
is what made this worth fixing immediately rather than just noting for
later.

## Milestone 7 Part B.3 follow-up: reject degenerate zero-area locate() boxes (2026-07-14)

Real bug, caught from an actual test run on real hardware (Premiere Pro,
dual-monitor, MiniCPM-V-2.6): `locate()` returned `found=True` with
`x=0, y=0, w=0, h=0` for "point to the export button on my left
screen" -- the model's own answer was meaningless (no real box), but
`GlowAuraRenderer.show_target_box()`'s existing clamping (Part B.2,
which only guards against off-screen/undersized coordinates) inflated
that zero-area box up to `MIN_BOX_SIZE_PX` and rendered a small box in
the top-left corner as if it were a real detection -- see the screenshot
in the session log. `_locate_worker()` in `main.py` now rejects
`found=True` responses where `w <= 0 or h <= 0` and routes them through
the same `report_not_found()` path as `found=False` -- a degenerate box
is not a real answer, whatever the `found` flag says. This is exactly
the caller-side sanity-checking `locate()`'s own docstring already calls
for ("the model could still report a `found=True` box that doesn't
actually correspond to anything real... Milestone 7's wiring should
clamp/sanity-check the box before using it") -- just not yet done when
Part B.3 first shipped.

Whether the *underlying* zero-area answer was a genuine model failure
(plausible -- MiniCPM-V-2.6 was asked to reason about a spatial concept,
"my left screen," inside a full 3840x1080 combined-virtual-screen
capture split into 8 tiled slices, which is a much harder grounding task
than locating something within a single monitor's screenshot) is a
separate, real-hardware tuning question, not something this fix
addresses -- see `docs/TODO.md`'s note on `vision.monitor_index`.
