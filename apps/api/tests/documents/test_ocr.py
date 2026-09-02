from PIL import Image

from app.documents.ocr import TesseractOcrProvider


def test_tesseract_provider_reports_unavailable_when_disabled():
    provider = TesseractOcrProvider(enabled=False, tesseract_cmd=None, timeout_seconds=20)

    assert provider.is_available() is False


def test_tesseract_provider_reports_unavailable_when_command_is_missing():
    provider = TesseractOcrProvider(enabled=True, tesseract_cmd="missing-tesseract-command", timeout_seconds=20)

    assert provider.is_available() is False


def test_tesseract_provider_does_not_run_when_unavailable():
    provider = TesseractOcrProvider(enabled=False, tesseract_cmd=None, timeout_seconds=20)
    image = Image.new("RGB", (50, 20), "white")

    result = provider.ocr_image(image, language="eng")

    assert result.text == ""
    assert result.confidence is None
    assert result.engine_name == "tesseract-unavailable"
