from collections.abc import Sequence
from dataclasses import dataclass
import re

from app.documents.parser import ParsedPage

_SECTION_HEADINGS = (
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
)
_HEADING_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])("
    + "|".join(re.escape(heading) for heading in sorted(_SECTION_HEADINGS, key=len, reverse=True))
    + r")(?![A-Za-z0-9])",
    re.IGNORECASE,
)
_STANDALONE_HEADING_PATTERN = re.compile(
    r"^\s*(?:[-*#]+\s*)?("
    + "|".join(re.escape(heading) for heading in sorted(_SECTION_HEADINGS, key=len, reverse=True))
    + r")\s*:?\s*$",
    re.IGNORECASE,
)
_SINGLE_WORD_HEADINGS = {heading for heading in _SECTION_HEADINGS if " " not in heading}


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
    return " ".join(text.split())


def _canonical_heading(value: str) -> str:
    normalized = _normalize_text(value).upper()
    for heading in _SECTION_HEADINGS:
        if normalized == heading.upper():
            return heading.upper()
    return normalized


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
    if match is None:
        return None
    return _canonical_heading(match.group(1))


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
