"""Screen understanding via `MiniCPM-V-2.6` (Milestone 5, rework 2026-07-13
part 4 -- reverted to MiniCPM-V-2.6 after confirming moondream2's
single-tile 378x378 encoder can't resolve dense screen/code text; the
laptop target accepts slower CPU-only inference in exchange for actually
usable scene descriptions).

Turns a screenshot into a short text description that `main.py` can fold
into the LLM prompt (see `docs/DECISIONS.md`). Knows nothing about screen
capture, Aura, or the LLM -- takes a PIL image in, returns a description
string out, the same "one thing in, one thing out" shape as `llm/engine.py`
and `speech/transcriber.py`.

**Why MiniCPM-V-2.6, not moondream2:** moondream2 (~1.8B) is a single-tile
encoder -- it squashes the whole screenshot down to 378x378 before
"reading" it, which destroys legibility of anything but the coarsest
screen content (a 1920x1080 code editor becomes unreadable mush at that
resolution). MiniCPM-V-2.6 is an 8B model (SigLip-400M vision encoder +
Qwen2-7B) with adaptive image slicing, built specifically for
document/UI/OCR-heavy understanding, and benchmarks meaningfully above
moondream2's weight class on exactly this kind of task. The cost is size:
~5.7GB total (text model + mmproj) vs moondream2's ~3.75GB, and
significantly slower per-query generation on CPU (~40s+ per screenshot
on the i7-6820HQ laptop target) -- accepted tradeoff for "actually tell
me what's on my screen" over speed.

Loaded via `llama-cpp-python`'s built-in `MiniCPMv26ChatHandler` -- no
new heavy dependency beyond what `llm/engine.py` already needs. Weights
are pulled from `openbmb/MiniCPM-V-2_6-gguf` on Hugging Face Hub via
`Llama.from_pretrained()` / `MiniCPMv26ChatHandler.from_pretrained()` on
first use and cached locally after that, same download-once pattern as
`llm/engine.py`.

IMPORTANT: the chat handler class must match the model family actually
being loaded -- `MiniCPMv26ChatHandler` builds MiniCPM-V's own chat
template and expects its own vision-projector output shape. Pointing a
different model's GGUF weights at the wrong handler (e.g. moondream2
weights through `MiniCPMv26ChatHandler`, or vice versa) silently produces
garbage image embeddings and hallucinated, image-unrelated output -- it
will not raise an error, it will just be wrong. (This is exactly what
happened during the 2026-07-13 moondream2 experiment on this repo -- see
git history.)
"""

from __future__ import annotations

import base64
import io
import logging

from llama_cpp import Llama
from llama_cpp.llama_chat_format import MiniCPMv26ChatHandler
from PIL import Image

logger = logging.getLogger(__name__)

# Official openbmb GGUF conversion -- verified to contain exactly these
# two files (no glob needed).
DEFAULT_REPO_ID = "openbmb/MiniCPM-V-2_6-gguf"
DEFAULT_MODEL_FILENAME = "ggml-model-Q4_K_M.gguf"
DEFAULT_MMPROJ_FILENAME = "mmproj-model-f16.gguf"

# MiniCPM-V's own docs use -c 4096 for image + prompt; moondream2 got by
# with 2048, but MiniCPM's larger vision encoder needs the extra room.
DEFAULT_N_CTX = 4096
# NOTE: defaults to CPU (0), not -1. The mmproj/image-embedding path
# inside llama-cpp-python's chat handler has its own, less-configurable
# GPU flag separate from this `n_gpu_layers` value. Combined with the
# main LLM's VRAM usage, there usually isn't spare VRAM for this model
# too on a 4GB card anyway -- see docs/DECISIONS.md before changing.
DEFAULT_N_GPU_LAYERS = 0
DEFAULT_MAX_TOKENS = 256
DEFAULT_SYSTEM_PROMPT = "You are an assistant who perfectly describes images."
DEFAULT_CAPTION_PROMPT = (
    "Describe what's on this screen concisely, focusing on any visible "
    "application windows, UI elements, and what the user appears to be doing."
)


