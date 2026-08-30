from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable

from app.db.models import Chunk, Document, Page
from app.documents.schemas import DocumentFactRead, DocumentProfileRead, DocumentSectionRead
from app.retrieval.reranker import infer_section_intents

DocumentType = str

_MAX_FACTS_PER_GROUP = 12
_MAX_SECTIONS = 24
_MAX_PREVIEW_CHARS = 320

_DATE_PATTERNS = (
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
    re.compile(
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:19|20)\d{2}\b"),
)
_MONEY_PATTERN = re.compile(r"\b(?:RM|USD|EUR|GBP|MYR|\$|€|£)\s?\d[\d,]*(?:\.\d{2})?\b", re.IGNORECASE)
_PERCENT_PATTERN = re.compile(r"\b\d+(?:\.\d+)?\s?%\b")
_METRIC_PATTERN = re.compile(r"\b(?:TOP1|TOP5|F1|ACC|AUC|MAP|IOU|DICE|RECALL|PRECISION)[\s:=]*\d+(?:\.\d+)?\b", re.IGNORECASE)
_TABLE_NUMBER_PATTERN = re.compile(r"\b\d+(?:\.\d+)?\b")
_METRIC_CONTEXT_PATTERN = re.compile(r"\b(?:TOP1|TOP5|F1|ACC|AUC|MAP|IOU|DICE|RECALL|PRECISION|ACCURACY|TABLE)\b", re.IGNORECASE)
_DATASET_PATTERN = re.compile(
    r"\b(?:Kinetics-400|UCF-101|HMDB-51|ImageNet|COCO|CIFAR-10|CIFAR-100|MNIST|FUNSD|SQuAD|BraTS\s?2019|PubMed|MIMIC-III|MIMIC-IV)\b",
    re.IGNORECASE,
)
_CAPITALIZED_PHRASE_PATTERN = re.compile(
    r"\b[A-Z][A-Za-z0-9&.+-]*(?:\s+[A-Z][A-Za-z0-9&.+-]*){1,5}\b"
)
_BETWEEN_PARTIES_PATTERN = re.compile(
    r"\bbetween\s+(.+?)\s+and\s+(.+?)(?:\.|,|\n|;|$)",
    re.IGNORECASE,
)
_BILL_TO_PATTERN = re.compile(r"\b(?:bill\s+to|client|customer|sold\s+to)\s*:?\s*([^\n.;]+)", re.IGNORECASE)
_VENDOR_PATTERN = re.compile(r"\b(?:vendor|supplier|from)\s*:?\s*([^\n.;]+)", re.IGNORECASE)

_KNOWN_HEADINGS = {
    "ABSTRACT",
    "KEYWORDS",
    "INTRODUCTION",
    "BACKGROUND",
    "RELATED WORK",
    "LITERATURE REVIEW",
    "METHODOLOGY",
    "METHOD",
    "METHODS",
    "APPROACH",
    "MODEL",
    "EXPERIMENT",
    "EXPERIMENTS",
    "EXPERIMENTAL SETUP",
    "EVALUATION",
    "RESULT",
    "RESULTS",
    "DISCUSSION",
    "LIMITATION",
    "LIMITATIONS",
    "FUTURE WORK",
    "CONCLUSION",
    "REFERENCES",
    "APPENDIX",
    "PROFESSIONAL SUMMARY",
    "CAREER OBJECTIVE",
    "SUMMARY",
    "ABOUT ME",
    "EDUCATION",
    "WORK EXPERIENCE",
    "PROFESSIONAL EXPERIENCE",
    "INTERNSHIP EXPERIENCE",
    "PROJECT EXPERIENCE",
    "EXPERIENCE",
    "KEY PROJECTS",
    "PROJECTS",
    "TECHNICAL SKILLS",
    "CORE SKILLS",
    "PROGRAMMING LANGUAGES",
    "FRAMEWORKS AND LIBRARIES",
    "FRAMEWORKS & LIBRARIES",
    "TOOLS AND PLATFORMS",
    "TOOLS & PLATFORMS",
    "CERTIFICATIONS",
    "ACHIEVEMENTS",
    "LANGUAGES",
    "LANGUAGE",
    "SKILLS",
    "INVOICE",
    "INVOICE DETAILS",
    "INVOICE SUMMARY",
    "PAYMENT SUMMARY",
    "PAYMENT TERMS",
    "BILL TO",
    "SHIP TO",
    "VENDOR",
    "CLIENT",
    "ITEMS",
    "SUBTOTAL",
    "TAX",
    "TOTAL",
    "BALANCE DUE",
    "AGREEMENT",
    "PARTIES",
    "TERMS",
    "OBLIGATIONS",
    "RESPONSIBILITIES",
    "PAYMENT",
    "CONFIDENTIALITY",
    "TERMINATION",
    "LIABILITY",
    "GOVERNING LAW",
    "SIGNATURES",
    "EFFECTIVE DATE",
    "EXECUTIVE SUMMARY",
    "FINDINGS",
    "RECOMMENDATIONS",
    "RISKS",
    "NEXT STEPS",
    "OVERVIEW",
    "OBJECTIVES",
    "SCOPE",
    "ANALYSIS",
    "DATASET",
    "DATASETS",
}

