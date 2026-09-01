from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from pydantic import BaseModel

from app.db.models import Chunk, Document, DocumentStatus, Page
from app.documents.intelligence import build_document_profile
from app.documents.parse_quality import build_parse_quality_from_pages
from app.documents.parser import ParsedPage
from app.retrieval.document_answers import build_document_aware_answer
from app.retrieval.query_router import route_query


@dataclass(frozen=True)
class GoldenChunkSpec:
    page_number: int
    heading: str | None
    text: str


@dataclass(frozen=True)
class GoldenDocumentSpec:
    key: str
    filename: str
    chunks: tuple[GoldenChunkSpec, ...]


@dataclass(frozen=True)
class GoldenCaseSpec:
    case_id: str
    document_key: str
    question: str
    expected_status: str
    expected_terms: tuple[str, ...]
    expected_intent: str
    quality_dimension: str = "answer_quality"


class GoldenEvalCaseResult(BaseModel):
    case_id: str
    document_name: str
    document_type: str
    question: str
    expected_status: str
    actual_status: str
    expected_terms: list[str]
    query_intent: str
    confidence: str
    citation_count: int
    answer_preview: str | None
    quality_reason: str
    quality_dimension: str
    passed: bool
    failure_reasons: list[str]


class GoldenEvalSummary(BaseModel):
    total_cases: int
    passed_cases: int
    failed_cases: int
    pass_rate: float
    answerable_cases: int
    abstention_cases: int
    document_types: dict[str, int]
    quality_dimensions: dict[str, int]


class GoldenEvalResponse(BaseModel):
    name: str
    summary: GoldenEvalSummary
    cases: list[GoldenEvalCaseResult]


_DOCUMENTS: tuple[GoldenDocumentSpec, ...] = (
    GoldenDocumentSpec(
        key="research",
        filename="h2r-paper.pdf",
        chunks=(
            GoldenChunkSpec(
                1,
                "ABSTRACT",
                (
                    "ABSTRACT H2R Bridge: Transferring vision-language models to few-shot intention "
                    "meta-perception in human robot collaboration. Human-robot collaboration enhances "
                    "efficiency by enabling robots to work alongside human operators in shared tasks. "
                    "This paper introduces H2R Bridge, a vision-language model transfer framework for "
                    "few-shot intention meta-perception."
                ),
            ),
            GoldenChunkSpec(
                3,
                "METHOD",
                (
                    "METHOD Joint vision-language encoder architecture uses a visual encoder and a GPT-2 "
                    "language encoder to align action representations with textual intentions."
                ),
            ),
            GoldenChunkSpec(
                7,
                "RESULTS",
                (
                    "RESULTS Experiments show that ViT-B/16 outperforms ViT-B/32, achieving TOP1 "
                    "accuracy of 91.38 on InHARD and 83.65 on HRI30."
                ),
            ),
            GoldenChunkSpec(
                8,
                "DATASET",
                "DATASET Experiments use InHARD, HRI30, Kinetics-400, UCF-101, HMDB-51, MECCANO, and Imagenet.",
            ),
            GoldenChunkSpec(
                12,
                "FUTURE WORK",
                (
                    "FUTURE WORK Future research directions include language-conditioned robotic policy "
                    "learning and virtual-to-real mapping techniques for actual scenarios."
                ),
            ),
            GoldenChunkSpec(13, "REFERENCES", "REFERENCES D. Wu et al. Journal of Manufacturing Systems."),
        ),
    ),
    GoldenDocumentSpec(
        key="resume",
        filename="candidate-resume.pdf",
        chunks=(
            GoldenChunkSpec(
                1,
                "PROFESSIONAL SUMMARY",
                "PROFESSIONAL SUMMARY AI student focused on computer vision, machine learning, and applied analytics.",
            ),
            GoldenChunkSpec(
                1,
                "TECHNICAL SKILLS",
                "TECHNICAL SKILLS Python, C++, SQL, JavaScript, PyTorch, TensorFlow, scikit-learn, and Git.",
            ),
            GoldenChunkSpec(
                1,
                "PROJECTS",
                (
                    "PROJECTS Skin Lesion Classification using convolutional neural networks. Traffic "
                    "Accident Prediction dashboard using time-series features and SQL data pipelines."
                ),
            ),
            GoldenChunkSpec(
                2,
                "EDUCATION",
                "EDUCATION Bachelor of Computer Science in Artificial Intelligence, Xiamen University Malaysia.",
            ),
        ),
    ),
    GoldenDocumentSpec(
        key="invoice",
        filename="invoice-1001.pdf",
        chunks=(
            GoldenChunkSpec(
                1,
                "INVOICE DETAILS",
                "INVOICE DETAILS Vendor: DocIntel Labs. Bill To: Xiamen University Malaysia. Invoice INV-1001.",
            ),
            GoldenChunkSpec(
                1,
                "PAYMENT SUMMARY",
                "PAYMENT SUMMARY Issue Date: 2026-08-01. Due Date: 2026-08-30. Total Due RM 1,272.00.",
            ),
        ),
    ),
    GoldenDocumentSpec(
        key="contract",
        filename="service-agreement.pdf",
        chunks=(
            GoldenChunkSpec(
                1,
                "PARTIES",
                "PARTIES This service agreement is between Acme Robotics Sdn Bhd and Beta University.",
            ),
            GoldenChunkSpec(
                2,
                "OBLIGATIONS",
                (
                    "OBLIGATIONS Acme Robotics Sdn Bhd shall provide monthly robotics maintenance, "
                    "and Beta University must provide safe lab access and pay the monthly service fee."
                ),
            ),
        ),
    ),
    GoldenDocumentSpec(
        key="report",
        filename="quarterly-lab-report.pdf",
        chunks=(
            GoldenChunkSpec(
                1,
                "EXECUTIVE SUMMARY",
                "EXECUTIVE SUMMARY The report reviews lab usage, support capacity, and student booking operations.",
            ),
            GoldenChunkSpec(
                2,
                "FINDINGS",
                "FINDINGS Lab usage increased 18%, while booking delays rose during evening project sessions.",
            ),
            GoldenChunkSpec(
                3,
                "RECOMMENDATIONS",
                "RECOMMENDATIONS Add evening supervisor hours and upgrade the booking workflow before thesis season.",
            ),
        ),
    ),
)