def _image_to_data_uri(image: Image.Image) -> str:
    """Encode a PIL image as a `data:image/jpeg;base64,...` URI.

    `MiniCPMv26ChatHandler` (like other llama-cpp-python multimodal chat
    handlers) accepts images as data URIs inside an `image_url` content
    block.
    """
    if image.mode != "RGB":
        image = image.convert("RGB")
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


class VisionModel:
    """Wraps a llama.cpp `Llama` instance + `MiniCPMv26ChatHandler` for
    image-grounded chat completion.

    Stateless across calls, same as `LLMEngine` -- one `describe()` call
    in, one description out, no memory of previous screenshots.
    """

    def __init__(
        self,
        repo_id: str = DEFAULT_REPO_ID,
        model_filename: str = DEFAULT_MODEL_FILENAME,
        mmproj_filename: str = DEFAULT_MMPROJ_FILENAME,
        local_model_path: str | None = None,
        local_mmproj_path: str | None = None,
        n_ctx: int = DEFAULT_N_CTX,
        n_gpu_layers: int = DEFAULT_N_GPU_LAYERS,
    ) -> None:
        try:
            if local_model_path:
                if not local_mmproj_path:
                    raise ValueError(
                        "local_mmproj_path is required when local_model_path is set."
                    )
                logger.info(
                    "Loading local vision model from '%s' (mmproj='%s', n_ctx=%d)...",
                    local_model_path,
                    local_mmproj_path,
                    n_ctx,
                )
                chat_handler = MiniCPMv26ChatHandler(
                    clip_model_path=local_mmproj_path, verbose=False
                )
                self._model = Llama(
                    model_path=local_model_path,
                    chat_handler=chat_handler,
                    n_ctx=n_ctx,
                    n_gpu_layers=n_gpu_layers,
                    verbose=False,
                )
            else:
                logger.info(
                    "Loading vision model '%s/%s' (n_ctx=%d) -- first run "
                    "downloads GGUF weights (~5.7GB total) from Hugging Face "
                    "Hub, cached after that...",
                    repo_id,
                    model_filename,
                    n_ctx,
                )
                chat_handler = MiniCPMv26ChatHandler.from_pretrained(
                    repo_id=repo_id,
                    filename=mmproj_filename,
                    verbose=False,
                )
                self._model = Llama.from_pretrained(
                    repo_id=repo_id,
                    filename=model_filename,
                    chat_handler=chat_handler,
                    n_ctx=n_ctx,
                    n_gpu_layers=n_gpu_layers,
                    verbose=False,
                )
        except Exception as exc:
            target = local_model_path or f"{repo_id}/{model_filename}"
            raise RuntimeError(
                f"Could not load vision model ('{target}'). This requires an "
                "internet connection the first time it's used to download "
                f"model weights. Underlying error: {exc}"
            ) from exc

        logger.info("Vision model ready.")

    def describe(
        self,
        image: Image.Image,
        prompt: str = DEFAULT_CAPTION_PROMPT,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> str:
        """Describe a single screenshot. Returns "" if generation produces nothing.

        Unlike moondream2 (single user-only turn), MiniCPM-V's own
        documented usage includes a system message -- kept here to match
        the model's expected/tested chat shape.
        """
        data_uri = _image_to_data_uri(image)
        messages = [
            {"role": "system", "content": DEFAULT_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": data_uri}},
                    {"type": "text", "text": prompt},
                ],
            },
        ]
        # Low temperature on purpose: this is a grounded "what's actually
        # there" description, not creative writing. Left at the library
        # default (higher, more random), two calls on the same screenshot
        # can produce meaningfully different captions -- including
        # confident-sounding hallucinated details -- which makes the
        # output impossible to trust or debug.
        result = self._model.create_chat_completion(
            messages=messages, max_tokens=max_tokens, temperature=0.1
        )
        content = result["choices"][0]["message"]["content"]
        text = content.strip() if content else ""

        logger.debug("Vision model generated %d chars: %r", len(text), text)
        return text