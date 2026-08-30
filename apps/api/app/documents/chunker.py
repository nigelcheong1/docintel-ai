from collections.abc import Sequence
from dataclasses import dataclass
import re

from app.documents.parser import ParsedPage

_SECTION_HEADINGS = (
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
)
_HEADING_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])("
    + "|".join(re.escape(heading) for heading in sorted(_SECTION_HEADINGS, key=len, reverse=True))
    + r")(?![A-Za-z0-9])",
    re.IGNORECASE,
)
_STANDALONE_HEADING_PATTERN = re.compile(
    r"^\s*(?:[-*#]+\s*)?(?:\d+(?:\.\d+)*\.?\s*)?("
    + "|".join(re.escape(heading) for heading in sorted(_SECTION_HEADINGS, key=len, reverse=True))
    + r")\s*:?\s*$",
    re.IGNORECASE,
)
_SINGLE_WORD_HEADINGS = {heading for heading in _SECTION_HEADINGS if " " not in heading}
_HEADING_BY_NORMALIZED = {re.sub(r"[^A-Z0-9]+", " ", heading).strip(): heading for heading in _SECTION_HEADINGS}
_HEADING_BY_COMPACT = {re.sub(r"[^A-Z0-9]+", "", heading): heading for heading in _SECTION_HEADINGS}
_SPACED_HEADING_REPLACEMENTS = tuple(
    (
        re.compile(r"\b" + r"\s+".join(re.escape(char) for char in re.sub(r"[^A-Z0-9]+", "", heading)) + r"\b", re.IGNORECASE),
        heading,
    )
    for heading in sorted(_SECTION_HEADINGS, key=len, reverse=True)
    if len(re.sub(r"[^A-Z0-9]+", "", heading)) >= 4
)
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


@dataclass(frozen=True)
class TextChunk:
    page_number: int
    chunk_index: int
    text: str
    token_estimate: int
    layout: dict[str, object]


@dataclass(frozen=True)
class _Section:
    text: str
    word_start: int
    heading: str | None = None


def _normalize_text(text: str) -> str:
    normalized = text
    for pattern, heading in _SPACED_HEADING_REPLACEMENTS:
        normalized = pattern.sub(heading, normalized)
    return " ".join(normalized.split())


def _canonical_heading(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9]+", " ", _normalize_text(value)).strip().upper()
    compact = re.sub(r"[^A-Z0-9]+", "", normalized)
    return _HEADING_BY_NORMALIZED.get(normalized, _HEADING_BY_COMPACT.get(compact, normalized))


def _academic_heading_alias(line: str) -> str | None:
    normalized_line = _normalize_text(line).strip()
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


def _is_uppercase_heading(candidate: str) -> bool:
    return candidate == candidate.upper()


def _is_heading_case(candidate: str, canonical_heading: str, allow_title_case: bool) -> bool:
    if _is_uppercase_heading(candidate):
        return True
    if canonical_heading in _SINGLE_WORD_HEADINGS:
        return False
    if not allow_title_case:
        return False
    words = [word for word in re.split(r"[\s&]+", candidate) if word]
    return all(word[0].isupper() for word in words)


def _section_heading_matches(text: str, allow_title_case: bool) -> list[re.Match[str]]:
    matches: list[re.Match[str]] = []
    for match in _HEADING_PATTERN.finditer(text):
        heading = _canonical_heading(match.group(1))
        if _is_heading_case(match.group(1), heading, allow_title_case):
            matches.append(match)
    return matches


def _standalone_heading_for_line(line: str) -> str | None:
    match = _STANDALONE_HEADING_PATTERN.match(line)
    if match is not None:
        return _canonical_heading(match.group(1))
    return _academic_heading_alias(line)


