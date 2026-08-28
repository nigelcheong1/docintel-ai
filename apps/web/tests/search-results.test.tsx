import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SearchResults } from "@/components/search-results";

describe("SearchResults", () => {
  it("renders an answer with traceable citations above evidence", () => {
    render(
      <SearchResults
        answer={{
          summary: "The invoice total is 1250 Malaysian Ringgit.",
          citations: [
            {
              chunk_id: "chunk-1",
              document_filename: "invoice.pdf",
              page_number: 2,
              section_heading: "INVOICE SUMMARY",
            },
          ],
        }}
        hits={[]}
      />,
    );

    expect(screen.getByRole("heading", { name: "Answer" })).toBeInTheDocument();
    expect(screen.getByText("The invoice total is 1250 Malaysian Ringgit.")).toBeInTheDocument();
    expect(screen.getByText("1 citation")).toBeInTheDocument();
    expect(screen.getByText("invoice.pdf, page 2, INVOICE SUMMARY")).toBeInTheDocument();
  });

  it("renders an answer before its supporting evidence", () => {
    render(
      <SearchResults
        answer={{
          summary: "The invoice total is 1250 Malaysian Ringgit.",
          citations: [
            {
              chunk_id: "chunk-1",
              document_filename: "invoice.pdf",
              page_number: 2,
              section_heading: "INVOICE SUMMARY",
            },
          ],
        }}
        hits={[
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
        ]}
      />,
    );

    const answer = screen.getByRole("heading", { name: "Answer" }).closest("section");
    const evidence = screen.getByText("invoice.pdf").closest("article");

    if (!answer || !evidence) {
      throw new Error("Expected answer section and evidence card to be rendered");
    }

    expect(answer.compareDocumentPosition(evidence)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
  });

  it("shows blended, source, and ranking signal scores for evidence", () => {
    render(
      <SearchResults
        hits={[
          {
            chunk_id: "chunk-ranked",
            document_id: "doc-1",
            document_filename: "invoice.pdf",
            page_number: 2,
            chunk_index: 0,
            score: 0.91,
            source_score: 0.87,
            ranking_signals: { keyword_overlap: 1, section_intent: 0.5 },
            section_heading: "INVOICE SUMMARY",
            snippet: "Invoice total is 1250 Malaysian Ringgit.",
          },
        ]}
      />,
    );

    expect(screen.getByText("Blended score")).toBeInTheDocument();
    expect(screen.getByText("91%")).toBeInTheDocument();
    expect(screen.getByText("Source score")).toBeInTheDocument();
    expect(screen.getByText("87%")).toBeInTheDocument();
    expect(screen.getByText("Keyword overlap")).toBeInTheDocument();
    expect(screen.getByText("100%")).toBeInTheDocument();
    expect(screen.getByText("Section intent")).toBeInTheDocument();
    expect(screen.getByText("50%")).toBeInTheDocument();
  });

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
            source_score: 0.83,
            ranking_signals: {},
            section_heading: "KEY PROJECTS",
            snippet: "Invoice total is 1250 Malaysian Ringgit.",
          },
        ]}
      />,
    );

    expect(screen.getByText("invoice.pdf")).toBeInTheDocument();
    expect(screen.getByText("Page 2")).toBeInTheDocument();
    expect(screen.getByText("KEY PROJECTS")).toBeInTheDocument();
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
            source_score: 0.5,
            ranking_signals: {},
            snippet,
          },
        ]}
      />,
    );

    expect(screen.getByText(filename)).toHaveClass("break-all");
    expect(screen.getByText(snippet)).toHaveClass("break-words");
  });
});
