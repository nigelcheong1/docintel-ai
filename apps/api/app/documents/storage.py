from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from app.documents.schemas import DocumentKind

ALLOWED_EXTENSIONS: dict[str, tuple[DocumentKind, str]] = {
    ".pdf": ("pdf", "application/pdf"),
    ".png": ("image", "image/png"),
    ".jpg": ("image", "image/jpeg"),
    ".jpeg": ("image", "image/jpeg"),
}


class FileValidationError(ValueError):
    pass


class UploadTooLargeError(FileValidationError):
    pass


class AsyncReadable(Protocol):
    async def read(self, size: int = -1) -> bytes:
        ...


@dataclass(frozen=True)
class UploadValidation:
    kind: DocumentKind
    mime_type: str
    extension: str
    size_bytes: int


@dataclass(frozen=True)
class StoredUpload:
    original_filename: str
    stored_filename: str
    mime_type: str
    file_path: Path
    kind: DocumentKind
    size_bytes: int


def validate_upload(filename: str, content_type: str | None, size_bytes: int, max_upload_mb: int) -> UploadValidation:
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise FileValidationError("Unsupported file type. Upload a PDF, PNG, JPG, or JPEG document.")

    max_bytes = max_upload_mb * 1024 * 1024
    if size_bytes > max_bytes:
        raise UploadTooLargeError(f"File is larger than {max_upload_mb} MB.")

    kind, default_mime = ALLOWED_EXTENSIONS[extension]
    return UploadValidation(
        kind=kind,
        mime_type=content_type or default_mime,
        extension=extension,
        size_bytes=size_bytes,
    )


def save_upload_bytes(
    filename: str,
    content_type: str | None,
    content: bytes,
    storage_dir: Path,
    max_upload_mb: int,
) -> StoredUpload:
    validation = validate_upload(filename, content_type, len(content), max_upload_mb)
    storage_dir.mkdir(parents=True, exist_ok=True)
    stored_filename = f"{uuid4().hex}{validation.extension}"
    file_path = storage_dir / stored_filename
    file_path.write_bytes(content)
    return StoredUpload(
        original_filename=filename,
        stored_filename=stored_filename,
        mime_type=validation.mime_type,
        file_path=file_path,
        kind=validation.kind,
        size_bytes=validation.size_bytes,
    )


async def save_upload_stream(
    filename: str,
    content_type: str | None,
    stream: AsyncReadable,
    storage_dir: Path,
    max_upload_mb: int,
    chunk_size: int = 1024 * 1024,
) -> StoredUpload:
    validation = validate_upload(filename, content_type, 0, max_upload_mb)
    max_bytes = max_upload_mb * 1024 * 1024
    storage_dir.mkdir(parents=True, exist_ok=True)
    stored_filename = f"{uuid4().hex}{validation.extension}"
    file_path = storage_dir / stored_filename
    size_bytes = 0

    try:
        with file_path.open("wb") as destination:
            while chunk := await stream.read(chunk_size):
                size_bytes += len(chunk)
                if size_bytes > max_bytes:
                    raise UploadTooLargeError(f"File is larger than {max_upload_mb} MB.")
                destination.write(chunk)
    except Exception:
        file_path.unlink(missing_ok=True)
        raise

    return StoredUpload(
        original_filename=filename,
        stored_filename=stored_filename,
        mime_type=validation.mime_type,
        file_path=file_path,
        kind=validation.kind,
        size_bytes=size_bytes,
    )
