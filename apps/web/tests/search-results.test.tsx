import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SearchResults } from "@/components/search-results";

describe("SearchResults", () => {
  it("renders cited evidence", () => {
    render(
      <SearchResults
        hits={[
          {
            chunk_id: "chunk-1",
            document_id: "doc-1",
            document_filename: "invoice.pdf",
            page_number: 2,
            chunk_index: 0,
            score: 0.87,
            snippet: "Invoice total is 1250 Malaysian Ringgit.",
          },
        ]}
      />,
    );

    expect(screen.getByText("invoice.pdf")).toBeInTheDocument();
    expect(screen.getByText("Page 2")).toBeInTheDocument();
    expect(screen.getByText("87%")).toBeInTheDocument();
  });

  it("allows long filenames and snippets to wrap inside result cards", () => {
    const filename = `${"quarterly".repeat(20)}.pdf`;
    const snippet = "unbroken".repeat(80);
    render(
      <SearchResults
        hits={[
          {
            chunk_id: "chunk-long",
            document_id: "doc-long",
            document_filename: filename,
            page_number: 1,
            chunk_index: 0,
            score: 0.5,
            snippet,
          },
        ]}
      />,
    );

    expect(screen.getByText(filename)).toHaveClass("break-all");
    expect(screen.getByText(snippet)).toHaveClass("break-words");
  });
});
