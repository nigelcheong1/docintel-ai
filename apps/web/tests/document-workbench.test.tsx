import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DocumentWorkbench } from "@/components/document-workbench";
import type { DocumentChunk, DocumentDetail, DocumentPage, DocumentProfile } from "@/lib/types";

const documentDetail: DocumentDetail = {
  id: "doc-1",
  filename: "research-paper.pdf",
  mime_type: "application/pdf",
  status: "indexed",
  error_message: null,
  created_at: "2026-09-02T10:00:00Z",
  updated_at: "2026-09-02T10:05:00Z",
  page_count: 2,
  chunk_count: 3,
  parse_quality: {
    page_count: 2,
    text_page_count: 2,
    empty_page_count: 0,
    total_characters: 1800,
    average_characters_per_page: 900,
    low_text_page_ratio: 0,
    scanned_likelihood: "low",
    warnings: ["OCR confidence is lower on page 2."],
    ocr_page_count: 1,
    native_text_page_count: 1,
    hybrid_page_count: 0,
    ocr_confidence_average: 88.5,
    ocr_duration_ms: 245,
    text_source_summary: { native: 1, ocr: 1 },
  },
};

const profile: DocumentProfile = {
  document_id: "doc-1",
  filename: "research-paper.pdf",
  document_type: "research_paper",
  title: "Human Robot Collaboration",
  overview: "This paper studies intent perception for human robot collaboration.",
  sections: [
    {
      heading: "ABSTRACT",
      page_number: 1,
      text_preview: "Abstract introduces human robot collaboration.",
      intents: ["overview"],
    },
    {
      heading: "RESULTS",
      page_number: 2,
      text_preview: "Results compare HRI30 and InHARD.",
      intents: ["results", "datasets"],
    },
  ],
  key_dates: [],
  key_numbers: [
    {
      kind: "metric",
      label: "Top1 accuracy",
      value: "91.38",
      page_number: 2,
      source_text: "Top1 accuracy of 91.38 on InHARD.",
    },
  ],
  key_entities: [],
  suggested_questions: ["What results are reported?"],
};

const pages: DocumentPage[] = [
  {
    document_id: "doc-1",
    page_number: 1,
    text_source: "native",
    text_preview: "Abstract introduces human robot collaboration.",
    character_count: 800,
    chunk_count: 1,
    token_estimate: 120,
  },
  {
    document_id: "doc-1",
    page_number: 2,
    text_source: "ocr",
    text_preview: "Table 1 compares HRI30 and InHARD.",
    character_count: 1000,
    chunk_count: 2,
    token_estimate: 180,
    ocr_engine: "tesseract",
    ocr_confidence: 88.5,
    ocr_duration_ms: 245,
  },
];

const chunks: DocumentChunk[] = [
  {
    id: "chunk-1",
    document_id: "doc-1",
    page_number: 1,
    chunk_index: 0,
    text: "Abstract introduces human robot collaboration.",
    token_estimate: 120,
  },
  {
    id: "chunk-2",
    document_id: "doc-1",
    page_number: 2,
    chunk_index: 1,
    text: "Table 1 compares HRI30 and InHARD.",
    token_estimate: 90,
  },
  {
    id: "chunk-3",
    document_id: "doc-1",
    page_number: 2,
    chunk_index: 2,
    text: "The model reaches 91.38 Top1 accuracy.",
    token_estimate: 90,
  },
];

describe("DocumentWorkbench", () => {
  it("summarizes document coverage and lets reviewers inspect page evidence", () => {
    render(
      <DocumentWorkbench
        document={documentDetail}
        profile={profile}
        pages={pages}
        chunks={chunks}
        initialPageNumber={2}
      />,
    );

    expect(screen.getByText("Evidence Workbench")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "research-paper.pdf" })).toBeInTheDocument();
    expect(screen.getByText("2 pages")).toBeInTheDocument();
    expect(screen.getByText("3 chunks")).toBeInTheDocument();
    expect(screen.getByText("88.5% OCR confidence")).toBeInTheDocument();
    expect(screen.getByText("OCR confidence is lower on page 2.")).toBeInTheDocument();

    const pageEvidence = screen.getByRole("region", { name: "Page evidence" });
    expect(within(pageEvidence).getByText("Table 1 compares HRI30 and InHARD.")).toBeInTheDocument();
    expect(within(pageEvidence).queryByText("Abstract introduces human robot collaboration.")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Page 1/ }));

    expect(within(pageEvidence).getByText("Abstract introduces human robot collaboration.")).toBeInTheDocument();
  });

  it("keeps the selected page synced when a document deep link changes", () => {
    const { rerender } = render(
      <DocumentWorkbench
        document={documentDetail}
        profile={profile}
        pages={pages}
        chunks={chunks}
        initialPageNumber={1}
      />,
    );

    expect(within(screen.getByRole("region", { name: "Page evidence" })).getByText("Abstract introduces human robot collaboration.")).toBeInTheDocument();

    rerender(
      <DocumentWorkbench
        document={documentDetail}
        profile={profile}
        pages={pages}
        chunks={chunks}
        initialPageNumber={2}
      />,
    );

    const pageEvidence = screen.getByRole("region", { name: "Page evidence" });
    expect(within(pageEvidence).getByText("Table 1 compares HRI30 and InHARD.")).toBeInTheDocument();
    expect(within(pageEvidence).queryByText("Abstract introduces human robot collaboration.")).not.toBeInTheDocument();
  });

  it("opens the evidence view when a reviewer selects a page", () => {
    render(<DocumentWorkbench document={documentDetail} profile={profile} pages={pages} chunks={chunks} />);

    expect(screen.queryByRole("region", { name: "Page evidence" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Page 2/ }));

    expect(within(screen.getByRole("region", { name: "Page evidence" })).getByText("Table 1 compares HRI30 and InHARD.")).toBeInTheDocument();
  });
});
