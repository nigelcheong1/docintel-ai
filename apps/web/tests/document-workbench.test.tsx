import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DocumentWorkbench } from "@/components/document-workbench";
import {
  generateDocumentStudySummary,
  generateStudyQuestions,
  getDocumentStudySummary,
  getStudyQuestions,
  previewDocumentStudySummary,
  previewStudyQuestions,
  saveDocumentStudySummary,
  saveStudyQuestions,
  submitStudyAnswer,
} from "@/lib/api";
import type { DocumentChunk, DocumentDetail, DocumentPage, DocumentProfile } from "@/lib/types";

vi.mock("@/lib/api", () => ({
  generateDocumentStudySummary: vi.fn(),
  generateStudyQuestions: vi.fn(),
  getDocumentStudySummary: vi.fn(),
  getStudyQuestions: vi.fn(),
  previewDocumentStudySummary: vi.fn(),
  previewStudyQuestions: vi.fn(),
  saveDocumentStudySummary: vi.fn(),
  saveStudyQuestions: vi.fn(),
  submitStudyAnswer: vi.fn(),
}));

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
    image_url: "/documents/doc-1/pages/1/image",
    text_source: "native",
    text_preview: "Abstract introduces human robot collaboration.",
    character_count: 800,
    chunk_count: 1,
    token_estimate: 120,
    text_density: 0.84,
    ocr_quality: "native",
    processing_status: "native_text",
    needs_review: false,
  },
  {
    document_id: "doc-1",
    page_number: 2,
    image_url: "/documents/doc-1/pages/2/image",
    text_source: "ocr",
    text_preview: "Table 1 compares HRI30 and InHARD.",
    character_count: 1000,
    chunk_count: 2,
    token_estimate: 180,
    text_density: 0.7,
    ocr_quality: "strong",
    processing_status: "ocr_strong",
    needs_review: false,
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
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getDocumentStudySummary).mockResolvedValue(null);
    vi.mocked(getStudyQuestions).mockResolvedValue([]);
    vi.mocked(generateDocumentStudySummary).mockResolvedValue({
      id: "summary-1",
      document_id: "doc-1",
      content: "DocIntel AI summarizes cited evidence and prepares study material.",
      created_at: "2026-09-07T00:00:00Z",
      citations: [
        {
          chunk_id: "chunk-1",
          document_id: "doc-1",
          document_filename: "research-paper.pdf",
          page_number: 1,
          section_heading: "ABSTRACT",
          page_image_url: "/documents/doc-1/pages/1/image",
          document_page_url: "/documents/doc-1?page=1&chunk=chunk-1",
        },
      ],
    });
    vi.mocked(previewDocumentStudySummary).mockResolvedValue({
      id: "summary-preview",
      document_id: "doc-1",
      content: "Preview replacement summary.",
      created_at: "2026-09-07T00:00:00Z",
      is_preview: true,
      generation_mode: "detailed",
      citation_count: 1,
      quality_status: "grounded",
      citations: [
        {
          chunk_id: "chunk-1",
          document_id: "doc-1",
          document_filename: "research-paper.pdf",
          page_number: 1,
          section_heading: "ABSTRACT",
          page_image_url: "/documents/doc-1/pages/1/image",
          document_page_url: "/documents/doc-1?page=1&chunk=chunk-1",
        },
      ],
    });
    vi.mocked(saveDocumentStudySummary).mockResolvedValue({
      id: "summary-saved",
      document_id: "doc-1",
      content: "Preview replacement summary.",
      created_at: "2026-09-07T00:00:00Z",
      is_preview: false,
      generation_mode: "detailed",
      citation_count: 1,
      quality_status: "grounded",
      citations: [
        {
          chunk_id: "chunk-1",
          document_id: "doc-1",
          document_filename: "research-paper.pdf",
          page_number: 1,
          section_heading: "ABSTRACT",
          page_image_url: "/documents/doc-1/pages/1/image",
          document_page_url: "/documents/doc-1?page=1&chunk=chunk-1",
        },
      ],
    });
    vi.mocked(generateStudyQuestions).mockResolvedValue([
      {
        id: "question-1",
        document_id: "doc-1",
        question: "What methods are used?",
        expected_answer: "The system uses OCR and embeddings.",
        created_at: "2026-09-07T00:00:00Z",
        latest_answer: null,
        citations: [
          {
            chunk_id: "chunk-2",
            document_id: "doc-1",
            document_filename: "research-paper.pdf",
            page_number: 2,
            section_heading: "METHOD",
            page_image_url: "/documents/doc-1/pages/2/image",
            document_page_url: "/documents/doc-1?page=2&chunk=chunk-2",
          },
        ],
      },
    ]);
    vi.mocked(previewStudyQuestions).mockResolvedValue([
      {
        id: "question-preview",
        document_id: "doc-1",
        question: "Which evidence supports the method?",
        expected_answer: "The cited method evidence mentions OCR and embeddings.",
        created_at: "2026-09-07T00:00:00Z",
        latest_answer: null,
        answer_count: 0,
        recent_answers: [],
        is_preview: true,
        generation_mode: "exam",
        citation_count: 1,
        quality_status: "grounded",
        citations: [
          {
            chunk_id: "chunk-2",
            document_id: "doc-1",
            document_filename: "research-paper.pdf",
            page_number: 2,
            section_heading: "METHOD",
            page_image_url: "/documents/doc-1/pages/2/image",
            document_page_url: "/documents/doc-1?page=2&chunk=chunk-2",
          },
        ],
      },
    ]);
    vi.mocked(saveStudyQuestions).mockResolvedValue([
      {
        id: "question-saved",
        document_id: "doc-1",
        question: "Which evidence supports the method?",
        expected_answer: "The cited method evidence mentions OCR and embeddings.",
        created_at: "2026-09-07T00:00:00Z",
        latest_answer: null,
        answer_count: 0,
        recent_answers: [],
        is_preview: false,
        generation_mode: "exam",
        citation_count: 1,
        quality_status: "grounded",
        citations: [
          {
            chunk_id: "chunk-2",
            document_id: "doc-1",
            document_filename: "research-paper.pdf",
            page_number: 2,
            section_heading: "METHOD",
            page_image_url: "/documents/doc-1/pages/2/image",
            document_page_url: "/documents/doc-1?page=2&chunk=chunk-2",
          },
        ],
      },
    ]);
    vi.mocked(submitStudyAnswer).mockResolvedValue({
      id: "answer-1",
      question_id: "question-1",
      answer_text: "It uses OCR and embeddings.",
      score: 0.82,
      feedback: "Strong answer. You covered the main cited points.",
      created_at: "2026-09-07T00:00:00Z",
    });
  });

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
    expect(screen.getByText("OCR strong")).toBeInTheDocument();
    expect(screen.getByText("OCR confidence is lower on page 2.")).toBeInTheDocument();

    const pageEvidence = screen.getByRole("region", { name: "Page evidence" });
    const pagePreview = screen.getByRole("img", { name: "Page 2 source preview" });

    expect(pagePreview).toHaveAttribute("src", "http://localhost:8000/documents/doc-1/pages/2/image");
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

  it("lets reviewers zoom the selected page preview", () => {
    render(<DocumentWorkbench document={documentDetail} profile={profile} pages={pages} chunks={chunks} initialPageNumber={2} />);

    expect(screen.getByText("100%")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Zoom in page preview" }));

    expect(screen.getByText("125%")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Reset page preview zoom" }));

    expect(screen.getByText("100%")).toBeInTheDocument();
  });

  it("highlights a citation chunk opened from a search deep link", () => {
    render(
      <DocumentWorkbench
        document={documentDetail}
        profile={profile}
        pages={pages}
        chunks={chunks}
        initialPageNumber={2}
        initialChunkId="chunk-3"
      />,
    );

    const selectedChunk = screen.getByText("The model reaches 91.38 Top1 accuracy.").closest("article");

    expect(selectedChunk).toHaveTextContent("Selected citation");
    expect(selectedChunk).toHaveClass("border-amber-300");
    expect(screen.getByRole("img", { name: "Page 2 source preview" })).toBeInTheDocument();
  });

  it("marks weak OCR pages as needing review", () => {
    const reviewPages = pages.map((page) =>
      page.page_number === 2
        ? {
            ...page,
            ocr_quality: "weak" as const,
            processing_status: "ocr_weak" as const,
            needs_review: true,
          }
        : page,
    );

    render(<DocumentWorkbench document={documentDetail} profile={profile} pages={reviewPages} chunks={chunks} />);

    fireEvent.click(screen.getByRole("button", { name: /Page 2/ }));

    expect(screen.getAllByText("Review needed").length).toBeGreaterThan(0);
  });

  it("generates a cited study summary from the workbench", async () => {
    render(<DocumentWorkbench document={documentDetail} profile={profile} pages={pages} chunks={chunks} />);

    fireEvent.click(screen.getByRole("button", { name: "Summary" }));
    fireEvent.click(screen.getByRole("button", { name: "Generate summary" }));

    expect(await screen.findByText("DocIntel AI summarizes cited evidence and prepares study material.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Page 1 ABSTRACT" })).toHaveAttribute(
      "href",
      "/documents/doc-1?page=1&chunk=chunk-1",
    );
    fireEvent.click(screen.getByRole("button", { name: "Preview citation research-paper.pdf page 1" }));

    expect(screen.getByRole("dialog", { name: "Source viewer" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Page 1 source preview for research-paper.pdf" })).toHaveAttribute(
      "src",
      "http://localhost:8000/documents/doc-1/pages/1/image",
    );
    expect(generateDocumentStudySummary).toHaveBeenCalledWith("doc-1", { mode: "concise" });
  });

  it("previews a regenerated summary before replacing the current one", async () => {
    vi.mocked(getDocumentStudySummary).mockResolvedValueOnce({
      id: "summary-current",
      document_id: "doc-1",
      content: "Current cited summary.",
      created_at: "2026-09-07T00:00:00Z",
      citations: [],
    });

    render(<DocumentWorkbench document={documentDetail} profile={profile} pages={pages} chunks={chunks} />);

    fireEvent.click(screen.getByRole("button", { name: "Summary" }));
    expect(await screen.findByText("Current cited summary.")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Detailed" }));
    fireEvent.click(screen.getByRole("button", { name: "Preview new summary" }));

    expect(await screen.findByText("Preview replacement summary.")).toBeInTheDocument();
    expect(screen.getByText("Current cited summary.")).toBeInTheDocument();
    expect(saveDocumentStudySummary).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Replace current" }));

    await waitFor(() =>
      expect(saveDocumentStudySummary).toHaveBeenCalledWith(
        "doc-1",
        expect.objectContaining({ content: "Preview replacement summary." }),
      ),
    );
    expect(screen.getByText("Preview replacement summary.")).toBeInTheDocument();
    expect(screen.queryByText("Current cited summary.")).not.toBeInTheDocument();
    expect(previewDocumentStudySummary).toHaveBeenCalledWith("doc-1", { mode: "detailed" });
  });

  it("generates study questions and submits an answer for feedback", async () => {
    render(<DocumentWorkbench document={documentDetail} profile={profile} pages={pages} chunks={chunks} />);

    fireEvent.click(screen.getByRole("button", { name: "Study" }));
    fireEvent.click(screen.getByRole("button", { name: "Generate study set" }));

    expect(await screen.findByText("What methods are used?")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Answer for What methods are used?"), {
      target: { value: "It uses OCR and embeddings." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Check answer" }));

    await waitFor(() => expect(submitStudyAnswer).toHaveBeenCalledWith("doc-1", "question-1", "It uses OCR and embeddings."));
    expect(await screen.findByText("Strong answer. You covered the main cited points.")).toBeInTheDocument();
    expect(screen.getByText("82%")).toBeInTheDocument();
  });

  it("lets reviewers discard a replacement study-set preview", async () => {
    vi.mocked(getStudyQuestions).mockResolvedValueOnce([
      {
        id: "question-stale",
        document_id: "doc-1",
        question: "What does the document say about 1 contents?",
        expected_answer: "XIAMEN UNIVERSITY MALAYSIA Table of Contents 1.",
        created_at: "2026-09-07T00:00:00Z",
        latest_answer: null,
        answer_count: 0,
        recent_answers: [],
        citations: [],
      },
    ]);

    render(<DocumentWorkbench document={documentDetail} profile={profile} pages={pages} chunks={chunks} />);

    fireEvent.click(screen.getByRole("button", { name: "Study" }));
    expect(await screen.findByText("What does the document say about 1 contents?")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Preview new study set" }));

    expect(await screen.findByText("Which evidence supports the method?")).toBeInTheDocument();
    expect(screen.getByText("What does the document say about 1 contents?")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Keep current" }));

    expect(screen.queryByText("Which evidence supports the method?")).not.toBeInTheDocument();
    expect(screen.getByText("What does the document say about 1 contents?")).toBeInTheDocument();
    expect(previewStudyQuestions).toHaveBeenCalledWith("doc-1", 5, { mode: "balanced", replaceExisting: true });
    expect(generateStudyQuestions).not.toHaveBeenCalled();
  });

  it("previews a replacement study set before clearing existing answers", async () => {
    vi.mocked(getStudyQuestions).mockResolvedValueOnce([
      {
        id: "question-current",
        document_id: "doc-1",
        question: "What is the stale question?",
        expected_answer: "Old expected answer.",
        created_at: "2026-09-07T00:00:00Z",
        latest_answer: {
          id: "answer-current",
          question_id: "question-current",
          answer_text: "Old answer.",
          score: 0.82,
          feedback: "Old feedback.",
          created_at: "2026-09-07T00:00:00Z",
        },
        answer_count: 1,
        recent_answers: [],
        citations: [],
      },
    ]);

    render(<DocumentWorkbench document={documentDetail} profile={profile} pages={pages} chunks={chunks} />);

    fireEvent.click(screen.getByRole("button", { name: "Study" }));
    expect(await screen.findByText("What is the stale question?")).toBeInTheDocument();
    expect(screen.getByText("82%")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Exam-style" }));
    fireEvent.click(screen.getByRole("button", { name: "Preview new study set" }));

    expect(await screen.findByText("Which evidence supports the method?")).toBeInTheDocument();
    expect(screen.getByText("What is the stale question?")).toBeInTheDocument();
    expect(saveStudyQuestions).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Replace current" }));

    await waitFor(() =>
      expect(saveStudyQuestions).toHaveBeenCalledWith(
        "doc-1",
        [expect.objectContaining({ question: "Which evidence supports the method?" })],
        { mode: "exam", replaceExisting: true },
      ),
    );
    expect(screen.queryByText("What is the stale question?")).not.toBeInTheDocument();
    expect(screen.queryByText("82%")).not.toBeInTheDocument();
    expect(previewStudyQuestions).toHaveBeenCalledWith("doc-1", 5, { mode: "exam", replaceExisting: true });
  });

  it("shows study attempt history and citation snippets in the source viewer", async () => {
    vi.mocked(getStudyQuestions).mockResolvedValueOnce([
      {
        id: "question-history",
        document_id: "doc-1",
        question: "What methods are used?",
        expected_answer: "The system uses OCR and embeddings.",
        created_at: "2026-09-07T00:00:00Z",
        latest_answer: {
          id: "answer-new",
          question_id: "question-history",
          answer_text: "It uses OCR and embeddings.",
          score: 0.82,
          feedback: "Strong answer.",
          created_at: "2026-09-07T11:00:00Z",
        },
        answer_count: 2,
        recent_answers: [
          {
            id: "answer-new",
            question_id: "question-history",
            answer_text: "It uses OCR and embeddings.",
            score: 0.82,
            feedback: "Strong answer.",
            created_at: "2026-09-07T11:00:00Z",
          },
          {
            id: "answer-old",
            question_id: "question-history",
            answer_text: "It reads files.",
            score: 0.35,
            feedback: "Needs work.",
            created_at: "2026-09-07T10:00:00Z",
          },
        ],
        citations: [
          {
            chunk_id: "chunk-2",
            document_id: "doc-1",
            document_filename: "research-paper.pdf",
            page_number: 2,
            section_heading: "METHOD",
            page_image_url: "/documents/doc-1/pages/2/image",
            document_page_url: "/documents/doc-1?page=2&chunk=chunk-2",
            snippet: "METHOD The pipeline uses OCR, page chunks, embeddings, and cited answer evidence.",
            score: 0.72,
            source_score: 0.68,
          },
        ],
      },
    ]);

    render(<DocumentWorkbench document={documentDetail} profile={profile} pages={pages} chunks={chunks} />);

    fireEvent.click(screen.getByRole("button", { name: "Study" }));

    expect(await screen.findByText("2 attempts")).toBeInTheDocument();
    expect(screen.getByText("Recent attempts")).toBeInTheDocument();
    expect(screen.getByText("Needs work.")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Preview citation research-paper.pdf page 2" }));

    const sourceViewer = screen.getByRole("dialog", { name: "Source viewer" });
    expect(within(sourceViewer).getByText("METHOD The pipeline uses OCR, page chunks, embeddings, and cited answer evidence.")).toBeInTheDocument();
    expect(within(sourceViewer).getByText("72%")).toBeInTheDocument();
    expect(within(sourceViewer).getByText("68%")).toBeInTheDocument();
  });
});
