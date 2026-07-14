# HANDOFF.md

**Last updated:** 2026-07-15
**Milestones completed:** 1 through 6 ✅. Milestone 7 (Visual Guidance) is
in progress: Parts B.1, B.2, and B.3 are done, B.4 remains. See
`docs/ROADMAP.md` for full milestone history and `docs/TODO.md` for the
part-by-part breakdown.

---

## Summary of work completed since the last HANDOFF.md update

**Session 3 (2026-07-15) — Part B.3: wiring.** `main.py`'s query flow now
actually calls `VisionModel.locate()` for the first time.

- A new `vision.locate_trigger_keywords` setting (`config/schema.py`,
  `config/default_config.yaml`) gates a separate path from the existing
  `trigger_keywords` (caption/OCR context gate) — see `docs/DECISIONS.md`
  for why these are two independent lists, not one reused list.
- `on_transcribed()` checks `_is_locate_query(text)` first; if matched,
  `_locate_worker()` runs on its own thread and **bypasses normal LLM
  generation entirely** — `locate()`'s structured output already is the
  answer to "where is X," so there's no second real-time inference pass
  through the text LLM. See `docs/DECISIONS.md` if that's ever worth
  revisiting for a more conversational reply.
- `_locate_worker()`: `screen_capture.capture()` →
  `vision_model.locate(image, target=text)` → converts the result's
  percent-of-screenshot coordinates to real screen pixels using the
  *actually captured* monitor's geometry → reports through a new
  `app/locate_bridge.py::LocateResultBridge` (same cross-thread
  `QObject`+`Signal` pattern as the other three `app/*_bridge.py` files).
- `found=True` → `on_target_found()` → `AuraController.show_target_box()`
  + a short reply + `AuraState.IDLE`. `found=False` / parse failure both
  collapse into `on_target_not_found()` → `AuraState.ERROR` + "I couldn't
  find that — want to try again?" — one path, not two, per the Milestone
  7 design decision.
- `vision/capture.py`: `ScreenCapture` gained a `monitor_geometry`
  property — the real geometry of whatever `capture()` last grabbed,
  needed because the percent→pixel conversion must use the region that
  was *actually* captured, not assume it matches Aura's own
  primary-screen-only overlay geometry (documented multi-monitor caveat,
  not solved this session — Part B.2's clamping is the safety net).
- **Verified for real**, with only two boundaries faked (both plainly
  documented as such, not silently glossed over): Llama (no GPU/model
  weights in this sandbox, same as Part B.1) and mss's X11 grab (this
  sandboxed container can't get a real X11/shm connection to Xvfb —
  confirmed by actually trying it first and getting a connection error,
  not assumed). Everything else in the verification is real: real
  `VisionModel.locate()` JSON parsing, the exact percent→pixel conversion
  code copied verbatim from `main.py`, a real `QObject` signal crossing a
  real background thread, and a real `GlowAuraRenderer` ending up tracing
  the exact right rect — for both the found and not-found paths.
- **Found and fixed a real, pre-existing config/code drift bug** while
  double-checking `VisionModel`'s config path: `config/schema.py` /
  `config/default_config.yaml`'s `vision.repo_id` / `model_filename` /
  `mmproj_filename` / `n_ctx` still held moondream2's values from before
  `vision/model.py`'s MiniCPM-V-2.6 rework. This wasn't introduced this
  session, but it's a live bug — `vision/model.py`'s own docstring
  explains pairing the wrong weights with `MiniCPMv26ChatHandler` fails
  *silently* (garbage embeddings, not an error), which is why it was
  fixed immediately rather than just noted. Corrected to match
  `vision/model.py`'s own `DEFAULT_*` constants.

## Files modified (2026-07-15 session)

- `main.py` — the actual Part B.3 wiring (see above).
- `app/locate_bridge.py` — new file, `LocateResultBridge`.
- `vision/capture.py` — `monitor_geometry` property.
- `config/schema.py`, `config/default_config.yaml` —
  `locate_trigger_keywords` (new), plus the moondream2→MiniCPM-V-2.6 drift
  fix (`repo_id`/`model_filename`/`mmproj_filename`/`n_ctx`).
- `docs/TODO.md`, `docs/DECISIONS.md` — Part B.3 marked done with real
  verification details; new decision entries for the LLM-bypass choice,
  the separate keyword list, the geometry-source-of-truth choice, and the
  config drift fix.
- `HANDOFF.md` — this file.

## Known issues / not yet verified

