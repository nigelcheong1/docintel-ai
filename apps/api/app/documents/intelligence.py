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
_DATE_LABELS = (
    ("due date", "Due date"),
    ("payment due", "Due date"),
    ("issue date", "Issue date"),
    ("invoice date", "Issue date"),
    ("effective date", "Effective date"),
    ("deadline", "Deadline"),
    ("expected", "Expected date"),
)
_MONEY_PATTERN = re.compile(r"\b(?:RM|USD|EUR|GBP|MYR|\$|€|£)\s?\d[\d,]*(?:\.\d{2})?\b", re.IGNORECASE)
_AMOUNT_LABELS = (
    ("total due", "Total due"),
    ("amount due", "Total due"),
    ("balance due", "Balance due"),
    ("subtotal", "Subtotal"),
    ("tax", "Tax"),
    ("total", "Total"),
    ("fee", "Fee"),
    ("cost", "Cost"),
)
_PERCENT_PATTERN = re.compile(r"\b\d+(?:\.\d+)?\s?%\b")
_METRIC_PATTERN = re.compile(r"\b(?:TOP1|TOP5|F1|ACC|AUC|MAP|IOU|DICE|RECALL|PRECISION)[\s:=]*\d+(?:\.\d+)?\b", re.IGNORECASE)
_TABLE_NUMBER_PATTERN = re.compile(r"\b\d+(?:\.\d+)?\b")
_METRIC_CONTEXT_PATTERN = re.compile(r"\b(?:TOP1|TOP5|F1|ACC|AUC|MAP|IOU|DICE|RECALL|PRECISION|ACCURACY|TABLE)\b", re.IGNORECASE)
_DATASET_PATTERN = re.compile(
    r"\b(?:Kinetics-400|UCF-101|HMDB-51|MECCANO|InHARD|HRI30|HRI-30|ImageNet|COCO|CIFAR-10|CIFAR-100|MNIST|FUNSD|SQuAD|BraTS\s?2019|PubMed|MIMIC-III|MIMIC-IV)\b",
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
_HEADING_BY_COMPACT = {re.sub(r"[^A-Z0-9]+", "", heading): heading for heading in _KNOWN_HEADINGS}
_SPACED_HEADING_REPLACEMENTS = tuple(
    (
        re.compile(r"\b" + r"\s+".join(re.escape(char) for char in re.sub(r"[^A-Z0-9]+", "", heading)) + r"\b", re.IGNORECASE),
        heading,
    )
    for heading in sorted(_KNOWN_HEADINGS, key=len, reverse=True)
    if len(re.sub(r"[^A-Z0-9]+", "", heading)) >= 4
)
_SECTION_LINE_PATTERN = re.compile(r"^\s*(?:\d+(?:\.\d+)*\.?\s+)?([A-Za-z][A-Za-z &/-]{2,60})\s*:?\s*$")
_ACADEMIC_NUMBERED_HEADING_PATTERN = re.compile(
    r"^\s*(?P<number>\d+(?:\.\d+)*\.)\s*(?P<title>[A-Za-z][A-Za-z0-9 /&,\-–]{2,90})\s*:?\s*$"
)
_ACADEMIC_HEADING_SKIP_PATTERN = re.compile(r"^(?:fig|figure|table)\.?\s+\d+", re.IGNORECASE)
_ACADEMIC_DATASET_TERMS = {"dataset", "datasets", "benchmark", "benchmarks", "corpus"}
_ACADEMIC_METHOD_TERMS = {
    "architecture",
    "attention",
    "encoder",
    "framework",
    "fusion",
    "implementation setting",
    "implementation settings",
    "learning framework",
    "methodology",
    "model",
    "module",
    "pipeline",
    "task formulation",
    "textual supervision",
    "translation",
}
_ACADEMIC_RESULT_TERMS = {
    "ablation",
    "case study",
    "comparison",
    "effectiveness",
    "evaluation",
    "experiment",
    "experiments",
    "finding",
    "findings",
    "performance",
    "result",
    "results",
}
_ACADEMIC_LIMITATION_TERMS = {
    "conclusion",
    "future direction",
    "future directions",
    "future research",
    "future work",
    "limitation",
    "limitations",
}
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")
_RESEARCH_CONTENT_HEADINGS = {
    "ABSTRACT",
    "INTRODUCTION",
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
    "DATASET",
    "DATASETS",
}
_RESEARCH_BOILERPLATE_PATTERNS = (
    re.compile(r"\bcontents lists available at sciencedirect\b", re.IGNORECASE),
    re.compile(r"\bjournal homepage\s*:?\s*\S+", re.IGNORECASE),
    re.compile(r"\bwww\.elsevier\.com/\S+", re.IGNORECASE),
    re.compile(r"\ball rights are reserved[^.]*\.?", re.IGNORECASE),
    re.compile(r"\btext and data mining[^.]*\.?", re.IGNORECASE),
    re.compile(r"\bai training,? and similar technologies[^.]*\.?", re.IGNORECASE),
    re.compile(r"\bavailable online\s+\d{1,2}\s+[A-Za-z]+\s+\d{4}\b", re.IGNORECASE),
    re.compile(r"\breceived\s+\d{1,2}\s+[A-Za-z]+\s+\d{4}\b", re.IGNORECASE),
    re.compile(r"\brevised\s+\d{1,2}\s+[A-Za-z]+\s+\d{4}\b", re.IGNORECASE),
    re.compile(r"\baccepted\s+\d{1,2}\s+[A-Za-z]+\s+\d{4}\b", re.IGNORECASE),
    re.compile(r"\*?\s*corresponding author[^.]*\.?", re.IGNORECASE),
)
_RESEARCH_NOISE_LINE_PATTERNS = (
    re.compile(r"^journal of\b", re.IGNORECASE),
    re.compile(r"^technical paper$", re.IGNORECASE),
    re.compile(r"^research article$", re.IGNORECASE),
    re.compile(r"^article info$", re.IGNORECASE),
    re.compile(r"^credit authorship contribution statement\b", re.IGNORECASE),
    re.compile(r"^declaration of competing interest\b", re.IGNORECASE),
    re.compile(r"^acknowledgments?\b", re.IGNORECASE),
    re.compile(r"^data availability\b", re.IGNORECASE),
    re.compile(r"^school of\b", re.IGNORECASE),
    re.compile(r"^state key laboratory\b", re.IGNORECASE),
    re.compile(r"\b[a-z]\s+school of\b", re.IGNORECASE),
)
_RESEARCH_AUTHOR_LINE_PATTERN = re.compile(r"\b[a-z],[a-z]\b|\bet al\.?\b", re.IGNORECASE)
_RESEARCH_POSTAL_OR_INDUSTRY_NUMBER_CONTEXT = re.compile(
    r"\b(?:shanghai|beijing|china|malaysia|industry\s+4\.0|industry\s+5\.0)\b",
    re.IGNORECASE,
)
_RESEARCH_LOCATION_CONTEXT = re.compile(r"\b(?:shanghai|beijing|china|malaysia)\b", re.IGNORECASE)
_RESEARCH_CONTRIBUTION_PATTERN = re.compile(
    r"\b(?:this paper|we)\s+(?:propose|proposes|present|presents|introduce|introduces|develop|develops)\b",
    re.IGNORECASE,
)
_RESEARCH_TABLE_SIGNAL_PATTERN = re.compile(
    r"\b(?:TOP1|TOP5|Avg\s+acc|Avg\s+pre|Avg\s+recall|F1\s+score|Pretrain|Train/Val/Test|Classes\s+Videos|Table\s+\d+)\b",
    re.IGNORECASE,
)
_RESEARCH_METHOD_PROSE_TERMS = {
    "approach",
    "architecture",
    "attention",
    "encoder",
    "fine-tuning",
    "framework",
    "fusion",
    "model",
    "module",
    "pipeline",
    "proposed",
    "temporal",
    "token",
    "transformer",
    "visual",
}
_RESEARCH_METHOD_TABLE_PENALTIES = {
    "avg acc",
    "baseline comparison",
    "comparison with sota",
    "method pretrain",
    "pretrain top1",
    "table",
    "top1",
    "top5",
}
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


def normalize_spaced_headings(text: str) -> str:
    normalized = text
    for pattern, heading in _SPACED_HEADING_REPLACEMENTS:
        normalized = pattern.sub(heading, normalized)
    return normalized


def clean_text(text: str) -> str:
    dehyphenated = re.sub(r"(?<=\w)-\s+(?=\w)", "", normalize_spaced_headings(text))
    return " ".join(dehyphenated.split())


def strip_leading_heading(text: str, heading: str | None) -> str:
    cleaned = clean_text(text)
    if not heading:
        return cleaned
    pattern = re.compile(rf"^\s*{re.escape(heading)}\s*[:.-]?\s*", re.IGNORECASE)
    stripped = pattern.sub("", cleaned, count=1).strip()
    return stripped or cleaned


def research_text_after_heading(text: str, heading: str | None) -> str:
    cleaned = clean_text(text)
    if heading:
        pattern = re.compile(rf"\b{re.escape(heading)}\b\s*[:.-]?\s*", re.IGNORECASE)
        match = pattern.search(cleaned)
        if match is not None:
            cleaned = cleaned[match.end() :].strip()
    return cleaned


def is_research_noise_line(line: str) -> bool:
    cleaned = clean_text(line)
    if not cleaned:
        return True
    return any(pattern.search(cleaned) for pattern in _RESEARCH_NOISE_LINE_PATTERNS) or any(
        pattern.search(cleaned) for pattern in _RESEARCH_BOILERPLATE_PATTERNS
    )


def _looks_like_research_location_metadata(line: str) -> bool:
    return bool(re.search(r"\b\d{5,}\b", line) and _RESEARCH_LOCATION_CONTEXT.search(line))


def clean_research_text(text: str) -> str:
    cleaned = normalize_spaced_headings(text)
    for pattern in _RESEARCH_BOILERPLATE_PATTERNS:
        cleaned = pattern.sub(" ", cleaned)
    cleaned = re.sub(r"\btechnical paper\s+(?=[A-Z0-9])", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bjournal of manufacturing systems\b", " ", cleaned, flags=re.IGNORECASE)
    return clean_text(cleaned)


def is_research_table_like_text(text: str) -> bool:
    cleaned = clean_research_text(text)
    if not cleaned:
        return False
    numeric_values = re.findall(r"\b\d+(?:\.\d+)?\b", cleaned)
    if re.search(r"^(?:method\s+)?(?:pretrain\s+)?TOP1\s*\(%\)\s+TOP5", cleaned, re.IGNORECASE):
        return True
    return bool(_RESEARCH_TABLE_SIGNAL_PATTERN.search(cleaned) and len(numeric_values) >= 2)


def is_research_noise_sentence(sentence: str) -> bool:
    cleaned = clean_research_text(sentence).strip()
    if not cleaned:
        return True
    words = cleaned.split()
    if len(words) < 5:
        return True
    if re.fullmatch(r"(?:[A-Z]\.\s*)+", cleaned):
        return True
    if _RESEARCH_AUTHOR_LINE_PATTERN.search(cleaned) and not _RESEARCH_CONTRIBUTION_PATTERN.search(cleaned):
        return True
    return is_research_noise_line(cleaned)


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
    compact = re.sub(r"[^A-Z0-9]+", "", normalized)
    return _HEADING_BY_NORMALIZED.get(normalized, _HEADING_BY_COMPACT.get(compact, normalized))


def _academic_heading_alias(line: str) -> str | None:
    normalized_line = clean_text(line)
    if not normalized_line or len(normalized_line) > 110:
        return None
    if _ACADEMIC_HEADING_SKIP_PATTERN.match(normalized_line):
        return None

    number_match = _ACADEMIC_NUMBERED_HEADING_PATTERN.match(normalized_line)
    if number_match is None:
        return None

    title = number_match.group("title") if number_match else normalized_line
    normalized_title = re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()
    title_words = normalized_title.split()
    words = set(title_words)
    major_section = number_match.group("number").split(".")[0] if number_match else None

    if words.intersection(_ACADEMIC_DATASET_TERMS):
        return "DATASET"
    if words.intersection(_ACADEMIC_LIMITATION_TERMS) or any(
        term in normalized_title for term in _ACADEMIC_LIMITATION_TERMS
    ):
        return "FUTURE WORK" if "future" in normalized_title else "CONCLUSION"
    if "implementation setting" in normalized_title:
        return "METHOD"
    if major_section == "3":
        return "METHOD"
    if major_section == "4":
        return "RESULTS"
    if any(term in normalized_title for term in _ACADEMIC_METHOD_TERMS):
        return "METHOD"
    if any(term in normalized_title for term in _ACADEMIC_RESULT_TERMS):
        return "RESULTS"
    return None


def _line_heading(line: str) -> str | None:
    normalized_line = normalize_spaced_headings(line).strip()
    match = _SECTION_LINE_PATTERN.match(normalized_line)
    if match is not None:
        heading = _canonical_heading(match.group(1))
        if heading in _KNOWN_HEADINGS:
            return heading
    return _academic_heading_alias(normalized_line)


def _section_from_chunk(chunk: Chunk) -> DocumentSectionRead | None:
    heading = chunk_heading(chunk)
    if heading is None:
        return None
    if heading in {"METHOD", "METHODS"} and is_research_table_like_text(chunk.text):
        return None
    preview_text = strip_leading_heading(chunk.text, heading)
    if heading in _RESEARCH_CONTENT_HEADINGS:
        preview_text = clean_research_text(research_text_after_heading(chunk.text, heading))
    return DocumentSectionRead(
        heading=heading,
        page_number=chunk.page.page_number,
        text_preview=_truncate(preview_text),
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
            body_lines: list[str] = []
            for body_line in lines[index + 1 :]:
                if _line_heading(body_line) in _KNOWN_HEADINGS:
                    break
                body_lines.append(body_line)
                if len(body_lines) >= 6:
                    break
            body_lines = body_lines or [line]
            preview_text = " ".join(body_lines)
            if heading in {"METHOD", "METHODS"} and is_research_table_like_text(preview_text):
                continue
            if heading in _RESEARCH_CONTENT_HEADINGS:
                preview_text = clean_research_text(preview_text)
            preview = _truncate(preview_text)
            sections.append(
                DocumentSectionRead(
                    heading=heading,
                    page_number=page.page_number,
                    text_preview=preview,
                    intents=sorted(infer_section_intents(heading)),
                )
            )
    return sections


def _merge_sections(*section_groups: Iterable[DocumentSectionRead]) -> list[DocumentSectionRead]:
    sections: list[DocumentSectionRead] = []
    seen: set[tuple[str, int]] = set()
    for group in section_groups:
        for section in group:
            key = (section.heading, section.page_number)
            if key in seen:
                continue
            seen.add(key)
            sections.append(section)
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
    line_sections = _sections_from_page_lines(_ordered_pages(document))
    return _merge_sections(line_sections, chunk_sections)[:_MAX_SECTIONS]


def infer_document_type(filename: str, text: str, sections: Iterable[DocumentSectionRead]) -> DocumentType:
    searchable_text = f"{filename} {text}".lower()
    scores = Counter({"generic": 1})
    for document_type, keywords in _DOCUMENT_TYPE_KEYWORDS.items():
        for keyword, weight in keywords.items():
            if keyword in searchable_text:
                scores[document_type] += weight

    section_headings = {section.heading for section in sections}
    if "ABSTRACT" in section_headings:
        scores["research_paper"] += 4
    if "KEYWORDS" in section_headings:
        scores["research_paper"] += 2
    if len(section_headings.intersection(_RESEARCH_CONTENT_HEADINGS)) >= 2:
        scores["research_paper"] += 3
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


def _research_title_candidate(line: str) -> str | None:
    cleaned = clean_research_text(line).strip(" .")
    cleaned = re.sub(r"^(?:technical paper|research article|article)\s+", "", cleaned, flags=re.IGNORECASE).strip(" .")
    if not cleaned:
        return None
    if is_research_noise_line(cleaned):
        return None
    if _RESEARCH_AUTHOR_LINE_PATTERN.search(cleaned):
        return None
    if _looks_like_research_location_metadata(cleaned):
        return None
    if len(cleaned.split()) < 4 and ":" not in cleaned:
        return None
    return cleaned


def _research_title_continuation(line: str) -> str | None:
    cleaned = clean_research_text(line).strip(" .")
    if not cleaned:
        return None
    if _canonical_heading(cleaned) in _KNOWN_HEADINGS:
        return None
    if is_research_noise_line(cleaned):
        return None
    if _RESEARCH_AUTHOR_LINE_PATTERN.search(cleaned):
        return None
    if _looks_like_research_location_metadata(cleaned):
        return None
    if len(cleaned) > 120:
        return None
    return cleaned


def infer_title(document: Document, sections: Iterable[DocumentSectionRead], document_type: str | None = None) -> str | None:
    known_headings = {section.heading for section in sections}.union(_KNOWN_HEADINGS)
    for page in _ordered_pages(document)[:2]:
        raw_lines = page.text.splitlines()
        for index, raw_line in enumerate(raw_lines):
            line = clean_text(raw_line)
            if not line or len(line) > 180:
                continue
            if _canonical_heading(line) in known_headings:
                continue
            if document_type == "research_paper":
                candidate = _research_title_candidate(line)
                if candidate is None:
                    continue
                title_parts = [candidate]
                for continuation_line in raw_lines[index + 1 : index + 4]:
                    continuation = _research_title_continuation(continuation_line)
                    if continuation is None:
                        break
                    title_parts.append(continuation)
                    if len(" ".join(title_parts)) >= 160:
                        break
                return clean_text(" ".join(title_parts))
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
            preview = clean_research_text(section.text_preview) if document_type == "research_paper" else section.text_preview
            if preview:
                return preview
    for chunk in chunks[:2]:
        preview_text = clean_research_text(chunk.text) if document_type == "research_paper" else chunk.text
        preview = _truncate(preview_text)
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


def _research_sentence_candidates(text: str) -> list[str]:
    cleaned = clean_research_text(text)
    return [
        sentence
        for sentence in (sentence.strip() for sentence in _SENTENCE_BOUNDARY.split(cleaned))
        if sentence and not is_research_noise_sentence(sentence)
    ]


def _research_chunks(document: Document) -> Iterable[Chunk]:
    for chunk in ordered_chunks(document):
        heading = chunk_heading(chunk)
        if heading == "REFERENCES":
            continue
        yield chunk


def _add_research_section_fact(
    facts: list[DocumentFactRead],
    seen: set[tuple[str, str]],
    *,
    document: Document,
    headings: set[str],
    label: str,
    kind: str,
    terms: set[str],
    allow_unheaded_terms: bool = False,
    exclude_table_like: bool = False,
) -> None:
    candidates: list[tuple[int, int, str, Chunk]] = []
    for chunk in _research_chunks(document):
        heading = chunk_heading(chunk)
        text = research_text_after_heading(chunk.text, heading)
        normalized_text = clean_research_text(text).lower()
        heading_match = heading in headings
        if not heading_match:
            if not allow_unheaded_terms or heading is not None:
                continue
            if not any(term in normalized_text for term in terms):
                continue
        if exclude_table_like and is_research_table_like_text(text):
            continue
        sentences = _research_sentence_candidates(text)
        if not sentences:
            continue
        for sentence_index, sentence in enumerate(sentences):
            lower_sentence = sentence.lower()
            if exclude_table_like and is_research_table_like_text(sentence):
                continue
            score = 5 if heading_match else 0
            score += 3 if any(term in lower_sentence for term in terms) else 0
            if label == "Method":
                score += sum(1 for term in _RESEARCH_METHOD_PROSE_TERMS if term in lower_sentence)
                score -= 3 * sum(1 for term in _RESEARCH_METHOD_TABLE_PENALTIES if term in lower_sentence)
            score += min(len(sentence.split()), 36)
            candidates.append((score, -sentence_index, sentence, chunk))
    if candidates:
        _score, _sentence_index, selected, chunk = max(candidates, key=lambda item: (item[0], item[1]))
        _add_fact(
            facts,
            seen,
            kind=kind,
            label=label,
            value=selected,
            page_number=chunk.page.page_number,
            source_text=chunk.text,
        )


def _extract_research_entities(document: Document) -> list[DocumentFactRead]:
    facts: list[DocumentFactRead] = []
    seen: set[tuple[str, str]] = set()
    for chunk in _research_chunks(document):
        text = clean_research_text(chunk.text)
        for match in _DATASET_PATTERN.finditer(text):
            _add_fact(
                facts,
                seen,
                kind="dataset",
                label="Dataset",
                value=match.group(0),
                page_number=chunk.page.page_number,
                source_text=chunk.text,
            )
            if len(facts) >= _MAX_FACTS_PER_GROUP:
                return facts

    _add_research_section_fact(
        facts,
        seen,
        document=document,
        headings={"ABSTRACT", "INTRODUCTION"},
        label="Contribution",
        kind="research_contribution",
        terms={"propose", "proposes", "present", "presents", "introduce", "introduces", "develop", "develops"},
    )
    _add_research_section_fact(
        facts,
        seen,
        document=document,
        headings={"METHODOLOGY", "METHOD", "METHODS", "APPROACH", "MODEL"},
        label="Method",
        kind="research_method",
        terms={
            "approach",
            "architecture",
            "attention",
            "encoder",
            "framework",
            "fusion",
            "method",
            "model",
            "module",
            "pipeline",
            "proposed",
            "temporal",
            "transformer",
            "visual",
        },
        allow_unheaded_terms=True,
        exclude_table_like=True,
    )
    _add_research_section_fact(
        facts,
        seen,
        document=document,
        headings={"RESULT", "RESULTS", "EVALUATION", "EXPERIMENT", "EXPERIMENTS"},
        label="Result",
        kind="research_result",
        terms={"achieve", "achieves", "result", "results", "accuracy", "top1", "top5", "f1"},
    )
    return facts[:_MAX_FACTS_PER_GROUP]


def _label_from_context(text: str, match_start: int, labels: tuple[tuple[str, str], ...], default: str) -> str:
    prefix = clean_text(text[max(0, match_start - 90) : match_start]).lower()
    best_label = default
    best_index = -1
    for marker, label in labels:
        marker_index = prefix.rfind(marker)
        if marker_index > best_index:
            best_label = label
            best_index = marker_index
    return best_label


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


def extract_dates(document: Document, document_type: str | None = None) -> list[DocumentFactRead]:
    if document_type == "research_paper":
        return []
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
                    label=_label_from_context(page.text, match.start(), _DATE_LABELS, "Date"),
                    value=match.group(0),
                    page_number=page.page_number,
                    source_text=page.text,
                )
                if len(facts) >= _MAX_FACTS_PER_GROUP:
                    return facts
    return facts


def _is_research_noise_number(value: str, source_text: str, match_start: int | None = None) -> bool:
    nearby = source_text[max(0, match_start - 32) : match_start + len(value) + 32].lower() if match_start is not None else source_text.lower()
    if "doi" in nearby or "http" in nearby or "www." in nearby:
        return True
    if re.fullmatch(r"\d+\.\d+", value) and float(value) < 10:
        return True
    if re.fullmatch(r"\d+\.\d+", value) and float(value) < 10 and re.search(
        rf"\b{re.escape(value)}\s+[A-Z][A-Za-z-]+",
        source_text[max(0, (match_start or 0) - 8) : (match_start or 0) + len(value) + 32],
    ):
        return True
    if value.isdigit() and (len(value) >= 5 or int(value) < 10):
        return True
    if value in {"4.0", "5.0"} and _RESEARCH_POSTAL_OR_INDUSTRY_NUMBER_CONTEXT.search(source_text):
        return True
    if len(value) == 4 and value.startswith(("19", "20")):
        return True
    return False


def _extract_research_numbers(document: Document) -> list[DocumentFactRead]:
    facts: list[DocumentFactRead] = []
    seen: set[tuple[str, str]] = set()
    for chunk in _research_chunks(document):
        heading = chunk_heading(chunk)
        text = clean_research_text(chunk.text)
        if heading not in {"RESULT", "RESULTS", "EVALUATION", "EXPERIMENT", "EXPERIMENTS", "DATASET", "DATASETS"} and not _METRIC_CONTEXT_PATTERN.search(text):
            continue
        metric_spans: list[tuple[int, int]] = []
        for match in _METRIC_PATTERN.finditer(text):
            metric_spans.append(match.span())
            _add_fact(
                facts,
                seen,
                kind="metric",
                label="Metric",
                value=match.group(0),
                page_number=chunk.page.page_number,
                source_text=chunk.text,
            )
            if len(facts) >= _MAX_FACTS_PER_GROUP:
                return facts
        if _METRIC_CONTEXT_PATTERN.search(text):
            for match in _TABLE_NUMBER_PATTERN.finditer(text):
                value = match.group(0)
                if any(start <= match.start() and match.end() <= end for start, end in metric_spans):
                    continue
                if "." not in value or _is_research_noise_number(value, text, match.start()):
                    continue
                _add_fact(
                    facts,
                    seen,
                    kind="metric",
                    label="Metric",
                    value=value,
                    page_number=chunk.page.page_number,
                    source_text=chunk.text,
                )
                if len(facts) >= _MAX_FACTS_PER_GROUP:
                    return facts
    return facts


def extract_numbers(document: Document, document_type: str | None = None) -> list[DocumentFactRead]:
    if document_type == "research_paper":
        return _extract_research_numbers(document)
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
                fact_label = (
                    _label_from_context(page.text, match.start(), _AMOUNT_LABELS, label)
                    if kind == "amount"
                    else label
                )
                _add_fact(
                    facts,
                    seen,
                    kind=kind,
                    label=fact_label,
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


def extract_entities(document: Document, document_type: str | None = None) -> list[DocumentFactRead]:
    if document_type == "research_paper":
        return _extract_research_entities(document)
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
    title = infer_title(document, sections, document_type)
    return DocumentProfileRead(
        document_id=document.id,
        filename=document.filename,
        document_type=document_type,
        title=title,
        overview=_overview(document_type, sections, chunks),
        sections=sections,
        key_dates=extract_dates(document, document_type),
        key_numbers=extract_numbers(document, document_type),
        key_entities=extract_entities(document, document_type),
        suggested_questions=_SUGGESTED_QUESTIONS.get(document_type, _SUGGESTED_QUESTIONS["generic"]),
    )
