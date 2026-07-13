# HANDOFF.md

**Last updated:** 2026-07-14
**Milestones completed:** 1 through 6 ✅ — plus a targeted vision-gating
fix, and Milestone 7 (Visual Guidance) is now in progress: Parts B.1 and
B.2 done, B.3 and B.4 remaining. See `docs/ROADMAP.md` for full milestone
history and `docs/TODO.md` for the part-by-part breakdown.

---

## Summary of work completed since the last HANDOFF.md update

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

## Current project status

Milestones 1–6 are code-complete and verified on real hardware. Milestone
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

## Ready-to-copy prompt for the next session

```
Continue development of Iris, a fully local AI desktop copilot for Windows.

Before writing any code:
1. Read HANDOFF.md (this file)
2. Read every file inside /docs
3. Understand the current project state

Milestones 1-6 are done and verified on real hardware. Milestone 7
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

Work incrementally, in small parts (not all at once -- confirm progress
with me between parts). Do not begin implementing anything beyond
Milestone 7's scope. Do not write fake/mock-only "it imports" tests --
verify things for real wherever this sandbox allows, and say plainly
when something genuinely can't be (e.g. real model weights, a real
display, real hardware). End the session by updating HANDOFF.md and
docs/TODO.md, and only docs/ROADMAP.md / docs/ARCHITECTURE.md /
docs/DECISIONS.md / README.md if something actually changed.
```
