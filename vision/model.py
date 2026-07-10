"""Image captioning via ONNX Runtime (Milestone 5, part 2).

Turns a screenshot into a short text description that `main.py` can fold
into the LLM prompt (see `docs/DECISIONS.md`). Knows nothing about screen
capture, Aura, or the LLM -- takes a PIL image in, returns a caption string
out, the same "one thing in, one thing out" shape as `llm/engine.py` and
`speech/transcriber.py`.

Model weights (an ONNX export of a ViT encoder + GPT-2 decoder image
captioning model) are pulled from Hugging Face Hub on first use via
`huggingface_hub.hf_hub_download` and cached locally after that -- the
same one-time-download-then-offline pattern as `llm/engine.py` and
`speech/transcriber.py`. See `docs/DECISIONS.md` for why the plain
(non-merged, no past-key-value cache) decoder export was chosen, and why
`tokenizers` is used here instead of pulling in the full `transformers`
package just for id<->text conversion.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import onnxruntime as ort
from huggingface_hub import hf_hub_download
from PIL import Image
from tokenizers import Tokenizer

logger = logging.getLogger(__name__)

# Xenova's ready-made ONNX export of nlpconnect/vit-gpt2-image-captioning.
# Chosen (like Milestone 4's LLM default) for "small and working" over
# "best possible caption quality" -- see docs/DECISIONS.md.
DEFAULT_REPO_ID = "Xenova/vit-gpt2-image-captioning"
DEFAULT_ENCODER_FILENAME = "onnx/encoder_model.onnx"
DEFAULT_DECODER_FILENAME = "onnx/decoder_model.onnx"
DEFAULT_TOKENIZER_FILENAME = "tokenizer.json"

DEFAULT_MAX_NEW_TOKENS = 30
_IMAGE_SIZE = 224  # ViT encoder's expected square input size.

# From the source model's preprocessor_config.json -- hardcoded here rather
# than pulling in the full `transformers` image-processor stack for one
# resize+normalize step (same "avoid a heavy dependency for a small job"
# reasoning as picking `tokenizers` over `transformers` below).
_IMAGE_MEAN = 0.5
_IMAGE_STD = 0.5

# GPT-2's <|endoftext|> token doubles as both BOS and EOS for this model.
_BOS_TOKEN_ID = 50256
_EOS_TOKEN_ID = 50256


def preprocess_image(image: Image.Image) -> np.ndarray:
    """Resize/normalize an image into the encoder's expected input tensor.

    Returns a `[1, 3, 224, 224]` float32 array, channel order matching the
    source model's `preprocessor_config.json` (RGB, mean/std 0.5). Pulled
    out as a free function (rather than a method) so it can be unit tested
    without needing the ONNX model files on disk -- see `tests/test_vision_model.py`.
    """
    resized = image.convert("RGB").resize((_IMAGE_SIZE, _IMAGE_SIZE), Image.BICUBIC)
    array = np.asarray(resized, dtype=np.float32) / 255.0
    array = (array - _IMAGE_MEAN) / _IMAGE_STD
    array = array.transpose(2, 0, 1)  # HWC -> CHW
    return array[np.newaxis, ...]  # add batch dim


class VisionModel:
    """Wraps ONNX Runtime encoder + decoder sessions for image captioning.

    Stateless across calls, same as `LLMEngine` -- one `describe()` call in,
    one caption out, no memory of previous screenshots.
    """

    def __init__(
        self,
        repo_id: str = DEFAULT_REPO_ID,
        encoder_filename: str = DEFAULT_ENCODER_FILENAME,
        decoder_filename: str = DEFAULT_DECODER_FILENAME,
        tokenizer_filename: str = DEFAULT_TOKENIZER_FILENAME,
        local_model_dir: str | None = None,
        providers: list[str] | None = None,
    ) -> None:
        session_providers = providers or ["CPUExecutionProvider"]

        try:
            if local_model_dir:
                base = Path(local_model_dir)
                encoder_path = base / encoder_filename
                decoder_path = base / decoder_filename
                tokenizer_path = base / tokenizer_filename
                logger.info("Loading local vision model from '%s'...", base)
            else:
                logger.info(
                    "Loading vision model '%s' -- first run downloads ONNX "
                    "weights + tokenizer from Hugging Face Hub, cached after "
                    "that...",
                    repo_id,
                )
                encoder_path = hf_hub_download(repo_id, encoder_filename)
                decoder_path = hf_hub_download(repo_id, decoder_filename)
                tokenizer_path = hf_hub_download(repo_id, tokenizer_filename)

            self._encoder = ort.InferenceSession(str(encoder_path), providers=session_providers)
            self._decoder = ort.InferenceSession(str(decoder_path), providers=session_providers)
            self._tokenizer = Tokenizer.from_file(str(tokenizer_path))
        except Exception as exc:
            target = local_model_dir or repo_id
            raise RuntimeError(
                f"Could not load vision model ('{target}'). This requires an "
                "internet connection the first time it's used to download "
                f"model weights. Underlying error: {exc}"
            ) from exc

        logger.info("Vision model ready (providers=%s).", session_providers)

    def describe(self, image: Image.Image, max_new_tokens: int = DEFAULT_MAX_NEW_TOKENS) -> str:
        """Caption a single image. Returns "" if generation produces nothing.

        Runs the encoder once, then greedily decodes token-by-token with the
        non-merged decoder (each step recomputes over the full sequence so
        far -- no past-key-value cache). Captions are short (a few dozen
        tokens), so the recompute cost is negligible for a single interactive
        query -- see `docs/DECISIONS.md` for why the simpler/slower decoder
        export was chosen over the merged one.
        """
        pixel_values = preprocess_image(image)
        (encoder_hidden_states,) = self._encoder.run(None, {"pixel_values": pixel_values})

        input_ids = np.array([[_BOS_TOKEN_ID]], dtype=np.int64)
        for _ in range(max_new_tokens):
            logits = self._decoder.run(
                None,
                {
                    "input_ids": input_ids,
                    "encoder_hidden_states": encoder_hidden_states,
                },
            )[0]
            next_token = int(np.argmax(logits[0, -1, :]))
            if next_token == _EOS_TOKEN_ID:
                break
            input_ids = np.concatenate(
                [input_ids, np.array([[next_token]], dtype=np.int64)], axis=1
            )

        generated_ids = input_ids[0, 1:].tolist()  # drop the leading BOS
        text = self._tokenizer.decode(generated_ids, skip_special_tokens=True).strip()

        logger.debug("Vision model generated caption: %r", text)
        return text
