# HANDOFF.md

<<<<<<< HEAD
**Last updated:** 2026-07-15
**Milestones completed:** 1 through 6 ✅. Milestone 7 (Visual Guidance) is
in progress: Parts B.1, B.2, and B.3 are done, B.4 remains. See
`docs/ROADMAP.md` for full milestone history and `docs/TODO.md` for the
part-by-part breakdown.
=======
**Last updated:** 2026-07-14
**Milestones completed:** 1 through 6 ✅ — plus a targeted vision-gating
fix, and Milestone 7 (Visual Guidance) is now in progress: Parts B.1 and
B.2 done, B.3 and B.4 remaining. See `docs/ROADMAP.md` for full milestone
history and `docs/TODO.md` for the part-by-part breakdown.
>>>>>>> e2362707338d13541ed6704fe96c939f88592a87

---

## Summary of work completed since the last HANDOFF.md update

<<<<<<< HEAD
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
=======
Two sessions since this file was last written:

**Session 1 (2026-07-13) — Part B.1: vision model structured output.**
`VisionModel.locate(image, target)` added to `vision/model.py`:
grammar-constrained (via `LlamaGrammar.from_json_schema`) to always
return `{"found": bool, "label": str, "x": int, "y": int, "w": int,
"h": int}`, coordinates as percent of the screenshot (0-100), not pixels.
`found=False` and a genuine parse failure are treated identically by
design — both mean "nothing to point at." Two pre-existing dead test
files (`tests/test_vision_model.py`, `tests/test_ocr.py` — both
importing functions that no longer exist after earlier reworks) were
also fixed in passing, with 11 new real tests between them. Full detail
in `docs/TODO.md`'s Milestone 7 section and `docs/DECISIONS.md`.

**Session 2 (2026-07-14) — Part B.2: generalize `GlowAuraRenderer` to
trace an arbitrary rectangle.** Picked up mid-implementation from a
session that got cut off before the renderer itself (only helper-level
scaffolding had landed, and some of it — the `base.py` interface
methods, the `GlowAuraRenderer` class methods themselves — hadn't
actually been saved despite being narrated as done). Completed for real
this session:

- `aura/renderer/base.py` — `show_target_box(x, y, w, h)` /
  `clear_target_box()` added to the `AuraRenderer` abstract interface,
  with the untrusted-coordinates contract documented on
  `show_target_box`.
- `aura/renderer/null_renderer.py`, `aura/controller.py` — log-only /
  passthrough implementations completing the interface contract.
