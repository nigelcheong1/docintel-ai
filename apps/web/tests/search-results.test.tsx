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
});
