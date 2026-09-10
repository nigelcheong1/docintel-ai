from app.db.models import Chunk, Document, DocumentStatus, Page, StudyQuestion
from app.llm.providers import AnswerEvaluationResult, GeneratedQuestionResult, LocalHeuristicLlmProvider
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
        self.summary_mode = ""
        self.question_mode = ""

    def summarize(self, context: str, mode: str = "concise") -> str:
        self.summary_context = context
        self.summary_mode = mode
        return "Provider summary from retrieved evidence."

    def generate_questions(self, context: str, count: int, mode: str = "balanced") -> list[GeneratedQuestionResult]:
        self.question_context = context
        self.question_mode = mode
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


class NoisyAcademicQuestionProvider(RecordingProvider):
    def generate_questions(self, context: str, count: int, mode: str = "balanced") -> list[GeneratedQuestionResult]:
        self.question_context = context
        self.question_mode = mode
        return [
            GeneratedQuestionResult(
                question="What does the document say about 0 1?",
                expected_answer=(
                    "The 16-dimensional feature vector includes idx feature 0,1 ball x, y and "
                    "8,9 ball-paddle relative positions."
                ),
            ),
            GeneratedQuestionResult(
                question="What does the document say about 14 controlling?",
                expected_answer=(
                    "A single shared policy needs an explicit cue for which side it is controlling."
                ),
            ),
            GeneratedQuestionResult(
                question="What does the document say about agent both?",
                expected_answer=(
                    "Both paddles read the same shared image while only the first agent receives "
                    "the visual observation."
                ),
            ),
            GeneratedQuestionResult(
                question="What does the document say about action both?",
                expected_answer="The action mapping is global and screen-space, identical for both paddles.",
            ),
            GeneratedQuestionResult(
                question="What design or methodology is used?",
                expected_answer=(
                    "Training is organised as a staged pipeline using a 16-dimensional observation "
                    "vector, shaped rewards, and PPO training."
                ),
            ),
        ][:count]


class NoisyResearchQuestionProvider(RecordingProvider):
    def generate_questions(self, context: str, count: int, mode: str = "balanced") -> list[GeneratedQuestionResult]:
        self.question_context = context
        self.question_mode = mode
        return [
            GeneratedQuestionResult(
                question="What datasets are mentioned?",
                expected_answer=(
                    "2025 v v Video description: A survey of methods, datasets, and evaluation metrics "
                    "ACM Computing Surveys 35 25 26 15 15 123 152 [45] Tell me Dave: Context-sensitive "
                    "grounding of natural language to manipulation instructions International Journal "
                    "of Robotics Research 14 16 10 18 6 109 151 [46] The body talks: Sensorimotor "
                    "communication and its brain and kinematic signatures Physics of Life Reviews 19 16 19 "
                    "13 12 106 107 [47] Survey of emotions in human-robot interactions."
                ),
            ),
            GeneratedQuestionResult(
                question="What does the document say about 1180 1351?",
                expected_answer="From Scopus, an aggregate of 2366 results were obtained, including 1180 papers and 1351 conference proceedings.",
            ),
            GeneratedQuestionResult(
                question="What does the document say about employed extract?",
                expected_answer="To screen and extract valuable insights from the targeted literature, this study employed a three-tiered fine screening process.",
            ),
            GeneratedQuestionResult(
                question="What is this document about?",
                expected_answer=(
                    "The integration of large language models into human-robot collaboration represents "
                    "a paradigm shift toward cognitive manufacturing under Industry 5.0."
                ),
            ),
            GeneratedQuestionResult(
                question="What methods are used?",
                expected_answer=(
                    "Human-robot collaboration Large language models Resilient manufacturing systems "
                    "Embodied intelligence Furthermore, we propose a layered training framework combining "
                    "domain-adaptive pre-training and scenario-"
                ),
            ),
        ][:count]


class UnsupportedSummaryProvider(RecordingProvider):
    def summarize(self, context: str, mode: str = "concise") -> str:
        self.summary_context = context
        self.summary_mode = mode
        return "The study analyzed 9999 papers and created a robot benchmark that is not in the cited evidence."


class DistortedResearchSummaryProvider(RecordingProvider):
    def summarize(self, context: str, mode: str = "concise") -> str:
        self.summary_context = context
        self.summary_mode = mode
        return (
            "The study screened 2,366 Scopus results, reducing an initial 4,364 papers to 2,092 after "
            "deduplication and 1,665 empirical papers after keyword screening. It presents a literature table "
            "covering task planning, decision making, perception, and embodied execution, and argues for standards "
            "that define rights, responsibilities, and transparency."
        )


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


