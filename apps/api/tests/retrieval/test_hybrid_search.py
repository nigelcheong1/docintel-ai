import pytest

from app.db.models import Chunk, Document, DocumentStatus, Page
from app.retrieval.search import SearchHit, hybrid_search_chunks, lexical_search_chunks

pytestmark = pytest.mark.integration


def add_chunked_document(db_session):
    document = Document(
        filename="contract.pdf",
        stored_filename="contract.pdf",
        mime_type="application/pdf",
        file_path="/tmp/contract.pdf",
        status=DocumentStatus.INDEXED,
    )
    page = Page(
        document=document,
        page_number=1,
        text="Payment deadline is September 30. Confidentiality obligations continue after termination.",
        width=612,
        height=792,
    )
    payment = Chunk(
        document=document,
        page=page,
        chunk_index=0,
        text="Payment deadline is September 30 and total due is RM 1,200.",
        token_estimate=10,
        layout={"section_heading": "PAYMENT TERMS"},
    )
    obligations = Chunk(
        document=document,
        page=page,
        chunk_index=1,
        text="Confidentiality obligations continue after termination.",
        token_estimate=6,
        layout={"section_heading": "OBLIGATIONS"},
    )
    db_session.add_all([document, page, payment, obligations])
    db_session.commit()
    return document, payment, obligations


def test_lexical_search_returns_matching_chunks_without_embeddings(db_session):
    document, payment, _obligations = add_chunked_document(db_session)

    hits = lexical_search_chunks(db_session, "payment deadline", top_k=2, document_id=document.id)

    assert [hit.chunk_id for hit in hits] == [payment.id]
    assert hits[0].ranking_signals["lexical_score"] == 1.0
    assert hits[0].source_score == 1.0
    assert hits[0].section_heading == "PAYMENT TERMS"


def test_hybrid_search_merges_vector_and_lexical_candidates(db_session):
    document, payment, obligations = add_chunked_document(db_session)

    def vector_search(_db, _embedding, _top_k, _document_id):
        return [
            SearchHit(
                chunk_id=obligations.id,
                document_id=document.id,
                document_filename=document.filename,
                page_number=1,
                chunk_index=1,
                text=obligations.text,
                score=0.77,
                source_score=0.77,
                ranking_signals={},
                section_heading="OBLIGATIONS",
            ),
            SearchHit(
                chunk_id=payment.id,
                document_id=document.id,
                document_filename=document.filename,
                page_number=1,
                chunk_index=0,
                text=payment.text,
                score=0.7,
                source_score=0.7,
                ranking_signals={},
                section_heading="PAYMENT TERMS",
            ),
        ]

    hits, mode = hybrid_search_chunks(
        db_session,
        [0.1, 0.2],
        "payment deadline",
        top_k=4,
        document_id=document.id,
        vector_search=vector_search,
    )

    assert mode.mode == "hybrid"
    assert sorted(hit.chunk_id for hit in hits) == sorted([payment.id, obligations.id])
    merged_payment = next(hit for hit in hits if hit.chunk_id == payment.id)
    assert merged_payment.ranking_signals["vector_score"] == 0.7
    assert merged_payment.ranking_signals["lexical_score"] == 1.0
    assert merged_payment.source_score == 1.0


def test_hybrid_search_falls_back_to_lexical_when_vector_search_fails(db_session):
    document, payment, _obligations = add_chunked_document(db_session)

    def failing_vector_search(_db, _embedding, _top_k, _document_id):
        raise RuntimeError("pgvector extension is unavailable")

    hits, mode = hybrid_search_chunks(
        db_session,
        [0.1, 0.2],
        "payment deadline",
        top_k=4,
        document_id=document.id,
        vector_search=failing_vector_search,
    )

    assert mode.mode == "lexical"
    assert mode.fallback_reason == "pgvector extension is unavailable"
    assert [hit.chunk_id for hit in hits] == [payment.id]


def test_lexical_search_returns_empty_when_session_cannot_execute():
    assert lexical_search_chunks(object(), "payment deadline", top_k=2) == []
