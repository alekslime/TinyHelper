"""Standalone vision pipeline diagnostic for Iris.

Run this directly (not through main.py) to isolate three things at once:
  1. What ScreenCapture actually grabs (saved full-res, so you can eyeball it)
  2. What the image looks like once shrunk to ~378x378 -- roughly what
     moondream2's vision encoder actually "sees" internally, since it's a
     single-tile encoder with no adaptive slicing (unlike MiniCPM-V).
  3. What VisionModel.describe() says about each of the above.

Drop this file in the TinyHelper repo root and run:
    python test_vision.py
Output images land next to this script so you can open them and compare
by eye against what the model claims to see.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Standalone scripts don't get main.py's setup_logging() -- without this,
# vision/model.py's own "Loading vision model 'repo/file'..." line (which
# tells you for certain which weights actually loaded) is silently
# swallowed, since the root logger defaults to WARNING.
logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")

from PIL import Image

from vision.capture import ScreenCapture
from vision.model import VisionModel


def main() -> None:
    print("Capturing full screen...")
    capture = ScreenCapture(monitor_index=0)
    full = capture.capture()
    full_path = Path("debug_full.png")
    full.save(full_path)
    print(f"  Saved: {full_path.resolve()} (size={full.size})")

    print("Shrinking to 378x378 (approximating what moondream2 actually sees)...")
    shrunk = full.resize((378, 378), Image.LANCZOS)
    shrunk_path = Path("debug_shrunk_378.png")
    shrunk.save(shrunk_path)
    print(f"  Saved: {shrunk_path.resolve()}")
    print("  >>> Open this file yourself first. If YOU can't read the text")
    print("      in it, the model definitely can't either -- that's a")
    print("      resolution limit, not a bug.")

    print("\nLoading vision model (moondream2)...")
    vm = VisionModel(n_gpu_layers=0)

    print("\nDescribing full-resolution capture...")
    caption_full = vm.describe(full)
    print(f"  Caption: {caption_full!r}")

    print("\nDescribing the same image after manual 378x378 shrink...")
    caption_shrunk = vm.describe(shrunk)
    print(f"  Caption: {caption_shrunk!r}")

    print("\nDone. Compare debug_shrunk_378.png by eye against both captions.")


if __name__ == "__main__":
    main()