def make_academic_report_document() -> Document:
    document = Document(
        id="academic-report-1",
        filename="DRL Final Report.pdf",
        stored_filename="DRL Final Report.pdf",
        mime_type="application/pdf",
        file_path="/tmp/DRL Final Report.pdf",
        status=DocumentStatus.INDEXED,
    )
    page_one = Page(
        id="academic-page-1",
        document_id=document.id,
        page_number=1,
        text=(
            "XIAMEN UNIVERSITY MALAYSIA Course Code : AIT306 Course Name : Deep Reinforcement Learning "
            "Lecturer : Goh Sim Kuan Assessment Title : Project Submission Prepared by : AIT2309628 Nigel Cheong Tze Hock"
        ),
        width=612,
        height=792,
    )
    page_three = Page(
        id="academic-page-3",
        document_id=document.id,
        page_number=3,
        text=(
            "Table of Contents 1. Overview & Objective ......................................................... 1 "
            "2. Design Approach .............................................................. 1 "
            "3. Observation: the 16-Dimensional Feature Contract ............................. 2"
        ),
        width=612,
        height=792,
    )
    page_four = Page(
        id="academic-page-4",
        document_id=document.id,
        page_number=4,
        text="Overview & Objective The project trains a PPO tennis agent to control rallies in Unity ML-Agents.",
        width=612,
        height=792,
    )
    page_five = Page(
        id="academic-page-5",
        document_id=document.id,
        page_number=5,
        text=(
            "Design Approach The implementation uses a 16-dimensional observation vector, shaped rewards, and PPO training. "
            "Results & Verification The final policy keeps rallies alive and reduces residual side asymmetry."
        ),
        width=612,
        height=792,
    )
    document.pages = [page_one, page_three, page_four, page_five]
    document.chunks = [
        Chunk(
            id="academic-front",
            document_id=document.id,
            page_id=page_one.id,
            page=page_one,
            chunk_index=0,
            text=page_one.text,
            token_estimate=len(page_one.text.split()),
            layout={},
        ),
        Chunk(
            id="academic-toc",
            document_id=document.id,
            page_id=page_three.id,
            page=page_three,
            chunk_index=1,
            text=page_three.text,
            token_estimate=len(page_three.text.split()),
            layout={},
        ),
        Chunk(
            id="academic-overview",
            document_id=document.id,
            page_id=page_four.id,
            page=page_four,
            chunk_index=2,
            text=page_four.text,
            token_estimate=len(page_four.text.split()),
            layout={"section_heading": "OVERVIEW"},
        ),
        Chunk(
            id="academic-method",
            document_id=document.id,
            page_id=page_five.id,
            page=page_five,
            chunk_index=3,
            text="METHOD " + page_five.text.split("Results & Verification")[0].strip(),
            token_estimate=15,
            layout={"section_heading": "METHOD"},
        ),
        Chunk(
            id="academic-results",
            document_id=document.id,
            page_id=page_five.id,
            page=page_five,
            chunk_index=4,
            text="RESULTS Results & Verification The final policy keeps rallies alive and reduces residual side asymmetry.",
            token_estimate=13,
            layout={"section_heading": "RESULTS"},
        ),
    ]
    return document


