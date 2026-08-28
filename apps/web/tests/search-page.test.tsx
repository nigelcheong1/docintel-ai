import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SearchPage from "@/app/search/page";

const apiMocks = vi.hoisted(() => ({
  searchDocuments: vi.fn(),
}));

vi.mock("@/lib/api", () => apiMocks);

const successfulResponse = {
  query: "invoice total",
  answer: {
    summary: "The invoice total is 1250 Malaysian Ringgit.",
    citations: [
      {
        chunk_id: "chunk-1",
        document_filename: "invoice.pdf",
        page_number: 2,
        section_heading: "INVOICE SUMMARY",
      },
    ],
  },
  hits: [
    {
      chunk_id: "chunk-1",
      document_id: "doc-1",
      document_filename: "invoice.pdf",
      page_number: 2,
      chunk_index: 0,
      score: 0.87,
      source_score: 0.83,
      ranking_signals: {},
      section_heading: "INVOICE SUMMARY",
      snippet: "Invoice total is 1250 Malaysian Ringgit.",
    },
  ],
};

describe("SearchPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("clears previous search results when a subsequent search fails", async () => {
    apiMocks.searchDocuments.mockResolvedValueOnce(successfulResponse).mockRejectedValueOnce(new Error("Search failed."));

    render(<SearchPage />);

    const input = screen.getByRole("textbox", { name: "Search query" });
    const form = input.closest("form");
    expect(form).not.toBeNull();

    fireEvent.change(input, { target: { value: "invoice total" } });
    fireEvent.submit(form!);
    expect(await screen.findByText("The invoice total is 1250 Malaysian Ringgit.")).toBeInTheDocument();

    fireEvent.change(input, { target: { value: "missing total" } });
    fireEvent.submit(form!);

    await waitFor(() => expect(screen.getByText("Search failed.")).toBeInTheDocument());
    expect(screen.queryByText("The invoice total is 1250 Malaysian Ringgit.")).not.toBeInTheDocument();
    expect(screen.queryByText("invoice.pdf")).not.toBeInTheDocument();
  });
});