_HEADING_BY_NORMALIZED = {re.sub(r"[^A-Z0-9]+", " ", heading).strip(): heading for heading in _KNOWN_HEADINGS}
_SECTION_LINE_PATTERN = re.compile(r"^\s*(?:\d+(?:\.\d+)*\.?\s+)?([A-Za-z][A-Za-z &/-]{2,60})\s*:?\s*$")
_DOCUMENT_TYPE_KEYWORDS = {
    "research_paper": {
        "abstract": 4,
        "references": 3,
        "introduction": 2,
        "method": 2,
        "methodology": 2,
        "results": 2,
        "experiments": 2,
        "doi": 3,
        "et al": 2,
        "benchmark": 2,
        "dataset": 2,
        "table": 1,
        "figure": 1,
    },
    "resume": {
        "resume": 3,
        "curriculum vitae": 4,
        "education": 2,
        "experience": 2,
        "technical skills": 4,
        "projects": 2,
        "cgpa": 2,
        "linkedin": 1,
        "github": 1,
    },
    "invoice": {
        "invoice": 5,
        "bill to": 4,
        "subtotal": 3,
        "total due": 5,
        "balance due": 4,
        "payment terms": 3,
        "tax": 2,
        "due date": 3,
    },
    "contract": {
        "agreement": 4,
        "contract": 4,
        "parties": 3,
        "obligations": 4,
        "termination": 3,
        "governing law": 3,
        "confidentiality": 3,
        "whereas": 2,
        "shall": 2,
    },
    "report": {
        "executive summary": 4,
        "findings": 3,
        "recommendations": 3,
        "risk": 2,
        "analysis": 2,
        "next steps": 2,
        "objectives": 2,
    },
}

_SUGGESTED_QUESTIONS = {
    "research_paper": [
        "What is this document about?",
        "What methods are used?",
        "What datasets are mentioned?",
        "What results are reported?",
        "What limitations or future work are discussed?",
    ],
    "resume": [
        "What technical skills are mentioned?",
        "What projects are listed in this document?",
        "What education background is listed?",
        "What experience is described?",
    ],
    "invoice": [
        "What total amount is due?",
        "When is payment due?",
        "Who is the invoice billed to?",
        "What payment terms are mentioned?",
    ],
    "contract": [
        "Who are the parties involved?",
        "What obligations are mentioned?",
        "What risks or termination terms are mentioned?",
        "What dates are mentioned?",
    ],
    "report": [
        "What is this document about?",
        "What are the key findings?",
        "What recommendations are listed?",
        "What risks are mentioned?",
    ],
    "generic": [
        "What is this document about?",
        "What are the main topics covered in this document?",
        "What dates are mentioned?",
    ],
}


def clean_text(text: str) -> str:
    dehyphenated = re.sub(r"(?<=\w)-\s+(?=\w)", "", text)
    return " ".join(dehyphenated.split())


def strip_leading_heading(text: str, heading: str | None) -> str:
    cleaned = clean_text(text)
    if not heading:
        return cleaned
    pattern = re.compile(rf"^\s*{re.escape(heading)}\s*[:.-]?\s*", re.IGNORECASE)
    stripped = pattern.sub("", cleaned, count=1).strip()
    return stripped or cleaned


def _truncate(text: str, max_chars: int = _MAX_PREVIEW_CHARS) -> str:
    cleaned = clean_text(text)
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 3].rstrip() + "..."


def _ordered_pages(document: Document) -> list[Page]:
    return sorted(document.pages, key=lambda page: page.page_number)


def ordered_chunks(document: Document) -> list[Chunk]:
    return sorted(document.chunks, key=lambda chunk: (chunk.page.page_number, chunk.chunk_index))


def chunk_heading(chunk: Chunk) -> str | None:
    heading = chunk.layout.get("section_heading") if isinstance(chunk.layout, dict) else None
    if isinstance(heading, str) and heading.strip():
        return _canonical_heading(heading)
    return None


def _full_text(document: Document) -> str:
    return "\n".join(page.text for page in _ordered_pages(document) if page.text)


def _canonical_heading(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9]+", " ", value).strip().upper()
    return _HEADING_BY_NORMALIZED.get(normalized, normalized)


def _line_heading(line: str) -> str | None:
    match = _SECTION_LINE_PATTERN.match(line.strip())
    if match is None:
        return None
    return _canonical_heading(match.group(1))


