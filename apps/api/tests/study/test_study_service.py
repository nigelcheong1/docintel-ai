from app.db.models import Chunk, Document, DocumentStatus, Page, StudyQuestion
from app.llm.providers import AnswerEvaluationResult, GeneratedQuestionResult
from app.retrieval.search import RetrievalMode, SearchHit
from app.study.service import (
    build_document_summary,
    build_study_questions,
    generate_document_summary,
    generate_study_questions,
    score_study_answer,
)


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


class RecordingProvider:
    provider_name = "test"

    def __init__(self) -> None:
        self.summary_context = ""
        self.question_context = ""

    def summarize(self, context: str) -> str:
        self.summary_context = context
        return "Provider summary from retrieved evidence."

    def generate_questions(self, context: str, count: int) -> list[GeneratedQuestionResult]:
        self.question_context = context
        return [
            GeneratedQuestionResult(
                question="What is this document about?",
                expected_answer="Duplicate provider answer should be deduped.",
            ),
            GeneratedQuestionResult(
                question="What does the document say about export controls?",
                expected_answer="Export controls are described in retrieved evidence.",
            ),
        ][:count]

    def evaluate_answer(self, question: str, expected_answer: str, user_answer: str) -> AnswerEvaluationResult:
        return AnswerEvaluationResult(score=0.5, feedback="Provider feedback.")


class ConstantEmbeddingProvider:
    model_name = "constant-study-embedding"
    dimension = 384

    def embed_texts(self, texts):
        return [[0.1] * self.dimension for _text in texts]


def add_retrieval_only_chunk(document: Document) -> Chunk:
    page = Page(
        id="page-4",
        document_id=document.id,
        page_number=4,
        text="Appendix Document overview main topics include export controls and audit trails.",
        width=612,
        height=792,
    )
    chunk = Chunk(
        id="chunk-retrieved",
        document_id=document.id,
        page_id=page.id,
        page=page,
        chunk_index=3,
        text="APPENDIX Document overview main topics include export controls and audit trails.",
        token_estimate=11,
        layout={"section_heading": "APPENDIX"},
    )
    document.pages.append(page)
    document.chunks.append(chunk)
    return chunk


def make_postgres_document() -> Document:
    document = make_document()
    document.id = "00000000-0000-0000-0000-000000000101"
    for index, page in enumerate(document.pages, start=1):
        page.id = f"00000000-0000-0000-0000-0000000002{index:02d}"
        page.document_id = document.id
    for index, chunk in enumerate(document.chunks, start=1):
        chunk.id = f"00000000-0000-0000-0000-0000000003{index:02d}"
        chunk.document_id = document.id
        chunk.page_id = chunk.page.id
    return document


def test_build_document_summary_uses_cited_high_signal_chunks():
    summary = build_document_summary(make_document())

    assert "DocIntel AI" in summary.content
    assert "OCR, page chunks, embeddings" in summary.content
    assert [citation["chunk_id"] for citation in summary.citations] == ["chunk-abstract", "chunk-method", "chunk-results"]
    assert summary.citations[0]["page_image_url"] == "/documents/document-1/pages/1/image"
    assert summary.citations[0]["document_page_url"] == "/documents/document-1?page=1&chunk=chunk-abstract"
    assert summary.citations[0]["snippet"].startswith("ABSTRACT This paper introduces")
    assert summary.citations[0]["score"] == 1.0
    assert summary.citations[0]["source_score"] == 1.0


def test_build_document_summary_can_use_provider_with_retrieved_context():
    document = make_document()
    add_retrieval_only_chunk(document)
    provider = RecordingProvider()

    summary = build_document_summary(document, provider=provider)

    assert summary.content == "Provider summary from retrieved evidence."
    assert "export controls" in provider.summary_context
    assert summary.citations[0]["chunk_id"] == "chunk-retrieved"
    assert "export controls" in summary.citations[0]["snippet"]


