from hashlib import sha256

import fitz
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.config import Settings, get_settings
from app.db.models import Base, Document, Page, PageImage
from app.db.session import get_db
from app.main import create_app
import app.documents.router as document_router


def test_preview_persists_rendered_metadata_without_rendering_twice(tmp_path, monkeypatch):
    path = tmp_path / "preview.pdf"
    with fitz.open() as pdf:
        pdf.new_page(width=72, height=144)
        pdf.save(path)

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=[Document.__table__, Page.__table__, PageImage.__table__])
    with Session(engine) as db:
        document = Document(filename="preview.pdf", stored_filename="preview.pdf", mime_type="application/pdf", file_path=str(path))
        document.pages = [Page(page_number=1, text="", width=72, height=144)]
        db.add(document)
        db.commit()
        document_id = document.id
        render_calls = []
        original_render = document_router.render_document_page_image

        def render(*args, **kwargs):
            render_calls.append(kwargs["page_number"])
            return original_render(*args, **kwargs)

        monkeypatch.setattr(document_router, "render_document_page_image", render)
        app = create_app()
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_settings] = lambda: Settings(storage_dir=tmp_path)
        response = TestClient(app).get(f"/documents/{document_id}/pages/1/image")

        assert response.status_code == 200
        assert render_calls == [1]
        record = db.scalar(select(PageImage))
        assert record is not None
        assert record.checksum == sha256(response.content).hexdigest()
        assert (record.width, record.height) == (150, 300)