def make_research_review_document() -> Document:
    document = Document(
        id="research-review-1",
        filename="Paper 10.pdf",
        stored_filename="Paper 10.pdf",
        mime_type="application/pdf",
        file_path="/tmp/Paper 10.pdf",
        status=DocumentStatus.INDEXED,
    )
    page_one = Page(
        id="research-page-1",
        document_id=document.id,
        page_number=1,
        text=(
            "ABSTRACT The integration of large language models (LLMs) into human-robot collaboration "
            "(HRC) represents a paradigm shift toward cognitive manufacturing under Industry 5.0. "
            "This systematic review analyzes 1278 publications to identify enabling mechanisms, "
            "application hierarchies, and persistent challenges of LLM-enhanced HRC."
        ),
        width=612,
        height=792,
    )
    page_three = Page(
        id="research-page-3",
        document_id=document.id,
        page_number=3,
        text=(
            "RESULTS From Scopus, an aggregate of 2366 results were obtained, including 1180 papers "
            "and 1351 conference proceedings. After database harmonization, 4364 entries were reduced "
            "to 2092 works after duplicate removal and to 1665 relevant entries after title-and-abstract "
            "screening; all selected works were subsequently read in full. Publications that engaged with "
            "the topic but did not present empirical experimental research were excluded."
        ),
        width=612,
        height=792,
    )
    page_five = Page(
        id="research-page-5",
        document_id=document.id,
        page_number=5,
        text=(
            "METHOD The review used database harmonization, de-duplication, and a three-tiered "
            "screening workflow to narrow Scopus records into empirical HRC studies."
        ),
        width=612,
        height=792,
    )
    page_ten = Page(
        id="research-page-10",
        document_id=document.id,
        page_number=10,
        text=(
            "Table 4 Key literature review for HRC cognitive hierarchy lists 109 references from 2015-2026 "
            "and maps task planning and decision making, environmental perception and understanding, "
            "and embodied execution and interaction."
        ),
        width=612,
        height=792,
    )
    page_sixteen = Page(
        id="research-page-16",
        document_id=document.id,
        page_number=16,
        text=(
            "CONCLUSION The review emphasizes standards that delineate rights, responsibilities, "
            "ethical safeguards, transparency, value alignment, and scalability in HRC deployments."
        ),
        width=612,
        height=792,
    )
    page_twenty = Page(
        id="research-page-20",
        document_id=document.id,
        page_number=20,
        text="REFERENCES Lou et al. Tell me Dave. The body talks.",
        width=612,
        height=792,
    )
    document.pages = [page_one, page_three, page_five, page_ten, page_sixteen, page_twenty]
    document.chunks = [
        Chunk(
            id="research-abstract",
            document_id=document.id,
            page_id=page_one.id,
            page=page_one,
            chunk_index=0,
            text=page_one.text,
            token_estimate=len(page_one.text.split()),
            layout={"section_heading": "ABSTRACT"},
        ),
        Chunk(
            id="research-results",
            document_id=document.id,
            page_id=page_three.id,
            page=page_three,
            chunk_index=1,
            text=page_three.text,
            token_estimate=len(page_three.text.split()),
            layout={"section_heading": "RESULTS"},
        ),
        Chunk(
            id="research-method",
            document_id=document.id,
            page_id=page_five.id,
            page=page_five,
            chunk_index=2,
            text=page_five.text,
            token_estimate=len(page_five.text.split()),
            layout={"section_heading": "METHOD"},
        ),
        Chunk(
            id="research-literature-table",
            document_id=document.id,
            page_id=page_ten.id,
            page=page_ten,
            chunk_index=3,
            text=page_ten.text,
            token_estimate=len(page_ten.text.split()),
            layout={},
        ),
        Chunk(
            id="research-conclusion",
            document_id=document.id,
            page_id=page_sixteen.id,
            page=page_sixteen,
            chunk_index=4,
            text=page_sixteen.text,
            token_estimate=len(page_sixteen.text.split()),
            layout={"section_heading": "CONCLUSION"},
        ),
        Chunk(
            id="research-references",
            document_id=document.id,
            page_id=page_twenty.id,
            page=page_twenty,
            chunk_index=5,
            text=page_twenty.text,
            token_estimate=len(page_twenty.text.split()),
            layout={"section_heading": "REFERENCES"},
        ),
    ]
    return document


def research_review_summary_hits(document: Document) -> list[SearchHit]:
    chunks = {chunk.id: chunk for chunk in document.chunks}

    def hit(chunk_id: str, score: float, heading: str | None = None) -> SearchHit:
        chunk = chunks[chunk_id]
        return SearchHit(
            chunk_id=chunk.id,
            document_id=document.id,
            document_filename=document.filename,
            page_number=chunk.page.page_number,
            chunk_index=chunk.chunk_index,
            text=chunk.text,
            score=score,
            source_score=score,
            ranking_signals={"lexical_score": score},
            section_heading=heading,
        )

    return [
        hit("research-literature-table", 0.9),
        hit("research-results", 0.86, "RESULTS"),
        hit("research-conclusion", 0.8),
    ]


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


