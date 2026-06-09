"""OCR axis labels from image strips."""

from __future__ import annotations

import re

import numpy as np


def ocr_axis_labels(img_array: np.ndarray) -> list[str]:
    """Extract numeric/text labels from an image strip using pytesseract.

    Returns an empty list gracefully if tesseract is unavailable.
    """
    try:
        import pytesseract
        from PIL import Image

        pil_img = Image.fromarray(img_array)
        text = pytesseract.image_to_string(
            pil_img,
            config="--psm 6 -c tessedit_char_whitelist=0123456789.,kKwWhH$JFMASONDjfmasond",
        )
        tokens = re.split(r"[\s\n]+", text.strip())
        return [t for t in tokens if t]
    except ImportError:
        return []
    except Exception:
        return []