def test_generate_document_summary_uses_hybrid_retrieval_hits(monkeypatch, db_session):
    document = make_postgres_document()
    db_session.add(document)
    db_session.commit()
    provider = RecordingProvider()

    def fake_hybrid_search(db, query_embedding, query, top_k, document_id, **kwargs):
        assert db is db_session
        assert query_embedding == [0.1] * 384
        assert "overview" in query
        assert top_k == 3
        assert document_id == document.id
        return [
            SearchHit(
                chunk_id="chunk-results",
                document_id=document.id,
                document_filename=document.filename,
                page_number=3,
                chunk_index=2,
                text="RESULTS Experiments show faster search and stronger citation coverage.",
                score=0.66,
                source_score=0.61,
                ranking_signals={"vector_score": 0.61, "lexical_score": 0.4},
                section_heading="RESULTS",
            )
        ], RetrievalMode(mode="hybrid")

    monkeypatch.setattr("app.study.service.hybrid_search_chunks", fake_hybrid_search)

    summary = generate_document_summary(
        db_session,
        document.id,
        provider=provider,
        embedder_factory=lambda: ConstantEmbeddingProvider(),
    )

    assert "faster search" in provider.summary_context
    assert summary.citations[0]["chunk_id"] == "chunk-results"
    assert summary.citations[0]["snippet"].startswith("RESULTS Experiments")
    assert summary.citations[0]["score"] == 0.66
    assert summary.citations[0]["source_score"] == 0.61


def test_generate_document_summary_falls_back_to_ranked_chunks_when_retrieval_has_no_hits(monkeypatch, db_session):
    document = make_postgres_document()
    db_session.add(document)
    db_session.commit()
    provider = RecordingProvider()

    def fake_hybrid_search(db, query_embedding, query, top_k, document_id, **kwargs):
        return [], RetrievalMode(mode="lexical", fallback_reason="No matching lexical hits.")

    monkeypatch.setattr("app.study.service.hybrid_search_chunks", fake_hybrid_search)

    summary = generate_document_summary(
        db_session,
        document.id,
        provider=provider,
        embedder_factory=lambda: ConstantEmbeddingProvider(),
    )

    assert "DocIntel AI" in provider.summary_context
    assert summary.citations[0]["chunk_id"] == "00000000-0000-0000-0000-000000000301"


def test_build_study_questions_reuses_document_aware_answers_and_deduplicates():
    questions = build_study_questions(make_document(), count=5)

    question_texts = [question.question for question in questions]
    assert "What is this document about?" in question_texts
    assert "What methods are used?" in question_texts
    assert len(question_texts) == len(set(question_texts))
    methods = next(question for question in questions if question.question == "What methods are used?")
    assert "OCR, page chunks, embeddings" in methods.expected_answer
    assert methods.citations[0]["chunk_id"] == "chunk-method"


def test_build_study_questions_dedupes_provider_generated_questions():
    document = make_document()
    add_retrieval_only_chunk(document)
    provider = RecordingProvider()

    questions = build_study_questions(document, count=5, provider=provider)

    question_texts = [question.question for question in questions]
    assert question_texts.count("What is this document about?") == 1
    assert "What does the document say about export controls?" in question_texts
    generated = next(question for question in questions if question.question == "What does the document say about export controls?")
    assert generated.citations[0]["chunk_id"] == "chunk-retrieved"


def test_generate_study_questions_falls_back_to_ranked_chunks_when_retrieval_has_no_hits(monkeypatch, db_session):
    document = make_postgres_document()
    db_session.add(document)
    db_session.commit()
    provider = RecordingProvider()

    def fake_hybrid_search(db, query_embedding, query, top_k, document_id, **kwargs):
        return [], RetrievalMode(mode="lexical", fallback_reason="No matching lexical hits.")

    monkeypatch.setattr("app.study.service.hybrid_search_chunks", fake_hybrid_search)

    questions = generate_study_questions(
        db_session,
        document.id,
        count=2,
        provider=provider,
        embedder_factory=lambda: ConstantEmbeddingProvider(),
    )

    assert "faster search" in provider.question_context
    assert questions[0].citations[0]["chunk_id"] == "00000000-0000-0000-0000-000000000303"


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


def test_score_study_answer_reports_missing_key_terms():
    question = StudyQuestion(
        id="question-1",
        document_id="document-1",
        question="What methods are used?",
        expected_answer="The system uses OCR, page chunks, embeddings, and extractive citations.",
        citations=[],
    )

    weak = score_study_answer(question, "It uses OCR.")

    assert weak.score < 0.75
    assert "Missing terms:" in weak.feedback
    assert "embeddings" in weak.feedback
