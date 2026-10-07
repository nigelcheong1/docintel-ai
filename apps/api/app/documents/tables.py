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
    text: str = ""


def _split_columns(line: str) -> list[str]:
    if "\t" in line:
        return [cell.strip() for cell in line.split("\t")]
    if "|" in line:
        return [cell.strip() for cell in line.strip("|").split("|")]
    return []


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

            body: list[str] = []
            for candidate in lines[index + 1 :]:
                if candidate.lower().startswith("table ") or (body and candidate.isupper() and not _is_table_row(candidate)):
                    break
                body.append(candidate)
            labels = _split_columns(body[0]) if body else []
            rows: list[DetectedTableRow] = []
            for candidate in body[1:] if labels else body:
                if not _is_table_row(candidate):
                    continue
                columns = _split_columns(candidate)
                if labels and len(columns) == len(labels):
                    rows.append(DetectedTableRow(len(rows), [
                        DetectedTableCell(column_index, text, labels[column_index])
                        for column_index, text in enumerate(columns)
                    ]))
                elif not labels:
                    rows.append(_parse_table_row(len(rows), candidate))
            tables.append(DetectedTable(
                page_number=page.page_number,
                caption=line,
                rows=rows,
                extraction_confidence="moderate" if labels and rows else "low",
                text="\n".join([line, *body]),
            ))
    return tables