def _split_by_standalone_heading_lines(text: str) -> list[_Section]:
    sections: list[_Section] = []
    current_lines: list[str] = []
    current_heading: str | None = None
    current_word_start = 0
    heading_found = False
    words_seen = 0

    def flush_section() -> None:
        if not current_lines:
            return
        section_text = _normalize_text(" ".join(current_lines))
        if section_text:
            sections.append(
                _Section(
                    text=section_text,
                    word_start=current_word_start,
                    heading=current_heading,
                )
            )

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        heading = _standalone_heading_for_line(line)
        if heading is not None:
            heading_found = True
            flush_section()
            current_lines = [line.rstrip(":")]
            current_heading = heading
            current_word_start = words_seen
        else:
            if not current_lines:
                current_word_start = words_seen
            current_lines.append(line)

        words_seen += len(line.split())

    flush_section()
    return sections if heading_found else []


def _split_inline_sections(normalized_text: str, allow_title_case: bool) -> list[_Section]:
    matches = _section_heading_matches(normalized_text, allow_title_case)
    if not matches:
        return []

    sections: list[_Section] = []
    first_start = matches[0].start()
    if first_start > 0:
        intro_text = normalized_text[:first_start].strip()
        if intro_text:
            sections.append(_Section(text=intro_text, word_start=0))

    for index, match in enumerate(matches):
        next_start = matches[index + 1].start() if index + 1 < len(matches) else len(normalized_text)
        section_text = normalized_text[match.start() : next_start].strip()
        if not section_text:
            continue
        word_start = len(normalized_text[: match.start()].split())
        sections.append(
            _Section(
                text=section_text,
                word_start=word_start,
                heading=_canonical_heading(match.group(1)),
            )
        )

    return sections


def _refine_line_sections(line_sections: Sequence[_Section]) -> list[_Section]:
    refined_sections: list[_Section] = []
    for section in line_sections:
        inline_sections = _split_inline_sections(section.text, allow_title_case=True)
        if not inline_sections:
            refined_sections.append(section)
            continue

        for index, inline_section in enumerate(inline_sections):
            refined_sections.append(
                _Section(
                    text=inline_section.text,
                    word_start=section.word_start + inline_section.word_start,
                    heading=inline_section.heading or (section.heading if index == 0 else None),
                )
            )

    return refined_sections


def _split_into_sections(text: str) -> list[_Section]:
    line_sections = _split_by_standalone_heading_lines(text)
    if line_sections:
        return _refine_line_sections(line_sections)

    normalized_text = _normalize_text(text)
    if not normalized_text:
        return []

    uppercase_heading_count = sum(
        1 for match in _HEADING_PATTERN.finditer(normalized_text) if _is_uppercase_heading(match.group(1))
    )
    inline_sections = _split_inline_sections(
        normalized_text,
        allow_title_case=uppercase_heading_count >= 2,
    )
    return inline_sections or [_Section(text=normalized_text, word_start=0)]


def chunk_pages(
    pages: Sequence[ParsedPage], chunk_size: int = 900, overlap: int = 120
) -> list[TextChunk]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero.")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError(
            "overlap must be greater than or equal to zero and smaller than chunk_size."
        )

    chunks: list[TextChunk] = []
    chunk_index = 0
    step = chunk_size - overlap

    for page in pages:
        sections = _split_into_sections(page.text)

        for section in sections:
            words = section.text.split()
            for start in range(0, len(words), step):
                window = words[start : start + chunk_size]
                if not window:
                    continue
                word_start = section.word_start + start
                layout: dict[str, object] = {
                    "source": "pymupdf",
                    "page_width": page.width,
                    "page_height": page.height,
                    "word_start": word_start,
                    "word_end": word_start + len(window),
                }
                if section.heading:
                    layout["section_heading"] = section.heading
                chunks.append(
                    TextChunk(
                        page_number=page.page_number,
                        chunk_index=chunk_index,
                        text=" ".join(window),
                        token_estimate=len(window),
                        layout=layout,
                    )
                )
                chunk_index += 1

    return chunks
