"""Verbatim on-screen text extraction via Tesseract OCR (Milestone 5 addendum).

Complements `vision/model.py`'s scene description with actual, literal
text recognition -- moondream2 can tell you "a video editor is open with a
timeline", but it can't reliably transcribe the exact text in a menu,
error dialog, or code editor. Tesseract can. `main.py` calls both and
folds each into the prompt separately, since they answer different
questions ("what is this" vs "what does it literally say").

Requires the actual Tesseract OCR engine installed as a system binary --
`pytesseract` is only a thin Python wrapper around the `tesseract` CLI,
not a bundled OCR implementation. See `docs/DECISIONS.md` for install
links. If Tesseract isn't found, `OCRReader.__init__` raises the same way
`VisionModel`/`LLMEngine` do, so `main.py` can catch it and continue
without OCR rather than crashing the whole app.
"""

from __future__ import annotations

import logging
import shutil

import pytesseract
from PIL import Image

logger = logging.getLogger(__name__)

DEFAULT_MIN_CONFIDENCE = 60.0


class OCRReader:
    """Wraps `pytesseract` for extracting literal text from a screenshot.

    Stateless across calls, same shape as `VisionModel.describe()` --
    one image in, one text blob out.
    """

    def __init__(
        self,
        tesseract_cmd: str | None = None,
        min_confidence: float = DEFAULT_MIN_CONFIDENCE,
    ) -> None:
        self._min_confidence = min_confidence

        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
        elif not shutil.which(pytesseract.pytesseract.tesseract_cmd):
            # No explicit path given and the default "tesseract" isn't on
            # PATH either -- fail loudly and early (during __init__, same
            # as a bad HF repo_id in VisionModel/LLMEngine) rather than
            # letting every describe() call fail silently later.
            raise RuntimeError(
                "Tesseract OCR engine not found. pytesseract is only a "
                "wrapper -- install the actual Tesseract binary (e.g. "
                "https://github.com/UB-Mannheim/tesseract/wiki on "
                "Windows) and either add it to PATH or set "
                "vision.tesseract_cmd to its full exe path in config.yaml."
            )

        logger.info("OCR reader ready (tesseract_cmd=%s).", pytesseract.pytesseract.tesseract_cmd)

    def read(self, image: Image.Image) -> str:
        """Extract text from a screenshot, filtering out low-confidence words.

        Uses `image_to_data` (not the simpler `image_to_string`) so each
        word's confidence score can be checked individually -- screenshots
        often have UI chrome/icons that OCR misreads with low confidence,
        and including those tokens verbatim would be worse than dropping
        them.
        """
        data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)

        words: list[str] = []
        for text, conf in zip(data["text"], data["conf"]):
            stripped = text.strip()
            if not stripped:
                continue
            try:
                confidence = float(conf)
            except (TypeError, ValueError):
                continue
            if confidence < self._min_confidence:
                continue
            words.append(stripped)

        result = " ".join(words)
        logger.debug("OCR extracted %d chars from %d confident words.", len(result), len(words))
        return result