_CASES: tuple[GoldenCaseSpec, ...] = (
    GoldenCaseSpec(
        "research-overview",
        "research",
        "What is this document about?",
        "answerable",
        ("H2R Bridge", "human-robot"),
        "overview",
    ),
    GoldenCaseSpec(
        "research-methods",
        "research",
        "What methods are used?",
        "answerable",
        ("vision-language", "encoder"),
        "methods",
    ),
    GoldenCaseSpec(
        "research-datasets",
        "research",
        "What datasets are mentioned?",
        "answerable",
        ("InHARD", "HRI30"),
        "datasets",
    ),
    GoldenCaseSpec(
        "research-results",
        "research",
        "What results are reported?",
        "answerable",
        ("TOP1", "91.38"),
        "results",
    ),
    GoldenCaseSpec(
        "research-hard-negative-total-due",
        "research",
        "What total amount is due?",
        "insufficient_evidence",
        (),
        "amounts",
        "abstention_safety",
    ),
    GoldenCaseSpec(
        "resume-skills",
        "resume",
        "What technical skills are mentioned?",
        "answerable",
        ("Python", "PyTorch"),
        "skills",
    ),
    GoldenCaseSpec(
        "resume-projects",
        "resume",
        "What projects are listed in this document?",
        "answerable",
        ("Skin Lesion", "Traffic Accident"),
        "projects",
    ),
    GoldenCaseSpec(
        "invoice-total-due",
        "invoice",
        "What total amount is due?",
        "answerable",
        ("RM 1,272.00",),
        "amounts",
    ),
    GoldenCaseSpec(
        "invoice-payment-due",
        "invoice",
        "When is payment due?",
        "answerable",
        ("2026-08-30",),
        "payment_due",
    ),
    GoldenCaseSpec(
        "contract-parties",
        "contract",
        "Who are the parties involved?",
        "answerable",
        ("Acme Robotics", "Beta University"),
        "parties",
    ),
    GoldenCaseSpec(
        "contract-obligations",
        "contract",
        "What obligations are mentioned?",
        "answerable",
        ("monthly robotics maintenance", "safe lab access"),
        "obligations",
    ),
    GoldenCaseSpec(
        "report-findings",
        "report",
        "What are the key findings?",
        "answerable",
        ("18%", "booking delays"),
        "findings",
    ),
    GoldenCaseSpec(
        "report-recommendations",
        "report",
        "What recommendations are listed?",
        "answerable",
        ("evening supervisor", "booking workflow"),
        "recommendations",
    ),
)


def _make_document(spec: GoldenDocumentSpec) -> Document:
    document = Document(
        id=f"golden-{spec.key}",
        filename=spec.filename,
        stored_filename=spec.filename,
        mime_type="application/pdf",
        file_path=f"/golden/{spec.filename}",
        status=DocumentStatus.INDEXED,
    )

    page_texts: dict[int, list[str]] = {}
    for chunk in spec.chunks:
        page_texts.setdefault(chunk.page_number, []).append(chunk.text)

    pages = [
        Page(
            id=f"golden-{spec.key}-page-{page_number}",
            document_id=document.id,
            page_number=page_number,
            text="\n".join(texts),
            width=612,
            height=792,
        )
        for page_number, texts in sorted(page_texts.items())
    ]
    pages_by_number = {page.page_number: page for page in pages}

    chunks = [
        Chunk(
            id=f"golden-{spec.key}-chunk-{index}",
            document_id=document.id,
            page_id=pages_by_number[chunk.page_number].id,
            page=pages_by_number[chunk.page_number],
            chunk_index=index,
            text=chunk.text,
            token_estimate=len(chunk.text.split()),
            layout={"section_heading": chunk.heading} if chunk.heading else {},
        )
        for index, chunk in enumerate(spec.chunks)
    ]

    document.pages = pages
    document.chunks = chunks
    return document


