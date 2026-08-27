import pytest

from app.documents.storage import FileValidationError, save_upload_bytes, validate_upload


def test_validate_upload_accepts_pdf():
    result = validate_upload("sample.pdf", "application/pdf", 1024, max_upload_mb=20)

    assert result.kind == "pdf"
    assert result.extension == ".pdf"
    assert result.mime_type == "application/pdf"


def test_validate_upload_rejects_unsupported_extension():
    with pytest.raises(FileValidationError, match="Unsupported file type"):
        validate_upload("notes.txt", "text/plain", 32, max_upload_mb=20)


def test_validate_upload_rejects_large_file():
    with pytest.raises(FileValidationError, match="File is larger than"):
        validate_upload("large.pdf", "application/pdf", 21 * 1024 * 1024, max_upload_mb=20)


def test_save_upload_bytes_writes_unique_file(tmp_path):
    stored = save_upload_bytes(
        filename="form.pdf",
        content_type="application/pdf",
        content=b"%PDF sample",
        storage_dir=tmp_path,
        max_upload_mb=20,
    )

    assert stored.original_filename == "form.pdf"
    assert stored.kind == "pdf"
    assert stored.file_path.exists()
    assert stored.file_path.read_bytes() == b"%PDF sample"
    assert stored.stored_filename.endswith(".pdf")
