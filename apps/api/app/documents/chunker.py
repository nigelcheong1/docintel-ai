from collections.abc import Sequence
from dataclasses import dataclass

from app.documents.parser import ParsedPage


@dataclass(frozen=True)
class TextChunk:
    page_number: int
    chunk_index: int
    text: str
    token_estimate: int
    layout: dict[str, object]


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
        words = page.text.split()
        if not words:
            continue

        for start in range(0, len(words), step):
            window = words[start : start + chunk_size]
            if not window:
                continue
            text = " ".join(window)
            chunks.append(
                TextChunk(
                    page_number=page.page_number,
                    chunk_index=chunk_index,
                    text=text,
                    token_estimate=len(window),
                    layout={
                        "source": "pymupdf",
                        "page_width": page.width,
                        "page_height": page.height,
                        "word_start": start,
                        "word_end": start + len(window),
                    },
                )
            )
            chunk_index += 1

    return chunks
