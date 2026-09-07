from app.db.models import Chunk, Document, DocumentStatus, Page, StudyQuestion
from app.study.service import build_document_summary, build_study_questions, score_study_answer


def make_document(filename: str = "paper.pdf") -> Document:
    document = Document(
        id="document-1",
        filename=filename,
        stored_filename=filename,
        mime_type="application/pdf",
        file_path=f"/tmp/{filename}",
        status=DocumentStatus.INDEXED,
    )
    page_one = Page(
        id="page-1",
        document_id=document.id,
        page_number=1,
        text="Abstract This paper introduces DocIntel AI for cited document intelligence.",
        width=612,
        height=792,
    )
    page_two = Page(
        id="page-2",
        document_id=document.id,
        page_number=2,
        text="Method The system uses OCR, page chunks, embeddings, and extractive citations.",
        width=612,
        height=792,
    )
    page_three = Page(
        id="page-3",
        document_id=document.id,
        page_number=3,
        text="Results Experiments show faster search and stronger citation coverage.",
        width=612,
        height=792,
    )
    document.pages = [page_one, page_two, page_three]
    document.chunks = [
        Chunk(
            id="chunk-abstract",
            document_id=document.id,
            page_id=page_one.id,
            page=page_one,
            chunk_index=0,
            text="ABSTRACT This paper introduces DocIntel AI for cited document intelligence.",
            token_estimate=10,
            layout={"section_heading": "ABSTRACT"},
        ),
        Chunk(
            id="chunk-method",
            document_id=document.id,
            page_id=page_two.id,
            page=page_two,
            chunk_index=1,
            text="METHOD The system uses OCR, page chunks, embeddings, and extractive citations.",
            token_estimate=11,
            layout={"section_heading": "METHOD"},
        ),
        Chunk(
            id="chunk-results",
            document_id=document.id,
            page_id=page_three.id,
            page=page_three,
            chunk_index=2,
            text="RESULTS Experiments show faster search and stronger citation coverage.",
            token_estimate=9,
            layout={"section_heading": "RESULTS"},
        ),
    ]
    return document


def test_build_document_summary_uses_cited_high_signal_chunks():
    summary = build_document_summary(make_document())

    assert "DocIntel AI" in summary.content
    assert "OCR, page chunks, embeddings" in summary.content
    assert [citation["chunk_id"] for citation in summary.citations] == ["chunk-abstract", "chunk-method", "chunk-results"]
    assert summary.citations[0]["page_image_url"] == "/documents/document-1/pages/1/image"
    assert summary.citations[0]["document_page_url"] == "/documents/document-1?page=1&chunk=chunk-abstract"


def test_build_study_questions_reuses_document_aware_answers_and_deduplicates():
    questions = build_study_questions(make_document(), count=5)

    question_texts = [question.question for question in questions]
    assert "What is this document about?" in question_texts
    assert "What methods are used?" in question_texts
    assert len(question_texts) == len(set(question_texts))
    methods = next(question for question in questions if question.question == "What methods are used?")
    assert "OCR, page chunks, embeddings" in methods.expected_answer
    assert methods.citations[0]["chunk_id"] == "chunk-method"


def test_score_study_answer_rewards_overlap_with_expected_answer():
    question = StudyQuestion(
        id="question-1",
        document_id="document-1",
        question="What methods are used?",
        expected_answer="The system uses OCR, page chunks, embeddings, and extractive citations.",
        citations=[],
    )

    strong = score_study_answer(question, "It uses OCR, page chunks, embeddings, and extractive citations.")
    weak = score_study_answer(question, "It is about invoices and payments.")

    assert strong.score >= 0.75
    assert "Strong" in strong.feedback
    assert weak.score < 0.4
    assert "Needs work" in weak.feedback
