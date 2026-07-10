# Iris

A fully local, voice-first AI desktop copilot for Windows.

Iris runs entirely on your machine — no cloud inference, no paid APIs, no
subscriptions, no external AI providers. You say "Hey Iris," ask a question
about what's on your screen, and Iris captures a screenshot, reasons about
it with local models, and guides you visually and by voice.

## Status

🚧 Early development. Milestone 5 (screen capture + vision) complete in
code; both it and Milestone 4's LLM generation are still pending
verification on real hardware with real internet access — see
[`docs/TODO.md`](docs/TODO.md). See [`docs/ROADMAP.md`](docs/ROADMAP.md)
for what's done and what's next. [`HANDOFF.md`](HANDOFF.md) has the full
current state for anyone (human or AI) picking up development.

## Core principles

- **Everything runs locally.** No cloud inference, no paid APIs, no subscriptions.
- **Offline-first.** Iris works with no internet connection.
- **Privacy by default.** No continuous screen or audio monitoring. Screenshots
  are analyzed and discarded unless you explicitly choose to keep one.
- **Modular.** Every major component (voice, vision, LLM, Aura) is swappable.

## Target hardware

Developed and tuned for:
- RTX 3070 Ti (8GB VRAM)
- Ryzen 7 5700X
- 32GB DDR4 RAM
- Windows 11

## Tech stack

Python 3.12+, PySide6, llama.cpp, Faster-Whisper, OpenWakeWord, MSS, OpenCV,
ONNX Runtime, SQLite.

## Getting started (development)

```bash
# Core dependencies only (enough to launch the app, no wake word detection)
pip install -e .

# Run
python main.py
```

To enable wake word detection ("Hey Jarvis" as a placeholder — a custom
"Hey Iris" model can be trained later at https://openwakeword.com/train and
dropped in via config with no code changes):

```bash
pip install -e ".[speech]"
python main.py
```

Say "Hey Jarvis" — Aura should transition through LISTENING (wake word
heard) → THINKING (your speech is transcribed, then a response is
generated) → back to IDLE. The response appears in the placeholder
window and is logged to the console.

**Testing without speaking:** the placeholder window has a debug text
input (on by default during development — see `debug.enabled` in config)
that simulates a full voice command. Type something and hit Enter/Send —
it drives Aura through the exact same LISTENING → THINKING → IDLE sequence
real voice input would, no microphone or speaking required.

To also enable local LLM responses (default model is a small ~1GB
`Qwen2.5-0.5B-Instruct` GGUF, downloaded and cached on first use — see
`config.yaml`'s `llm:` section to point at a different model):

```bash
pip install -e ".[speech,llm]"
python main.py
```

Without the `llm` extra installed, Iris still runs fine — voice/transcript
handling works as before, and the response window just shows a
"no LLM configured" placeholder instead of a generated reply.

To also enable screen-context awareness (Iris looks at a screenshot and
folds a short caption into the prompt): install the `vision` extra, **and**
turn it on in config — it's opt-in and off by default even with the extra
installed, since it involves reading your screen (see `docs/DECISIONS.md`):

```bash
pip install -e ".[speech,llm,vision]"
```

```yaml
# In your config.yaml (see config/paths.py for its location):
vision:
  enabled: true
```

The default captioning model (~250MB, ONNX) downloads and caches on first
use, same as the LLM. Without `vision.enabled: true`, Iris never captures
the screen at all, regardless of which extras are installed.

Everything, including the Windows-only and dev-tooling extras:

```bash
pip install -e ".[speech,llm,vision,windows,dev]"
```

## Project structure

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for a full breakdown of
the folder structure and how modules relate to each other.

## Contributing

Iris is built incrementally, one milestone at a time, with documentation
kept in sync at every step. See `docs/DECISIONS.md` for the reasoning
behind key architectural choices.