def _section_from_chunk(chunk: Chunk) -> DocumentSectionRead | None:
    heading = chunk_heading(chunk)
    if heading is None:
        return None
    return DocumentSectionRead(
        heading=heading,
        page_number=chunk.page.page_number,
        text_preview=_truncate(strip_leading_heading(chunk.text, heading)),
        intents=sorted(infer_section_intents(heading)),
    )


def _sections_from_page_lines(pages: Iterable[Page]) -> list[DocumentSectionRead]:
    sections: list[DocumentSectionRead] = []
    seen: set[tuple[str, int]] = set()
    for page in pages:
        lines = [line.strip() for line in page.text.splitlines() if line.strip()]
        for index, line in enumerate(lines):
            heading = _line_heading(line)
            if heading not in _KNOWN_HEADINGS:
                continue
            key = (heading, page.page_number)
            if key in seen:
                continue
            seen.add(key)
            body_lines = lines[index + 1 : index + 7] or [line]
            preview = _truncate(" ".join(body_lines))
            sections.append(
                DocumentSectionRead(
                    heading=heading,
                    page_number=page.page_number,
                    text_preview=preview,
                    intents=sorted(infer_section_intents(heading)),
                )
            )
    return sections


def _sections_from_chunks(document: Document) -> list[DocumentSectionRead]:
    sections: list[DocumentSectionRead] = []
    seen: set[tuple[str, int]] = set()
    for chunk in ordered_chunks(document):
        section = _section_from_chunk(chunk)
        if section is None:
            continue
        key = (section.heading, section.page_number)
        if key in seen:
            continue
        seen.add(key)
        sections.append(section)
    return sections


def extract_sections(document: Document) -> list[DocumentSectionRead]:
    chunk_sections = _sections_from_chunks(document)
    if chunk_sections:
        return chunk_sections[:_MAX_SECTIONS]
    return _sections_from_page_lines(_ordered_pages(document))[:_MAX_SECTIONS]


def infer_document_type(filename: str, text: str, sections: Iterable[DocumentSectionRead]) -> DocumentType:
    searchable_text = f"{filename} {text}".lower()
    scores = Counter({"generic": 1})
    for document_type, keywords in _DOCUMENT_TYPE_KEYWORDS.items():
        for keyword, weight in keywords.items():
            if keyword in searchable_text:
                scores[document_type] += weight

    section_headings = {section.heading for section in sections}
    if {"ABSTRACT", "REFERENCES"}.issubset(section_headings):
        scores["research_paper"] += 5
    if {"TOTAL", "PAYMENT SUMMARY", "INVOICE SUMMARY"}.intersection(section_headings):
        scores["invoice"] += 4
    if {"OBLIGATIONS", "TERMINATION", "PARTIES"}.intersection(section_headings):
        scores["contract"] += 4
    if {"TECHNICAL SKILLS", "CORE SKILLS", "PROJECTS", "EDUCATION"}.intersection(section_headings):
        scores["resume"] += 3
    if {"EXECUTIVE SUMMARY", "FINDINGS", "RECOMMENDATIONS"}.intersection(section_headings):
        scores["report"] += 4

    return scores.most_common(1)[0][0]


def infer_title(document: Document, sections: Iterable[DocumentSectionRead]) -> str | None:
    known_headings = {section.heading for section in sections}.union(_KNOWN_HEADINGS)
    for page in _ordered_pages(document)[:2]:
        for raw_line in page.text.splitlines():
            line = clean_text(raw_line)
            if not line or len(line) > 180:
                continue
            if _canonical_heading(line) in known_headings:
                continue
            if _MONEY_PATTERN.search(line) or line.lower().startswith(("email", "phone", "tel")):
                continue
            return line
    chunks = ordered_chunks(document)
    return _truncate(chunks[0].text, 120) if chunks else None


def _overview(document_type: str, sections: list[DocumentSectionRead], chunks: list[Chunk]) -> str | None:
    preferred_headings = {
        "research_paper": {"ABSTRACT", "INTRODUCTION", "CONCLUSION"},
        "resume": {"PROFESSIONAL SUMMARY", "SUMMARY", "ABOUT ME"},
        "invoice": {"INVOICE", "INVOICE DETAILS", "PAYMENT SUMMARY"},
        "contract": {"AGREEMENT", "PARTIES", "TERMS"},
        "report": {"EXECUTIVE SUMMARY", "OVERVIEW", "FINDINGS"},
    }.get(document_type, {"SUMMARY", "OVERVIEW"})

    for section in sections:
        if section.heading in preferred_headings:
            return section.text_preview
    for chunk in chunks[:2]:
        preview = _truncate(chunk.text)
        if preview:
            return preview
    return None