- **Part B.3 has only been verified with two documented sandbox-only
  fakes (Llama, mss's X11 grab)** — never against real hardware, a real
  microphone, or a real vision model. The percent→pixel conversion math
  and the full thread→bridge→Aura path are confirmed correct by direct
  execution; what a real `locate()` call on real screen content actually
  *finds* is not.
- **The multi-monitor geometry mismatch** between `vision.monitor_index`
  (can capture a single monitor or the combined virtual screen) and
  `GlowAuraRenderer`'s primary-screen-only overlay is a known, documented
  gap — not solved this session. On a single-monitor dev/target machine
  it won't matter; worth a real check once multi-monitor is in scope.
- **`locate_trigger_keywords`'s defaults are a first guess**, not tuned
  against real usage — worth revisiting once real voice queries are
  actually being tried against it.
- Everything already listed as open in Part B.1/B.2's entries (real
  MiniCPM-V-2.6 inference never run, `MIN_BOX_SIZE_PX` not tuned against
  a real display, etc.) is still open.
- All previously-open items in `docs/TODO.md`'s "Loose ends" section
  remain open.

## Current project status

Milestones 1–6 are code-complete and verified on real hardware. Milestone
7 (Visual Guidance): Parts B.1, B.2, and B.3 are code-complete and
verified for real in this sandbox wherever the sandbox allows (real logic
throughout, with only the unavoidable Llama/display boundaries faked and
plainly documented). None of Milestone 7 has run against real hardware
yet. Part B.4 (reverting to the full-screen edge on next-query or
cursor-dwell) has not been started.

## Next milestone

**Milestone 7, Part B.4 — Reverting to full-screen edges.** Two triggers:

1. **The next query comes in.** `on_transcribed()` already runs at the
   start of every query — call `aura.clear_target_box()` there
   unconditionally (before branching into the locate vs. LLM path), so
   any active target box always clears the moment a new query starts,
   regardless of whether the new query is itself a locate query.
2. **The cursor dwells inside the target box for ~4 seconds** (matches
   the existing breathing-pulse period). Needs a `QTimer` polling
   `QCursor.pos()` against the currently-active box rect, or an event
   filter — and needs to track "is a box currently active" and "what is
   its rect" somewhere accessible to that timer, which right now only
   `GlowAuraRenderer`/`_AuraOverlayWidget` know internally. Worth
   deciding whether `AuraController` needs a way to expose "is a target
   box active" (e.g. a property) rather than `main.py` tracking its own
   separate copy of that state.

## Ready-to-copy prompt for the next session

```
Continue development of Iris, a fully local AI desktop copilot for Windows.

Before writing any code:
1. Read HANDOFF.md (this file)
2. Read every file inside /docs
3. Understand the current project state

Milestones 1-6 are done and verified on real hardware. Milestone 7
(Visual Guidance) is in progress: Parts B.1 (VisionModel.locate()), B.2
(GlowAuraRenderer's target-box morph), and B.3 (main.py wiring: a
locate-triggered query calls locate() and morphs Aura to the result) are
all code-complete and verified for real in this sandbox -- real logic
throughout, with only the Llama/display boundaries faked (this sandbox
has no GPU/model weights or a working X11 connection to its own Xvfb).
None of it has run against real hardware yet.

Start with Part B.4 -- Reverting to full-screen edges, as scoped in
docs/TODO.md's Milestone 7 section:
  1. Trigger 1 (next query): call aura.clear_target_box() at the start
     of on_transcribed(), unconditionally, before branching into the
     locate vs. LLM generation path.
  2. Trigger 2 (cursor dwell, ~4s): needs a QTimer polling
     QCursor.pos() against the active target box's rect. Decide first
     whether AuraController should expose "is a target box currently
     active, and what's its rect" as its own small piece of state (it
     isn't tracked anywhere outside GlowAuraRenderer/_AuraOverlayWidget
     right now), rather than main.py keeping a separate shadow copy that
     could drift out of sync.
  3. Confirm the whole flow end-to-end as best this sandbox allows (see
     docs/TODO.md and the verify_target_box.py / verify_part_b3.py
     approach from the last two sessions for the offscreen-Qt pattern),
     then flag plainly what still needs a real-hardware pass.

Work incrementally, in small parts (not all at once -- confirm progress
with me between parts). Do not begin implementing anything beyond
Milestone 7's scope. Do not write fake/mock-only "it imports" tests --
verify things for real wherever this sandbox allows, and say plainly
when something genuinely can't be. End the session by updating
HANDOFF.md and docs/TODO.md, and only docs/ROADMAP.md /
docs/ARCHITECTURE.md / docs/DECISIONS.md / README.md if something
actually changed.
```
