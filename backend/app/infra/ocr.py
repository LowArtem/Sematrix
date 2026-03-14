from __future__ import annotations

from functools import cached_property
from pathlib import Path


class OcrClientError(RuntimeError):
    """Raised when the local OCR runtime cannot extract text."""


class PaddleOcrClient:
    def __init__(self, *, language: str = "ru") -> None:
        self._language = language

    def extract_text(self, *, image_path: Path) -> str:
        if not image_path.exists():
            raise OcrClientError(f"OCR asset file not found: {image_path}")

        try:
            raw_result = self._ocr_engine.ocr(str(image_path), cls=True)
        except Exception as exc:  # pragma: no cover - depends on local OCR runtime
            raise OcrClientError(f"PaddleOCR failed for {image_path.name}: {exc}") from exc

        lines: list[str] = []
        for page in raw_result or []:
            if not isinstance(page, list):
                continue
            for item in page:
                if not isinstance(item, list) or len(item) < 2:
                    continue
                recognition = item[1]
                if not isinstance(recognition, tuple) or not recognition:
                    continue
                text = recognition[0]
                if isinstance(text, str):
                    normalized_text = text.strip()
                    if normalized_text:
                        lines.append(normalized_text)

        return "\n".join(lines)

    @cached_property
    def _ocr_engine(self):  # pragma: no cover - depends on optional runtime dependency
        try:
            from paddleocr import PaddleOCR
        except ImportError as exc:  # pragma: no cover - depends on optional runtime dependency
            raise OcrClientError("PaddleOCR is not installed in the backend runtime") from exc

        return PaddleOCR(use_angle_cls=True, lang=self._language, show_log=False)