def _context(text: str, value: str, window: int = 80) -> str:
    index = text.lower().find(value.lower())
    if index < 0:
        return _truncate(text, 160)
    start = max(0, index - window)
    end = min(len(text), index + len(value) + window)
    return _truncate(text[start:end], 180)


def _add_fact(
    facts: list[DocumentFactRead],
    seen: set[tuple[str, str]],
    *,
    kind: str,
    label: str,
    value: str,
    page_number: int,
    source_text: str,
) -> None:
    normalized_value = clean_text(value).strip(" ,;:.")
    if not normalized_value:
        return
    key = (kind, normalized_value.lower())
    if key in seen:
        return
    seen.add(key)
    facts.append(
        DocumentFactRead(
            kind=kind,
            label=label,
            value=normalized_value,
            page_number=page_number,
            source_text=_context(source_text, normalized_value),
        )
    )


def extract_dates(document: Document) -> list[DocumentFactRead]:
    pages = _ordered_pages(document)
    facts: list[DocumentFactRead] = []
    seen: set[tuple[str, str]] = set()
    for page in pages:
        for pattern in _DATE_PATTERNS:
            for match in pattern.finditer(page.text):
                _add_fact(
                    facts,
                    seen,
                    kind="date",
                    label="Date",
                    value=match.group(0),
                    page_number=page.page_number,
                    source_text=page.text,
                )
                if len(facts) >= _MAX_FACTS_PER_GROUP:
                    return facts
    return facts


def extract_numbers(document: Document) -> list[DocumentFactRead]:
    pages = _ordered_pages(document)
    facts: list[DocumentFactRead] = []
    seen: set[tuple[str, str]] = set()
    for page in pages:
        for kind, label, pattern in (
            ("amount", "Amount", _MONEY_PATTERN),
            ("percentage", "Percentage", _PERCENT_PATTERN),
            ("metric", "Metric", _METRIC_PATTERN),
        ):
            for match in pattern.finditer(page.text):
                _add_fact(
                    facts,
                    seen,
                    kind=kind,
                    label=label,
                    value=match.group(0),
                    page_number=page.page_number,
                    source_text=page.text,
                )
                if len(facts) >= _MAX_FACTS_PER_GROUP:
                    return facts
        if _METRIC_CONTEXT_PATTERN.search(page.text):
            for match in _TABLE_NUMBER_PATTERN.finditer(page.text):
                value = match.group(0)
                if len(value) == 4 and value.startswith(("19", "20")):
                    continue
                _add_fact(
                    facts,
                    seen,
                    kind="metric",
                    label="Metric",
                    value=value,
                    page_number=page.page_number,
                    source_text=page.text,
                )
                if len(facts) >= _MAX_FACTS_PER_GROUP:
                    return facts
    return facts


def _entity_candidates(text: str) -> Iterable[tuple[str, str]]:
    for match in _DATASET_PATTERN.finditer(text):
        yield "Dataset", match.group(0)

    for match in _BETWEEN_PARTIES_PATTERN.finditer(text):
        yield "Party", match.group(1)
        yield "Party", match.group(2)

    for pattern in (_BILL_TO_PATTERN, _VENDOR_PATTERN):
        for match in pattern.finditer(text):
            yield "Entity", match.group(1)

    for match in _CAPITALIZED_PHRASE_PATTERN.finditer(text):
        value = match.group(0)
        if _canonical_heading(value) in _KNOWN_HEADINGS:
            continue
        if value.lower() in {"this paper", "this agreement", "due date", "issue date", "total due"}:
            continue
        yield "Entity", value


def extract_entities(document: Document) -> list[DocumentFactRead]:
    pages = _ordered_pages(document)
    facts: list[DocumentFactRead] = []
    seen: set[tuple[str, str]] = set()
    for page in pages:
        for label, value in _entity_candidates(page.text):
            kind = "dataset" if label == "Dataset" else "entity"
            _add_fact(
                facts,
                seen,
                kind=kind,
                label=label,
                value=value,
                page_number=page.page_number,
                source_text=page.text,
            )
            if len(facts) >= _MAX_FACTS_PER_GROUP:
                return facts
    return facts


def build_document_profile(document: Document) -> DocumentProfileRead:
    chunks = ordered_chunks(document)
    sections = extract_sections(document)
    text = _full_text(document)
    document_type = infer_document_type(document.filename, text, sections)
    title = infer_title(document, sections)
    return DocumentProfileRead(
        document_id=document.id,
        filename=document.filename,
        document_type=document_type,
        title=title,
        overview=_overview(document_type, sections, chunks),
        sections=sections,
        key_dates=extract_dates(document),
        key_numbers=extract_numbers(document),
        key_entities=extract_entities(document),
        suggested_questions=_SUGGESTED_QUESTIONS.get(document_type, _SUGGESTED_QUESTIONS["generic"]),
    )
