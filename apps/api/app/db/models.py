from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Boolean, CheckConstraint, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class DocumentStatus(StrEnum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    OCR_PROCESSING = "ocr_processing"
    EMBEDDING = "embedding"
    INDEXED = "indexed"
    DEFERRED_OCR = "deferred_ocr"
    FAILED = "failed"


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, name="document_status", values_callable=lambda enum: [item.value for item in enum]),
        nullable=False,
        default=DocumentStatus.UPLOADED,
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    processing_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processing_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processing_duration_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    pages: Mapped[list["Page"]] = relationship(back_populates="document", cascade="all, delete-orphan")
    chunks: Mapped[list["Chunk"]] = relationship(back_populates="document", cascade="all, delete-orphan")
    summaries: Mapped[list["DocumentSummary"]] = relationship(back_populates="document", cascade="all, delete-orphan")
    study_questions: Mapped[list["StudyQuestion"]] = relationship(back_populates="document", cascade="all, delete-orphan")
    page_images: Mapped[list["PageImage"]] = relationship(back_populates="document", cascade="all, delete-orphan")
    document_tables: Mapped[list["DocumentTable"]] = relationship(back_populates="document", cascade="all, delete-orphan")
    document_table_cells: Mapped[list["DocumentTableCell"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )


class Page(Base):
    __tablename__ = "pages"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    width: Mapped[float | None]
    height: Mapped[float | None]
    text_source: Mapped[str] = mapped_column(String(20), nullable=False, default="native")
    ocr_engine: Mapped[str | None] = mapped_column(String(100))
    ocr_confidence: Mapped[float | None] = mapped_column(Float)
    ocr_duration_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    document: Mapped[Document] = relationship(back_populates="pages")
    chunks: Mapped[list["Chunk"]] = relationship(back_populates="page", cascade="all, delete-orphan")
    page_images: Mapped[list["PageImage"]] = relationship(back_populates="page", cascade="all, delete-orphan")
    document_tables: Mapped[list["DocumentTable"]] = relationship(back_populates="page", cascade="all, delete-orphan")
    document_table_cells: Mapped[list["DocumentTableCell"]] = relationship(
        back_populates="page",
        cascade="all, delete-orphan",
    )


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    page_id: Mapped[str] = mapped_column(ForeignKey("pages.id", ondelete="CASCADE"), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    token_estimate: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    layout: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    document: Mapped[Document] = relationship(back_populates="chunks")
    page: Mapped[Page] = relationship(back_populates="chunks")
    embedding: Mapped["ChunkEmbedding"] = relationship(back_populates="chunk", cascade="all, delete-orphan")


class ChunkEmbedding(Base):
    __tablename__ = "chunk_embeddings"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    chunk_id: Mapped[str] = mapped_column(ForeignKey("chunks.id", ondelete="CASCADE"), nullable=False, unique=True)
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(384), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    chunk: Mapped[Chunk] = relationship(back_populates="embedding")


class PageImage(Base):
    __tablename__ = "page_images"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    page_id: Mapped[str] = mapped_column(ForeignKey("pages.id", ondelete="CASCADE"), nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    render_dpi: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[float | None]
    height: Mapped[float | None]
    media_type: Mapped[str] = mapped_column(String(100), nullable=False, default="image/png")
    checksum: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    document: Mapped[Document] = relationship(back_populates="page_images")
    page: Mapped[Page] = relationship(back_populates="page_images")


class DocumentTable(Base):
    __tablename__ = "document_tables"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    page_id: Mapped[str] = mapped_column(ForeignKey("pages.id", ondelete="CASCADE"), nullable=False)
    source_chunk_id: Mapped[str | None] = mapped_column(ForeignKey("chunks.id", ondelete="SET NULL"))
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    table_index: Mapped[int] = mapped_column(Integer, nullable=False)
    caption: Mapped[str | None] = mapped_column(Text)
    extraction_confidence: Mapped[str] = mapped_column(String(20), nullable=False, default="low")
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    column_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB().with_variant(JSON, "sqlite"),
        nullable=False,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    document: Mapped[Document] = relationship(back_populates="document_tables")
    page: Mapped[Page] = relationship(back_populates="document_tables")
    source_chunk: Mapped[Chunk | None] = relationship()
    cells: Mapped[list["DocumentTableCell"]] = relationship(back_populates="table", cascade="all, delete-orphan")


class DocumentTableCell(Base):
    __tablename__ = "document_table_cells"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    table_id: Mapped[str] = mapped_column(ForeignKey("document_tables.id", ondelete="CASCADE"), nullable=False)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    page_id: Mapped[str] = mapped_column(ForeignKey("pages.id", ondelete="CASCADE"), nullable=False)
    source_chunk_id: Mapped[str | None] = mapped_column(ForeignKey("chunks.id", ondelete="SET NULL"))
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    row_index: Mapped[int] = mapped_column(Integer, nullable=False)
    column_index: Mapped[int] = mapped_column(Integer, nullable=False)
    column_label: Mapped[str | None] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    table: Mapped[DocumentTable] = relationship(back_populates="cells")
    document: Mapped[Document] = relationship(back_populates="document_table_cells")
    page: Mapped[Page] = relationship(back_populates="document_table_cells")
    source_chunk: Mapped[Chunk | None] = relationship()


class DocumentSummary(Base):
    __tablename__ = "document_summaries"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    citations: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    document: Mapped[Document] = relationship(back_populates="summaries")


class StudyQuestion(Base):
    __tablename__ = "study_questions"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    expected_answer: Mapped[str] = mapped_column(Text, nullable=False)
    citations: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    document: Mapped[Document] = relationship(back_populates="study_questions")
    answers: Mapped[list["StudyAnswer"]] = relationship(back_populates="question", cascade="all, delete-orphan")


class StudyAnswer(Base):
    __tablename__ = "study_answers"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    question_id: Mapped[str] = mapped_column(ForeignKey("study_questions.id", ondelete="CASCADE"), nullable=False)
    answer_text: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    feedback: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    question: Mapped[StudyQuestion] = relationship(back_populates="answers")


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    retrieval_results: Mapped[list["RetrievalResult"]] = relationship(back_populates="question", cascade="all, delete-orphan")


class RetrievalResult(Base):
    __tablename__ = "retrieval_results"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    chunk_id: Mapped[str] = mapped_column(ForeignKey("chunks.id", ondelete="CASCADE"), nullable=False)
    score: Mapped[float] = mapped_column(nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    question: Mapped[Question] = relationship(back_populates="retrieval_results")
    chunk: Mapped[Chunk] = relationship()


class EvalRun(Base):
    __tablename__ = "eval_runs"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class DocumentEvalSuite(Base):
    __tablename__ = "document_eval_suites"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class DocumentEvalCase(Base):
    __tablename__ = "document_eval_cases"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    suite_id: Mapped[str] = mapped_column(ForeignKey("document_eval_suites.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"), index=True)
    document_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    expected_outcome: Mapped[str] = mapped_column(String(30), nullable=False)
    facts: Mapped[list[dict[str, Any]]] = mapped_column(JSONB().with_variant(JSON, "sqlite"), default=list, nullable=False)
    anchors: Mapped[list[dict[str, Any]]] = mapped_column(JSONB().with_variant(JSON, "sqlite"), default=list, nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSONB().with_variant(JSON, "sqlite"), default=list, nullable=False)
    review_rationale: Mapped[str] = mapped_column(Text, default="", nullable=False)
    review_state: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    content_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_page_hashes: Mapped[dict[str, str]] = mapped_column(JSONB().with_variant(JSON, "sqlite"), default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class DocumentEvalRun(Base):
    __tablename__ = "document_eval_runs"
    __table_args__ = (CheckConstraint("active_slot IS NULL OR active_slot = 1", name="document_eval_active_slot"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    suite_id: Mapped[str | None] = mapped_column(ForeignKey("document_eval_suites.id", ondelete="SET NULL"), index=True)
    suite_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB().with_variant(JSON, "sqlite"), default=dict, nullable=False)
    case_snapshots: Mapped[list[dict[str, Any]]] = mapped_column(JSONB().with_variant(JSON, "sqlite"), default=list, nullable=False)
    pipeline_config: Mapped[dict[str, Any]] = mapped_column(JSONB().with_variant(JSON, "sqlite"), default=dict, nullable=False)
    measurements: Mapped[dict[str, Any]] = mapped_column(JSONB().with_variant(JSON, "sqlite"), default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="queued", nullable=False)
    active_slot: Mapped[int | None] = mapped_column(Integer, unique=True)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    total_cases: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed_cases: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DocumentEvalResult(Base):
    __tablename__ = "document_eval_results"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    run_id: Mapped[str] = mapped_column(ForeignKey("document_eval_runs.id", ondelete="CASCADE"), index=True)
    case_id_snapshot: Mapped[str] = mapped_column(String(36), nullable=False)
    case_version: Mapped[int] = mapped_column(Integer, nullable=False)
    case_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB().with_variant(JSON, "sqlite"), default=dict, nullable=False)
    execution_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB().with_variant(JSON, "sqlite"), default=dict, nullable=False)
    measurements: Mapped[dict[str, Any]] = mapped_column(JSONB().with_variant(JSON, "sqlite"), default=dict, nullable=False)
    failure_reasons: Mapped[list[str]] = mapped_column(JSONB().with_variant(JSON, "sqlite"), default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    duration_ms: Mapped[float] = mapped_column(Float, nullable=False)
    human_assessment: Mapped[str | None] = mapped_column(String(20))
    assessment_note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    assessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
