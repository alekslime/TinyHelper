"""Tests for `vision/ocr.py`, added 2026-07-11 alongside the moondream2
vision model swap (see docs/DECISIONS.md).

`pytesseract` is only a wrapper around a system-level Tesseract install,
so `extract_text()` must fail loudly and helpfully when that binary isn't
found -- covered here without mocking, since a missing/wrong path is a
real thing this test can reproduce directly. Iris's own confidence-
filtering logic is covered separately with a mocked `pytesseract.image_to_data`,
so it doesn't depend on Tesseract's actual recognition accuracy.
"""

from __future__ import annotations

import shutil

import pytest
import pytesseract
from PIL import Image

from vision.ocr import extract_text


@pytest.fixture(autouse=True)
def _restore_tesseract_cmd():
    """`pytesseract.pytesseract.tesseract_cmd` is process-global state --
    without resetting it after each test, a fake path set by one test
    (e.g. the missing-binary test below) would leak into every later
    test in this file, including the real end-to-end one.
    """
    original = pytesseract.pytesseract.tesseract_cmd
    yield
    pytesseract.pytesseract.tesseract_cmd = original


def test_raises_runtime_error_when_tesseract_binary_missing() -> None:
    image = Image.new("RGB", (32, 32), color=(255, 255, 255))

    with pytest.raises(RuntimeError, match="Tesseract OCR engine not found"):
        extract_text(image, tesseract_cmd="/definitely/not/a/real/tesseract/binary")


def test_real_tesseract_extracts_rendered_text() -> None:
    # This sandbox happens to have the real Tesseract binary installed, so
    # this exercises the actual OCR engine end-to-end rather than a mock,
    # unlike everything else in this file. Skips cleanly on a machine
    # without Tesseract, since this is a real-engine smoke test, not a
    # test of Iris's own logic (that's covered below).
    if shutil.which("tesseract") is None:
        pytest.skip("tesseract binary not installed in this environment")

    from PIL import ImageDraw, ImageFont

    image = Image.new("RGB", (300, 60), color=(255, 255, 255))
    draw = ImageDraw.Draw(image)
    try:
        # PIL's default bitmap font is too small/blurry for Tesseract to
        # read reliably -- a real TrueType font at a larger size is needed
        # for a stable result. DejaVu Sans is Linux-only; fall back to the
        # default font (best-effort) elsewhere rather than failing the test.
        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28
        )
    except OSError:
        font = ImageFont.load_default()
    draw.text((10, 10), "Hello Iris", fill=(0, 0, 0), font=font)

    result = extract_text(image, min_confidence=0)

    assert "Iris" in result


def test_filters_out_words_below_confidence_threshold(monkeypatch) -> None:
    monkeypatch.setattr(
        pytesseract,
        "image_to_data",
        lambda *args, **kwargs: {
            "text": ["Hello", "blurry", "Iris", ""],
            "conf": ["95", "12", "88", "-1"],
        },
    )

    result = extract_text(Image.new("RGB", (8, 8)), min_confidence=60)

    assert result == "Hello Iris"


def test_returns_empty_string_when_nothing_above_confidence(monkeypatch) -> None:
    monkeypatch.setattr(
        pytesseract,
        "image_to_data",
        lambda *args, **kwargs: {"text": ["blurry", "noise"], "conf": ["10", "5"]},
    )

    result = extract_text(Image.new("RGB", (8, 8)), min_confidence=60)

    assert result == ""


def test_sets_tesseract_cmd_when_provided(monkeypatch) -> None:
    captured = {}

    def fake_image_to_data(*args, **kwargs):
        captured["tesseract_cmd"] = pytesseract.pytesseract.tesseract_cmd
        return {"text": [], "conf": []}

    monkeypatch.setattr(pytesseract, "image_to_data", fake_image_to_data)

    extract_text(Image.new("RGB", (8, 8)), tesseract_cmd="/custom/path/tesseract")

    assert captured["tesseract_cmd"] == "/custom/path/tesseract"
