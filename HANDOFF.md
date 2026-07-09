# HANDOFF.md

**Last updated:** 2026-07-09
**Milestone completed:** Milestone 1 — Project Scaffolding ✅

---

## Summary of work completed

Milestone 1 is fully complete: the Iris repository was initialized, the
full folder structure created, dependency management configured, a working
config + logging system built, a minimal PySide6 application that launches
successfully, and a placeholder Aura renderer interface (structure only, no
actual rendering). All documentation files were created.

Work was done in four incremental parts within a single session:
1. Repo init, folder structure, `pyproject.toml`, `.gitignore`
2. Config system (`config/`) + logging (`utils/logger.py`) — smoke-tested
3. `main.py` entry point, minimal PySide6 window, Aura placeholder interface
   (states, abstract renderer, no-op renderer, controller) — launch-tested
4. Documentation (this file + README + docs/)

## Files created

```
iris/
├── .gitignore
├── README.md
├── pyproject.toml
├── main.py
├── app/
│   ├── __init__.py
│   └── main_window.py
├── aura/
│   ├── __init__.py
│   ├── controller.py
│   ├── states.py
│   ├── animations/__init__.py
│   ├── renderer/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   └── null_renderer.py
│   ├── shaders/__init__.py
│   └── themes/__init__.py
├── automation/__init__.py
├── config/
│   ├── __init__.py
│   ├── default_config.yaml
│   ├── paths.py
│   ├── schema.py
│   └── settings.py
├── docs/
│   ├── ARCHITECTURE.md
│   ├── DECISIONS.md
│   ├── ROADMAP.md
│   └── TODO.md
├── llm/__init__.py
├── memory/__init__.py
├── overlay/__init__.py
├── speech/__init__.py
├── tests/__init__.py
├── utils/
│   ├── __init__.py
│   └── logger.py
├── vision/__init__.py
└── voice/__init__.py
```

## Files modified

None — this was the initial scaffolding session, everything above is new.

## Dependencies added

Core (installed, in `pyproject.toml` `[project] dependencies`):
- `PySide6>=6.7.0`
- `pydantic>=2.7.0`
- `PyYAML>=6.0.1`

Optional extras (declared, **not yet installed** — will be installed as
their milestones are built):
- `speech`: `faster-whisper>=1.0.0`, `openwakeword>=0.6.0`
- `llm`: `llama-cpp-python>=0.2.90`
- `vision`: `mss>=9.0.1`, `opencv-python>=4.10.0`, `onnxruntime-gpu>=1.18.0`
- `windows`: `pywin32>=306` (Windows only)
- `dev`: `pytest`, `black`, `ruff`, `mypy`

## Important implementation details

- **Config load order:** `config/default_config.yaml` (bundled) →
  `%APPDATA%/Iris/config/config.yaml` (user, created on first run) → merged
  → validated against `AppSettings` (Pydantic). On non-Windows dev machines,
  user data falls back to a local `.iris_data/` folder (gitignored).
- **Aura decoupling:** All Aura interaction goes through
  `aura.controller.AuraController.set_state(AuraState)`. No other module
  should import `aura.renderer.*` directly. Current renderer is
  `NullAuraRenderer` — logs state changes, renders nothing. This is
  intentional (see `docs/DECISIONS.md`).
- **Logging:** `utils.logger.setup_logging(settings.logging)` must be called
  once, early, in `main.py` before any other module logs. It's idempotent
  (clears existing handlers) so safe to call again in tests.
- **App data location:** Windows → `%APPDATA%\Iris\`. Linux/macOS (dev) →
  `<repo_root>/.iris_data/` (gitignored, safe to delete anytime — it's
  regenerated on next run).

## Current folder structure

See "Files created" above — that *is* the current full structure.

## Known issues

- None blocking. One cosmetic note: launching under `QT_QPA_PLATFORM=offscreen`
  (used for testing in this sandboxed environment, which has no display)
  prints `This plugin does not support propagateSizeHints()` to stderr.
  This is expected for the offscreen Qt plugin and should not occur when
  running normally on Windows with a real display. If it does appear on
  the target Windows machine, investigate — it should not.
- `tests/` package exists but is currently empty. Flagged in `docs/TODO.md`
  as a loose end to address before Milestone 2 grows in scope.

## Testing performed

1. **Config + logging smoke test:** Loaded settings, verified `app_name`,
   `version`, `aura.theme` values, confirmed user config file was
   auto-generated at first run, confirmed logging output formatted
   correctly to console. PASS.
2. **Application launch test:** Constructed `QApplication`, `AuraController`
   with `NullAuraRenderer`, and `MainWindow` under an offscreen Qt platform
   (no display available in this dev sandbox). Verified: window becomes
   visible (`isVisible() == True`), window title reads `"Iris v0.1.0"`,
   Aura reaches `AuraState.IDLE`, and both Aura and the app shut down
   cleanly with no exceptions. PASS.
3. Both test runs' generated runtime artifacts (`.iris_data/`, `__pycache__/`)
   were deleted afterward — they are gitignored and not part of the repo.

**Not yet tested:** actual display rendering on Windows (this dev
environment has no GUI/display — only offscreen/headless testing was
possible). The next session on a real Windows machine should do a real
`python main.py` run and visually confirm the window appears.

## Current project status

Milestone 1 complete and verified (within the limits of a headless dev
sandbox). Repo is a clean, git-initialized Python project with no
uncommitted cruft (test artifacts cleaned up). Ready for Milestone 2.

## Next milestone

**Milestone 2 — Wake Word Detection.** See `docs/ROADMAP.md` for full
scope and `docs/TODO.md` for the specific next actions, including the
open research question of whether a custom-trained "Hey Iris" wake word
model is needed vs. adapting a stock OpenWakeWord model.

## Ready-to-copy prompt for the next session

```
Continue development of Iris, a fully local AI desktop copilot for Windows.

Before writing any code:
1. Read HANDOFF.md (this file)
2. Read every file inside /docs
3. Understand the current project state

Milestone 1 (project scaffolding) is complete and verified. We are now
starting Milestone 2 — Wake Word Detection, as scoped in docs/ROADMAP.md
and docs/TODO.md.

Work incrementally, in small parts (not all at once — confirm progress
with me between parts). Do not begin implementing anything beyond
Milestone 2's scope. End the session by updating HANDOFF.md and
docs/TODO.md, and only docs/ROADMAP.md / docs/ARCHITECTURE.md /
docs/DECISIONS.md / README.md if something actually changed.
```
