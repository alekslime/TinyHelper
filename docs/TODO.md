# TODO

Granular, actionable task tracking. Coarser-grained progress lives in
`docs/ROADMAP.md`; this file is for the immediate next steps and small
loose ends.

## Immediate next steps (Milestone 2 — Wake Word Detection)

- [ ] Research OpenWakeWord model options and pick one appropriate for
      "Hey Iris" (may need a custom-trained wake word model — investigate
      feasibility vs. using a stock model + fuzzy phrase matching)
- [ ] Add `voice/` module: microphone input stream handling
- [ ] Add `voice/wake_word.py`: wake word detection wrapping OpenWakeWord
- [ ] Wire wake word detection into `main.py` → `AuraController.set_state(LISTENING)`
- [ ] Add `voice` extras group usage docs to README
- [ ] Decide on mic device selection UX (default device vs. configurable)

## Loose ends / small items

- [ ] Add `tests/` content — currently just an empty package. Add first
      unit tests for `config/settings.py` (merge logic) and
      `aura/controller.py` (state transitions) before Milestone 2 grows scope.
- [ ] Add a `LICENSE` file (MIT referenced in `pyproject.toml` but not yet present)
- [ ] Consider a `Makefile` or `justfile` for common dev commands
      (`run`, `test`, `lint`, `format`) once there's enough to script
- [ ] `NullAuraRenderer` currently has no visual feedback at all in dev —
      consider a temporary debug print/overlay so it's obvious Aura state
      is changing during Milestone 2/3 development, before real rendering exists

## Known issues

- None currently open. See `HANDOFF.md` "Known issues" for anything
  discovered during the most recent session.