def test_build_document_summary_filters_toc_fragments_for_academic_reports():
    document = make_academic_report_document()
    retrieval_hits = [
        SearchHit(
            chunk_id="academic-toc",
            document_id=document.id,
            document_filename=document.filename,
            page_number=3,
            chunk_index=1,
            text=document.chunks[1].text,
            score=0.9,
            source_score=0.9,
            ranking_signals={"lexical_score": 0.9},
            section_heading=None,
        ),
        SearchHit(
            chunk_id="academic-overview",
            document_id=document.id,
            document_filename=document.filename,
            page_number=4,
            chunk_index=2,
            text=document.chunks[2].text,
            score=0.8,
            source_score=0.8,
            ranking_signals={"lexical_score": 0.8},
            section_heading="OVERVIEW",
        ),
        SearchHit(
            chunk_id="academic-results",
            document_id=document.id,
            document_filename=document.filename,
            page_number=5,
            chunk_index=4,
            text=document.chunks[4].text,
            score=0.7,
            source_score=0.7,
            ranking_signals={"lexical_score": 0.7},
            section_heading="RESULTS",
        ),
    ]

    summary = build_document_summary(document, retrieval_hits=retrieval_hits)

    assert "PPO tennis agent" in summary.content
    assert "keeps rallies alive" in summary.content
    assert "Table of Contents" not in summary.content
    assert "................................" not in summary.content
    assert "Page 5 RESULTS" not in summary.content
    assert [citation["chunk_id"] for citation in summary.citations] == ["academic-overview", "academic-results"]


def test_academic_document_summary_balances_core_sections_when_retrieval_is_narrow():
    document = make_academic_report_document()
    document.chunks[3].text = (
        "METHOD 4. Development Pipeline Phase 0: Measuring the environment Before writing any learning code, "
        "the environment was characterised empirically. The implementation uses a 16-dimensional observation "
        "vector, shaped rewards, and PPO training."
    )
    retrieval_hits = [
        SearchHit(
            chunk_id="academic-method",
            document_id=document.id,
            document_filename=document.filename,
            page_number=5,
            chunk_index=3,
            text=document.chunks[3].text,
            score=0.86,
            source_score=0.82,
            ranking_signals={"lexical_score": 0.86},
            section_heading="METHOD",
        )
    ]

    summary = build_document_summary(document, retrieval_hits=retrieval_hits)

    assert "PPO tennis agent" in summary.content
    assert "16-dimensional observation vector" in summary.content
    assert "keeps rallies alive" in summary.content
    assert "Table of Contents" not in summary.content
    assert not summary.content.startswith("4. Development Pipeline Phase 0")
    assert [citation["chunk_id"] for citation in summary.citations] == [
        "academic-overview",
        "academic-method",
        "academic-results",
    ]

    provider_summary = build_document_summary(
        document,
        provider=LocalHeuristicLlmProvider(),
        retrieval_hits=retrieval_hits,
    )
    assert "PPO tennis agent" in provider_summary.content
    assert "16-dimensional observation vector" in provider_summary.content
    assert "keeps rallies alive" in provider_summary.content
    assert not provider_summary.content.startswith("4. Development Pipeline Phase 0")


def test_build_document_summary_can_use_provider_with_retrieved_context():
    document = make_document()
    add_retrieval_only_chunk(document)
    provider = RecordingProvider()

    summary = build_document_summary(document, provider=provider)

    assert summary.content == "Provider summary from retrieved evidence."
    assert "export controls" in provider.summary_context
    assert summary.citations[0]["chunk_id"] == "chunk-retrieved"
    assert "export controls" in summary.citations[0]["snippet"]


def test_build_document_summary_rejects_provider_claims_not_supported_by_citations():
    summary = build_document_summary(make_research_review_document(), provider=UnsupportedSummaryProvider())

    assert "9999" not in summary.content
    assert "robot benchmark" not in summary.content
    assert "large language models" in summary.content.lower()
    assert summary.citations[0]["chunk_id"] == "research-abstract"


def test_build_document_summary_normalizes_research_screening_count_wording():
    document = make_research_review_document()

    summary = build_document_summary(
        document,
        provider=DistortedResearchSummaryProvider(),
        retrieval_hits=research_review_summary_hits(document),
    )

    assert summary.content == (
        "The study reviews human-robot collaboration, beginning with 2,366 Scopus results and "
        "narrowing the literature through database harmonization, deduplication, title-and-abstract screening, "
        "and full-text review. It maps HRC cognitive-hierarchy tasks such as planning, decision making, "
        "perception, and embodied execution, and argues for standards around rights, responsibilities, "
        "transparency, ethics, and scalable deployment."
    )
    assert [citation["chunk_id"] for citation in summary.citations] == [
        "research-literature-table",
        "research-results",
        "research-conclusion",
    ]


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


