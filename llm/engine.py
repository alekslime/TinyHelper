"""Local LLM inference via llama.cpp (`llama-cpp-python`).

Knows nothing about voice, transcripts, or Aura — takes one piece of user
text, returns generated text. `main.py` decides when to call it and how to
route the result to Aura / the placeholder window.

Model weights are pulled from Hugging Face Hub on first use via
`Llama.from_pretrained()` and cached locally after that — the same
one-time-download-then-offline pattern as `speech/transcriber.py`'s
Faster-Whisper model. See `docs/DECISIONS.md`.
"""

from __future__ import annotations

import logging
import time

from llama_cpp import Llama

logger = logging.getLogger(__name__)

# Small instruct model chosen for fast iteration on modest dev hardware
# (does NOT need to match the RTX 3070 Ti target — see docs/DECISIONS.md
# for why, and for what to swap in for the real target hardware).
DEFAULT_REPO_ID = "Qwen/Qwen2.5-0.5B-Instruct-GGUF"
DEFAULT_FILENAME = "qwen2.5-0.5b-instruct-q4_k_m.gguf"

DEFAULT_N_CTX = 4096
DEFAULT_N_GPU_LAYERS = -1  # -1 = offload every layer to GPU
DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_TOKENS = 512
DEFAULT_SYSTEM_PROMPT = (
    "You are Iris, a concise local AI desktop copilot. Keep answers short "
    "and to the point unless the user asks for more detail."
)

# `Llama.from_pretrained()` has to list every file in the repo (to glob-match
# `filename`) before it can download anything -- a heavier Hub API call than
# a direct file download, and one real-hardware run showed it can hit a
# transient SSL handshake timeout even when the network is otherwise fine
# (a plain file download to the same host succeeded seconds later in the
# same run). Retried a few times with backoff rather than failing the whole
# app on one flaky connection attempt. See docs/DECISIONS.md.
DOWNLOAD_RETRY_ATTEMPTS = 3
DOWNLOAD_RETRY_BACKOFF_S = 2.0


class LLMEngine:
    """Wraps a llama.cpp `Llama` instance for one-shot chat completion.

    Stateless across calls — no conversation history yet (that's Milestone
    9's job). Each `generate()` call is a fresh system+user turn.
    """

    def __init__(
        self,
        repo_id: str = DEFAULT_REPO_ID,
        filename: str = DEFAULT_FILENAME,
        local_model_path: str | None = None,
        n_ctx: int = DEFAULT_N_CTX,
        n_gpu_layers: int = DEFAULT_N_GPU_LAYERS,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    ) -> None:
        self._system_prompt = system_prompt

        try:
            if local_model_path:
                logger.info(
                    "Loading local LLM from '%s' (n_ctx=%d, n_gpu_layers=%d)...",
                    local_model_path,
                    n_ctx,
                    n_gpu_layers,
                )
                self._model = Llama(
                    model_path=local_model_path,
                    n_ctx=n_ctx,
                    n_gpu_layers=n_gpu_layers,
                    verbose=False,
                )
            else:
                logger.info(
                    "Loading LLM '%s/%s' (n_ctx=%d, n_gpu_layers=%d) — first run "
                    "downloads weights from Hugging Face Hub, cached after that...",
                    repo_id,
                    filename,
                    n_ctx,
                    n_gpu_layers,
                )
                self._model = self._load_from_hub_with_retry(
                    repo_id, filename, n_ctx, n_gpu_layers
                )
        except Exception as exc:
            target = local_model_path or f"{repo_id}/{filename}"
            raise RuntimeError(
                f"Could not load LLM ('{target}'). This requires an internet "
                "connection the first time it's used to download model weights. "
                f"Underlying error: {exc}"
            ) from exc

        logger.info("LLM ready.")

    def _load_from_hub_with_retry(
        self, repo_id: str, filename: str, n_ctx: int, n_gpu_layers: int
    ) -> Llama:
        last_exc: Exception | None = None
        for attempt in range(1, DOWNLOAD_RETRY_ATTEMPTS + 1):
            try:
                return Llama.from_pretrained(
                    repo_id=repo_id,
                    filename=filename,
                    n_ctx=n_ctx,
                    n_gpu_layers=n_gpu_layers,
                    verbose=False,
                )
            except Exception as exc:  # noqa: BLE001 - deliberately broad, see retry note above
                last_exc = exc
                if attempt < DOWNLOAD_RETRY_ATTEMPTS:
                    delay = DOWNLOAD_RETRY_BACKOFF_S * attempt
                    logger.warning(
                        "LLM download/load attempt %d/%d failed (%s) — "
                        "retrying in %.0fs. This is usually a transient network "
                        "hiccup talking to Hugging Face Hub, not a real problem "
                        "with the model or your setup.",
                        attempt,
                        DOWNLOAD_RETRY_ATTEMPTS,
                        exc,
                        delay,
                    )
                    time.sleep(delay)
        assert last_exc is not None  # loop always runs >=1 time
        raise last_exc

    def generate(
        self,
        user_text: str,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
    ) -> str:
        """Generate a reply to a single user utterance.

        Returns an empty string for empty input; raises on inference
        failure (the caller decides how to handle that — see
        `voice's on_transcribed` pattern in `main.py`).
        """
        if not user_text.strip():
            return ""

        messages = [
            {"role": "system", "content": self._system_prompt},
            {"role": "user", "content": user_text},
        ]
        result = self._model.create_chat_completion(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        text = result["choices"][0]["message"]["content"].strip()

        logger.debug("LLM generated %d chars for input %r", len(text), user_text)
        return text