def _evaluate_case(case: GoldenCaseSpec, document: Document) -> GoldenEvalCaseResult:
    profile = build_document_profile(document)
    route = route_query(case.question, profile.document_type)
    result = build_document_aware_answer(case.question, document, profile, route)
    if result is None:
        answer = None
        quality_status = "insufficient_evidence"
        confidence = "weak"
        quality_reason = "No document-aware answer path handled this query."
        citation_count = 0
        query_intent = route.intent
        document_type = profile.document_type
    else:
        answer = result.answer
        quality_status = result.quality.status
        confidence = result.quality.confidence
        quality_reason = result.quality.reason
        citation_count = len(answer.citations) if answer is not None else 0
        query_intent = result.query_intent
        document_type = result.document_type

    answer_preview = answer.summary if answer is not None else None
    failure_reasons: list[str] = []
    if quality_status != case.expected_status:
        failure_reasons.append(f"Expected status {case.expected_status}, got {quality_status}.")
    if query_intent != case.expected_intent:
        failure_reasons.append(f"Expected intent {case.expected_intent}, got {query_intent}.")
    if case.expected_status == "answerable" and answer is None:
        failure_reasons.append("Expected an answer with citations.")
    if case.expected_status == "answerable" and citation_count == 0:
        failure_reasons.append("Expected at least one citation.")
    if case.expected_status == "insufficient_evidence" and answer is not None:
        failure_reasons.append("Expected no answer preview for an abstention case.")
    if case.expected_status == "insufficient_evidence" and citation_count != 0:
        failure_reasons.append("Expected zero citations for an abstention case.")

    normalized_answer = (answer_preview or "").lower()
    for term in case.expected_terms:
        if term.lower() not in normalized_answer:
            failure_reasons.append(f"Missing expected term: {term}.")

    return GoldenEvalCaseResult(
        case_id=case.case_id,
        document_name=document.filename,
        document_type=document_type,
        question=case.question,
        expected_status=case.expected_status,
        actual_status=quality_status,
        expected_terms=list(case.expected_terms),
        query_intent=query_intent,
        confidence=confidence,
        citation_count=citation_count,
        answer_preview=answer_preview,
        quality_reason=quality_reason,
        quality_dimension=case.quality_dimension,
        passed=not failure_reasons,
        failure_reasons=failure_reasons,
    )


def _evaluate_parse_quality_case() -> GoldenEvalCaseResult:
    profile = build_parse_quality_from_pages(
        [
            ParsedPage(page_number=1, text=".", width=612, height=792),
            ParsedPage(page_number=2, text="", width=612, height=792),
        ]
    )
    expected_warning = "This PDF has very little extractable text and may need OCR."
    answer_preview = f"OCR recommended: {expected_warning}"
    failure_reasons: list[str] = []
    if profile.scanned_likelihood != "high":
        failure_reasons.append(f"Expected high scanned likelihood, got {profile.scanned_likelihood}.")
    if expected_warning not in profile.warnings:
        failure_reasons.append("Expected OCR guidance warning.")

    return GoldenEvalCaseResult(
        case_id="parse-quality-low-text-guidance",
        document_name="sparse-text.pdf",
        document_type="parse_quality",
        question="Can this PDF be searched locally?",
        expected_status="insufficient_evidence",
        actual_status="insufficient_evidence",
        expected_terms=["OCR"],
        query_intent="parse_quality",
        confidence="weak",
        citation_count=0,
        answer_preview=answer_preview,
        quality_reason="Parse quality detected very little extractable text.",
        quality_dimension="parse_quality",
        passed=not failure_reasons,
        failure_reasons=failure_reasons,
    )


def run_golden_evaluation() -> GoldenEvalResponse:
    documents = {spec.key: _make_document(spec) for spec in _DOCUMENTS}
    cases = [_evaluate_case(case, documents[case.document_key]) for case in _CASES]
    cases.append(_evaluate_parse_quality_case())
    passed_cases = sum(1 for case in cases if case.passed)
    document_types = Counter(case.document_type for case in cases)
    quality_dimensions = Counter(case.quality_dimension for case in cases)

    return GoldenEvalResponse(
        name="universal-document-qa-golden",
        summary=GoldenEvalSummary(
            total_cases=len(cases),
            passed_cases=passed_cases,
            failed_cases=len(cases) - passed_cases,
            pass_rate=round(passed_cases / len(cases), 4) if cases else 0.0,
            answerable_cases=sum(1 for case in cases if case.expected_status == "answerable"),
            abstention_cases=sum(1 for case in cases if case.expected_status == "insufficient_evidence"),
            document_types=dict(sorted(document_types.items())),
            quality_dimensions=dict(sorted(quality_dimensions.items())),
        ),
        cases=cases,
    )
