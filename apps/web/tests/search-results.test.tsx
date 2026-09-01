import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

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

  it("shows answer confidence when quality metadata is available", () => {
    render(
      <SearchResults
        documentType="research_paper"
        queryIntent="overview"
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
        quality={{
          status: "answerable",
          confidence: "strong",
          reason: "Answer built from 1 cited evidence chunk.",
          evidence_count: 1,
          best_score: 0.91,
          best_source_score: 0.87,
          best_keyword_overlap: 1,
          best_section_intent: 1,
          suggested_questions: [],
        }}
        hits={[]}
      />,
    );

    expect(screen.getByText("Strong confidence")).toBeInTheDocument();
    expect(screen.getByText("Research paper")).toBeInTheDocument();
    expect(screen.getByText("Overview")).toBeInTheDocument();
    expect(screen.getByText("Answer built from 1 cited evidence chunk.")).toBeInTheDocument();
  });

  it("shows diagnostics and separates answer evidence from related results", () => {
    render(
      <SearchResults
        documentType="invoice"
        queryIntent="amounts"
        diagnostics={{
          document_type: "invoice",
          query_intent: "amounts",
          quality_status: "answerable",
          confidence: "strong",
          reason: "Answer built from 1 cited evidence chunk.",
          answer_chunk_ids: ["answer-1"],
          answer_evidence_count: 1,
          related_result_count: 1,
          top_rejected_reasons: ["related-1: not cited in the answer"],
        }}
        answer={{
          summary: "Total due: RM 1,272.00.",
          citations: [
            {
              chunk_id: "answer-1",
              document_filename: "invoice.pdf",
              page_number: 1,
              section_heading: "PAYMENT SUMMARY",
            },
          ],
        }}
        hits={[
          {
            chunk_id: "answer-1",
            document_id: "doc-1",
            document_filename: "invoice.pdf",
            page_number: 1,
            chunk_index: 0,
            score: 0.91,
            source_score: 0.87,
            ranking_signals: {},
            result_role: "answer_evidence",
            section_heading: "PAYMENT SUMMARY",
            snippet: "PAYMENT SUMMARY Total Due RM 1,272.00.",
          },
          {
            chunk_id: "related-1",
            document_id: "doc-1",
            document_filename: "invoice.pdf",
            page_number: 1,
            chunk_index: 1,
            score: 0.55,
            source_score: 0.49,
            ranking_signals: {},
            result_role: "related",
            section_heading: "VENDOR",
            snippet: "Vendor: DocIntel Labs.",
          },
        ]}
      />,
    );

    expect(screen.getByText("Search diagnostics")).toBeInTheDocument();
    expect(screen.getByText("1 answer chunk")).toBeInTheDocument();
    expect(screen.getByText("1 related result")).toBeInTheDocument();
    expect(screen.queryByText(/related-1:/)).not.toBeInTheDocument();
    expect(screen.getByText(/ranked below the selected answer evidence/)).toBeInTheDocument();

    const answerEvidence = screen.getByRole("heading", { name: "Answer evidence" });
    const relatedEvidence = screen.getByRole("heading", { name: "Related evidence" });
    expect(answerEvidence.compareDocumentPosition(relatedEvidence)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
  });

  it("renders an abstention panel with suggested questions", () => {
    const handleSuggestionSelect = vi.fn();
    render(
      <SearchResults
        documentType="resume"
        queryIntent="amounts"
        answer={null}
        quality={{
          status: "insufficient_evidence",
          confidence: "weak",
          reason: "The retrieved documents do not contain enough matching evidence to answer this question.",
          evidence_count: 0,
          best_score: 0.34,
          best_source_score: 0.46,
          best_keyword_overlap: 0,
          best_section_intent: 0,
          suggested_questions: ["What technical skills are mentioned?"],
        }}
        hits={[
          {
            chunk_id: "chunk-weak",
            document_id: "doc-1",
            document_filename: "resume.pdf",
            page_number: 1,
            chunk_index: 0,
            score: 0.34,
            source_score: 0.46,
            ranking_signals: { keyword_overlap: 0, section_intent: 0 },
            snippet: "Technical Skills Machine Learning, Python, SQL.",
          },
        ]}
        onSuggestionSelect={handleSuggestionSelect}
      />,
    );

    expect(screen.getByRole("heading", { name: "Not enough evidence" })).toBeInTheDocument();
    expect(screen.getByText("Weak confidence")).toBeInTheDocument();
    expect(screen.getByText("Resume")).toBeInTheDocument();
    expect(screen.getByText("Amounts")).toBeInTheDocument();
    expect(
      screen.getByText("The retrieved documents do not contain enough matching evidence to answer this question."),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "What technical skills are mentioned?" }));

    expect(handleSuggestionSelect).toHaveBeenCalledWith("What technical skills are mentioned?");
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
