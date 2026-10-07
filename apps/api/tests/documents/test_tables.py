from app.documents.extraction import ExtractedPage
from app.documents.tables import detect_tables


def test_detect_tables_extracts_rows_and_cells_from_text_table():
    check = "\u221a"
    page = ExtractedPage(
        page_number=10,
        text=(
            "Table 4 Key literature review\n"
            "Reference Year Task planning Environmental perception Embodied execution\n"
            f"Chen et al. 2026 {check} {check} {check}\n"
            f"Lou et al. 2025 {check}  {check}\n"
        ),
        width=612,
        height=792,
        text_source="native",
    )

    tables = detect_tables([page])

    assert len(tables) == 1
    assert tables[0].caption == "Table 4 Key literature review"
    assert tables[0].page_number == 10
    assert tables[0].rows[0].cells[0].text == "Chen et al."
    assert any(cell.text == "2026" for cell in tables[0].rows[0].cells)


def test_detect_tables_retains_all_delimited_rows_and_column_labels():
    rows = "\n".join(f"Method {i}\t{2020 + i}\t{i}%" for i in range(10))
    page = ExtractedPage(1, "Table 1 Results\nMethod\tYear\tAccuracy\n" + rows, 612, 792, "native")

    table = detect_tables([page])[0]

    assert len(table.rows) == 10
    assert table.rows[0].cells[2].column_label == "Accuracy"
    assert table.rows[-1].cells[0].text == "Method 9"


def test_detect_tables_preserves_uncertain_text_without_guessing_cells():
    page = ExtractedPage(1, "Table 2 Results\nUnreadable columns\nSymbols cannot be aligned", 612, 792, "native")

    table = detect_tables([page])[0]

    assert table.extraction_confidence == "low"
    assert "Symbols cannot be aligned" in table.text


def test_table_source_chunk_points_to_table_instead_of_page_introduction():
    from app.db.models import Chunk, Page
    from app.documents.service import _first_chunk_for_page

    page = Page(id="page-1", page_number=1, text="")
    introduction = Chunk(id="intro", page_id=page.id, text="Introduction to robot learning.")
    table = Chunk(id="table", page_id=page.id, text="Table 1 Results Method A 2026 90%")

    assert _first_chunk_for_page([introduction, table], page, "Table 1 Results").id == "table"
