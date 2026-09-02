import subprocess

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


def test_tesseract_provider_uses_utf8_replacement_decoding(monkeypatch):
    captured_kwargs = {}
    expected_text = "R\u00e9sum\u00e9"

    def fake_run(args, **kwargs):
        captured_kwargs.update(kwargs)
        stdout = (
            "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
            f"5\t1\t1\t1\t1\t1\t0\t0\t10\t10\t92.5\t{expected_text}\n"
        )
        return subprocess.CompletedProcess(args, 0, stdout=stdout, stderr="")

    provider = TesseractOcrProvider(enabled=True, tesseract_cmd="tesseract", timeout_seconds=20)
    monkeypatch.setattr(provider, "_resolved_command", lambda: "tesseract")
    monkeypatch.setattr(subprocess, "run", fake_run)
    image = Image.new("RGB", (50, 20), "white")

    result = provider.ocr_image(image, language="eng")

    assert captured_kwargs["encoding"] == "utf-8"
    assert captured_kwargs["errors"] == "replace"
    assert result.text == expected_text
    assert result.confidence == 92.5


def test_tesseract_provider_treats_missing_stdout_as_empty_result(monkeypatch):
    def fake_run(args, **kwargs):
        return subprocess.CompletedProcess(args, 0, stdout=None, stderr="")

    provider = TesseractOcrProvider(enabled=True, tesseract_cmd="tesseract", timeout_seconds=20)
    monkeypatch.setattr(provider, "_resolved_command", lambda: "tesseract")
    monkeypatch.setattr(subprocess, "run", fake_run)
    image = Image.new("RGB", (50, 20), "white")

    result = provider.ocr_image(image, language="eng")

    assert result.text == ""
    assert result.confidence is None
    assert result.engine_name == "tesseract"