def test_build_study_questions_for_academic_report_use_meaningful_evidence_not_headings():
    questions = build_study_questions(make_academic_report_document(), count=4)

    assert questions
    combined_expected = " ".join(question.expected_answer for question in questions)
    combined_questions = " ".join(question.question for question in questions)

    assert "Table of Contents" not in combined_expected
    assert "................................" not in combined_expected
    assert "1 contents" not in combined_questions
    assert any("PPO" in question.expected_answer or "16-dimensional observation" in question.expected_answer for question in questions)
    assert any("rallies alive" in question.expected_answer for question in questions)


def test_build_study_questions_skip_academic_future_work_when_only_declaration_mentions_future():
    document = make_academic_report_document()
    declaration_page = Page(
        id="academic-page-2",
        document_id=document.id,
        page_number=2,
        text=(
            "Own Work Declaration I/We acknowledge the digital copy of the work may be retained "
            "for future comparisons."
        ),
        width=612,
        height=792,
    )
    document.pages.append(declaration_page)
    document.chunks.append(
        Chunk(
            id="academic-declaration",
            document_id=document.id,
            page_id=declaration_page.id,
            page=declaration_page,
            chunk_index=1,
            text=declaration_page.text,
            token_estimate=len(declaration_page.text.split()),
            layout={},
        )
    )

    questions = build_study_questions(document, count=5)

    question_texts = [question.question for question in questions]
    assert "What limitations or future work are discussed?" not in question_texts


def test_build_study_questions_dedupes_academic_overview_question_wording():
    questions = build_study_questions(make_academic_report_document(), count=5)

    question_texts = [question.question for question in questions]

    assert "What is this project report about?" in question_texts
    assert "What is this document about?" not in question_texts
    assert "What are the main topics covered in this document?" not in question_texts


def test_build_study_questions_filters_provider_fragment_questions_for_academic_reports():
    questions = build_study_questions(
        make_academic_report_document(),
        count=5,
        provider=NoisyAcademicQuestionProvider(),
    )

    question_texts = [question.question for question in questions]
    combined_questions = " ".join(question_texts)

    assert "What design or methodology is used?" in question_texts
    assert "What results are reported?" in question_texts
    assert "0 1" not in combined_questions
    assert "14 controlling" not in combined_questions
    assert "agent both" not in combined_questions
    assert "action both" not in combined_questions


def test_build_study_questions_rejects_noisy_research_provider_answers():
    questions = build_study_questions(
        make_research_review_document(),
        count=5,
        provider=NoisyResearchQuestionProvider(),
    )

    expected_answers = " ".join(question.expected_answer for question in questions)
    question_texts = [question.question for question in questions]
    combined_questions = " ".join(question_texts)
    method_answer = next(question.expected_answer for question in questions if question.question == "What methods are used?")

    assert "What is this document about?" in question_texts
    assert "1180 1351" not in combined_questions
    assert "employed extract" not in combined_questions
    assert "ACM Computing Surveys" not in expected_answers
    assert "[45]" not in expected_answers
    assert "scenario-" not in expected_answers
    assert "three-tiered" in method_answer
    assert "screening" in method_answer


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


def test_generate_study_questions_can_replace_stale_existing_questions(monkeypatch, db_session):
    document = make_postgres_document()
    stale_question = StudyQuestion(
        id="00000000-0000-0000-0000-000000000401",
        document_id=document.id,
        question="What does the document say about 1 contents?",
        expected_answer="XIAMEN UNIVERSITY MALAYSIA Table of Contents 1.",
        citations=[],
    )
    document.study_questions = [stale_question]
    db_session.add(document)
    db_session.commit()

    def fake_hybrid_search(db, query_embedding, query, top_k, document_id, **kwargs):
        return [], RetrievalMode(mode="lexical", fallback_reason="No matching lexical hits.")

    monkeypatch.setattr("app.study.service.hybrid_search_chunks", fake_hybrid_search)

    questions = generate_study_questions(
        db_session,
        document.id,
        count=2,
        provider=RecordingProvider(),
        embedder_factory=lambda: ConstantEmbeddingProvider(),
        replace_existing=True,
    )

    saved_questions = db_session.query(StudyQuestion).filter_by(document_id=document.id).all()
    assert len(saved_questions) == len(questions)
    assert stale_question.id not in {question.id for question in saved_questions}
    assert not any("1 contents" in question.question for question in saved_questions)
    assert not any("Table of Contents" in question.expected_answer for question in saved_questions)


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
