from __future__ import annotations

import csv
import shutil
import subprocess
import tempfile
import time
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from PIL import Image, ImageFilter, ImageOps


class OcrUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True)
class OcrPageResult:
    text: str
    confidence: float | None
    engine_name: str
    duration_ms: int


class OcrProvider(Protocol):
    engine_name: str

    def is_available(self) -> bool:
        ...

    def ocr_image(self, image: Image.Image, *, language: str) -> OcrPageResult:
        ...


def _normalize_words(words: Iterable[str]) -> str:
    return " ".join(" ".join(words).split())


def _parse_confidence(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        confidence = float(value)
    except ValueError:
        return None
    return confidence if confidence >= 0 else None


def _parse_tesseract_tsv(output: str | None) -> tuple[str, float | None]:
    if not output:
        return "", None

    words: list[str] = []
    confidences: list[float] = []
    reader = csv.DictReader(output.splitlines(), delimiter="\t")
    for row in reader:
        text = (row.get("text") or "").strip()
        if not text:
            continue
        words.append(text)
        confidence = _parse_confidence(row.get("conf"))
        if confidence is not None:
            confidences.append(confidence)

    average_confidence = round(sum(confidences) / len(confidences), 2) if confidences else None
    return _normalize_words(words), average_confidence


def prepare_image_for_ocr(image: Image.Image) -> Image.Image:
    prepared = ImageOps.grayscale(image)
    prepared = ImageOps.autocontrast(prepared)

    target_min_width = 1200
    max_width = 3000
    if 0 < prepared.width < target_min_width:
        scale = min(target_min_width / prepared.width, max_width / prepared.width)
        prepared = prepared.resize(
            (int(prepared.width * scale), int(prepared.height * scale)),
            Image.Resampling.LANCZOS,
        )

    return prepared.filter(ImageFilter.SHARPEN)


class TesseractOcrProvider:
    engine_name = "tesseract"

    def __init__(self, *, enabled: bool, tesseract_cmd: str | None, timeout_seconds: int) -> None:
        self.enabled = enabled
        self.tesseract_cmd = tesseract_cmd
        self.timeout_seconds = timeout_seconds

    def _resolved_command(self) -> str | None:
        if not self.enabled:
            return None
        if self.tesseract_cmd is None:
            return shutil.which("tesseract")
        command_path = Path(self.tesseract_cmd)
        if command_path.exists():
            return str(command_path)
        return shutil.which(self.tesseract_cmd)

    def is_available(self) -> bool:
        return self._resolved_command() is not None

    def ocr_image(self, image: Image.Image, *, language: str) -> OcrPageResult:
        command = self._resolved_command()
        if command is None:
            return OcrPageResult(text="", confidence=None, engine_name="tesseract-unavailable", duration_ms=0)

        start = time.perf_counter()
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                image_path = Path(temp_dir) / "page.png"
                prepare_image_for_ocr(image).save(image_path)
                completed = subprocess.run(
                    [command, str(image_path), "stdout", "-l", language, "--psm", "6", "tsv"],
                    capture_output=True,
                    check=False,
                    encoding="utf-8",
                    errors="replace",
                    text=True,
                    timeout=self.timeout_seconds,
                )
        except (OSError, subprocess.SubprocessError):
            duration_ms = int((time.perf_counter() - start) * 1000)
            return OcrPageResult(text="", confidence=None, engine_name=self.engine_name, duration_ms=duration_ms)

        duration_ms = int((time.perf_counter() - start) * 1000)
        if completed.returncode != 0:
            return OcrPageResult(text="", confidence=None, engine_name=self.engine_name, duration_ms=duration_ms)

        text, confidence = _parse_tesseract_tsv(completed.stdout)
        return OcrPageResult(text=text, confidence=confidence, engine_name=self.engine_name, duration_ms=duration_ms)