- `aura/renderer/glow_renderer.py` — `_build_blurred_mask()` generalized
  to take a `target_rect` and draw its 4 seed bands along that rect's
  edges instead of always the canvas's; `_AuraOverlayWidget` gained
  `_target_rect` + `set_target_rect()` with a rect-aware mask cache;
  `GlowAuraRenderer` gained a `_screen_rect` "home" rect, a second
  `QVariantAnimation` (`_rect_animation`, 600ms, separate from the color
  fade's 500ms) morphing between the screen edge and a target box, the
  public `show_target_box()`/`clear_target_box()` methods, and
  `_clamp_target_rect()` to defensively clamp untrusted `(x, y, w, h)`
  to stay on-screen at a legal minimum size.
- Verified for real via `QT_QPA_PLATFORM=offscreen` (this sandbox has no
  display) — a real `QApplication` + `GlowAuraRenderer`, real
  `AuraController` calls, the real 600ms animation pumped through the Qt
  event loop, and actual painted mask pixels read back afterward (glow
  band alpha 94 at the target box's edge vs. alpha 0 at its center,
  confirming the band traces the box and not the screen). Also verified
  the out-of-bounds clamp and that `clear_target_box()` returns exactly
  to the screen rect.
- Along the way, found and fixed two literal unresolved `git` merge
  conflict markers (`<<<<<<< HEAD` / `=======` / `>>>>>>>`) baked into
  the *committed* `docs/TODO.md` and `docs/DECISIONS.md` — left over from
  a prior "resolve merge conflicts" commit that didn't actually resolve
  them. Both sides of each conflict were real, non-overlapping content,
  so the fix was just removing the marker lines.

## Files modified (2026-07-14 session)

- `aura/renderer/base.py` — new abstract methods.
- `aura/renderer/null_renderer.py` — new no-op implementations.
- `aura/renderer/glow_renderer.py` — the actual Part B.2 work (see above).
- `docs/TODO.md`, `docs/DECISIONS.md` — conflict markers removed, Part
  B.2 marked done with real verification details, a decision entry added
  for the clamping-lives-in-the-renderer choice.
- `HANDOFF.md` — this file.

## Important implementation details

- **Geometry (target box) and color (`AuraState`) are orthogonal.** They
  animate on separate `QVariantAnimation` instances with separate
  durations and can change independently — calling `show_target_box()`
  never touches the current `AuraState`, and `set_state()` never touches
  the current target rect.
- **Clamping happens in `GlowAuraRenderer`, not the caller.** Part B.3's
  `main.py` wiring will call `show_target_box()` with whatever
  `VisionModel.locate()` returns (converted from percent to pixels) —
  the renderer, not the caller, is what actually knows the legal screen
  bounds, so it's the one place that enforces them. See
  `docs/DECISIONS.md` for the full reasoning.
- **`MIN_BOX_SIZE_PX` (56px, `2 * SEED_BAND_PX + 20`) is not yet tuned
  against a real display** — reasoned about from the seed-band width,
  not measured. Worth a look on real hardware once Part B.3 is wired up
  and target boxes are coming from real vision-model output instead of
  test coordinates.

## Known issues / not yet verified

- **Part B.2 has only been verified offscreen (Xvfb/`QT_QPA_PLATFORM=
  offscreen`), never on a real display.** The animation, clamping, and
  mask-rebuild-on-rect-change logic are confirmed correct via real Qt
  rendering and pixel inspection, but a real monitor pass (does the morph
  actually look smooth, is `BOX_TRANSITION_MS`/`MIN_BOX_SIZE_PX` sized
  right visually) hasn't happened.
- **Vision gating (Milestone 6.5 fix) still hasn't been verified on real
  hardware either** — carried over from before Part B.1, still open.
- All previously-open items in `docs/TODO.md`'s "Loose ends" section
  remain open — startup timing, `tests/` coverage for
  `voice/`/`speech/`/`llm/`/`aura/`, silence-detection tuning, etc. Note
  `aura/` specifically still has zero `pytest` coverage — Part B.2's
  verification this session was a real, hands-on offscreen script, not a
  committed test file; worth turning into an actual `tests/test_aura_*.py`
  at some point (needs `PySide6` + `pytest-qt` or an offscreen fixture in
  the test environment, which the existing `tests/` suite doesn't set up
  yet). See `docs/TODO.md` directly rather than duplicating that list
  here.
>>>>>>> e2362707338d13541ed6704fe96c939f88592a87

## Current project status

Milestones 1–6 are code-complete and verified on real hardware. Milestone
<<<<<<< HEAD
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
=======
7 (Visual Guidance): Part B.1 (vision model structured output) and Part
B.2 (renderer generalization) are code-complete and verified for real in
this sandbox (offscreen Qt rendering / mocked `Llama` respectively — see
each part's entry in `docs/TODO.md`), but neither has run against real
hardware/real model weights yet. Part B.3 (wiring `main.py`'s query flow
to `VisionModel.locate()` and `AuraController.show_target_box()`/
`clear_target_box()`) and Part B.4 (reverting to the full-screen edge on
next-query or cursor-dwell) have not been started.

## Next milestone

**Milestone 7, Part B.3 — Wiring.** `found=True` → convert `locate()`'s
percent coordinates to real screen pixels (using the known
screen-capture geometry) → `AuraController.show_target_box(x, y, w, h)`.
`found=False` / parse failure → `AuraState.ERROR` (already red, already
wired) + a reply asking the user if they want to try again — both
collapse into the same path, per the Milestone 7 design decision. This
is the piece that actually calls `VisionModel.locate()` from `main.py`
for the first time; nothing calls it yet.

After B.3: **Part B.4 — Reverting to full-screen edges.** Two triggers:
(1) the next query comes in, (2) the cursor dwells inside the target box
for ~4 seconds (matches the existing breathing-pulse period — needs a
`QTimer` polling `QCursor.pos()` against the box rect, or an event
filter).
>>>>>>> e2362707338d13541ed6704fe96c939f88592a87

## Ready-to-copy prompt for the next session

```
Continue development of Iris, a fully local AI desktop copilot for Windows.

Before writing any code:
1. Read HANDOFF.md (this file)
2. Read every file inside /docs
3. Understand the current project state

Milestones 1-6 are done and verified on real hardware. Milestone 7
<<<<<<< HEAD
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

=======
(Visual Guidance) is in progress: Part B.1 (vision model structured
output, VisionModel.locate()) and Part B.2 (GlowAuraRenderer generalized
to morph between the full screen edge and a target box) are both
code-complete and verified for real in this sandbox, but neither has run
against real hardware yet.

Start with Part B.3 -- Wiring, as scoped in docs/TODO.md's Milestone 7
section:
  1. In main.py, after a vision-gated query comes back with screen
     context, call VisionModel.locate(image, target) with the relevant
     target description.
  2. found=True -> convert locate()'s percent (0-100) coordinates to
     real screen pixels using the known screen-capture geometry, then
     call AuraController.show_target_box(x, y, w, h).
  3. found=False or a parse failure -> AuraState.ERROR (already wired)
     + a text reply asking the user if they want to try again. Both
     cases share this one path, per the Milestone 7 design decision in
     docs/DECISIONS.md -- do not build a separate "broken" vs "empty"
     branch.
  4. Confirm the whole flow end-to-end as best this sandbox allows (real
     Llama calls can be mocked the same way tests/test_vision_model.py
     already does; the renderer side can be verified offscreen the same
     way Part B.2 was -- see docs/TODO.md for the exact approach), then
     flag plainly what still needs a real-hardware pass.

Once B.3 is confirmed, move to Part B.4 -- reverting to the full-screen
edge on the next query or a ~4s cursor dwell inside the target box.

>>>>>>> e2362707338d13541ed6704fe96c939f88592a87
Work incrementally, in small parts (not all at once -- confirm progress
with me between parts). Do not begin implementing anything beyond
Milestone 7's scope. Do not write fake/mock-only "it imports" tests --
verify things for real wherever this sandbox allows, and say plainly
<<<<<<< HEAD
when something genuinely can't be. End the session by updating
HANDOFF.md and docs/TODO.md, and only docs/ROADMAP.md /
docs/ARCHITECTURE.md / docs/DECISIONS.md / README.md if something
actually changed.
=======
when something genuinely can't be (e.g. real model weights, a real
display, real hardware). End the session by updating HANDOFF.md and
docs/TODO.md, and only docs/ROADMAP.md / docs/ARCHITECTURE.md /
docs/DECISIONS.md / README.md if something actually changed.
>>>>>>> e2362707338d13541ed6704fe96c939f88592a87
```
