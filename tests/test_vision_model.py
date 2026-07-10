"""Tests for the parts of `vision/model.py` that don't require downloading
the actual ONNX model files (no Hugging Face Hub access in CI/sandboxes).

`VisionModel` itself (encoder/decoder sessions + tokenizer) is intentionally
NOT tested here -- see docs/TODO.md / HANDOFF.md "known issues" for why
that needs real hardware with Hub access. `preprocess_image` is a free
function specifically so this much can be verified without any of that.
"""

from __future__ import annotations

import numpy as np
from PIL import Image

from vision.model import preprocess_image


def test_preprocess_image_shape_and_dtype() -> None:
    image = Image.new("RGB", (640, 480), color=(100, 150, 200))

    tensor = preprocess_image(image)

    assert tensor.shape == (1, 3, 224, 224)
    assert tensor.dtype == np.float32


def test_preprocess_image_normalizes_into_expected_range() -> None:
    # A pixel value of 0 maps to (0/255 - 0.5) / 0.5 == -1.0; a pixel value
    # of 255 maps to (255/255 - 0.5) / 0.5 == 1.0. Anything outside
    # [-1.0, 1.0] would mean the normalization constants are wrong.
    image = Image.new("RGB", (10, 10), color=(0, 255, 128))

    tensor = preprocess_image(image)

    assert tensor.min() >= -1.0 - 1e-6
    assert tensor.max() <= 1.0 + 1e-6


def test_preprocess_image_converts_non_rgb_modes() -> None:
    grayscale_image = Image.new("L", (50, 50), color=128)

    tensor = preprocess_image(grayscale_image)

    assert tensor.shape == (1, 3, 224, 224)
