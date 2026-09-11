from __future__ import annotations

import re
from dataclasses import dataclass

from app.documents.extraction import ExtractedPage

_YEAR_PATTERN = re.compile(r"^(?:19|20)\d{2}$")
_NUMBER_PATTERN = re.compile(r"^\d+(?:[.,]\d+)*%?$")
_CHECK_PATTERN = re.compile(r"^[\u221a\u2713\u2714xX-]+$")


@dataclass(frozen=True)
class DetectedTableCell:
    column_index: int
    text: str
    column_label: str | None = None


@dataclass(frozen=True)
class DetectedTableRow:
    row_index: int
    cells: list[DetectedTableCell]


@dataclass(frozen=True)
class DetectedTable:
    page_number: int
    caption: str
    rows: list[DetectedTableRow]
    extraction_confidence: str


def _is_cell_boundary_token(token: str) -> bool:
    stripped = token.strip(";,")
    return bool(_YEAR_PATTERN.match(stripped) or _NUMBER_PATTERN.match(stripped) or _CHECK_PATTERN.match(stripped))


def _is_table_row(line: str) -> bool:
    tokens = line.split()
    if len(tokens) < 3:
        return False
    return any(_is_cell_boundary_token(token) for token in tokens)


def _parse_table_row(row_index: int, line: str) -> DetectedTableRow:
    cells: list[str] = []
    leading_text: list[str] = []

    for token in line.split():
        stripped = token.strip(";,")
        if _is_cell_boundary_token(stripped):
            if leading_text:
                cells.append(" ".join(leading_text).strip())
                leading_text = []
            cells.append(stripped)
        else:
            leading_text.append(stripped)

    if leading_text:
        cells.append(" ".join(leading_text).strip())

    return DetectedTableRow(
        row_index=row_index,
        cells=[
            DetectedTableCell(column_index=column_index, text=text)
            for column_index, text in enumerate(cells)
            if text
        ],
    )


def detect_tables(pages: list[ExtractedPage]) -> list[DetectedTable]:
    tables: list[DetectedTable] = []
    for page in pages:
        lines = [line.strip() for line in page.text.splitlines() if line.strip()]
        for index, line in enumerate(lines):
            if not line.lower().startswith("table "):
                continue

            body = lines[index + 1 : index + 8]
            rows = [
                _parse_table_row(row_index, row)
                for row_index, row in enumerate(body)
                if _is_table_row(row)
            ]
            rows = [row for row in rows if row.cells]
            if rows:
                tables.append(
                    DetectedTable(
                        page_number=page.page_number,
                        caption=line,
                        rows=rows,
                        extraction_confidence="moderate",
                    )
                )
    return tables
