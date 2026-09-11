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
