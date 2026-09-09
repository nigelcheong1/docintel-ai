import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import DocumentsPage from "@/app/documents/page";

const apiMocks = vi.hoisted(() => ({
  deleteDocument: vi.fn(),
  getDocument: vi.fn(),
  getDocuments: vi.fn(),
  getDocumentStatus: vi.fn(),
  reindexDocument: vi.fn(),
  uploadDocument: vi.fn(),
}));

vi.mock("@/lib/api", () => apiMocks);

const documentSummary = {
  id: "doc-1",
  filename: "quarterly-report.pdf",
  mime_type: "application/pdf",
  status: "indexed",
  error_message: null,
  created_at: "2026-08-28T03:30:00Z",
  updated_at: "2026-08-28T03:30:00Z",
  page_count: 12,
  chunk_count: 48,
};

const documentDetail = {
  ...documentSummary,
  page_count: 12,
  chunk_count: 48,
};

describe("DocumentsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    apiMocks.getDocuments.mockResolvedValue([documentSummary]);
    apiMocks.getDocument.mockResolvedValue(documentDetail);
    apiMocks.deleteDocument.mockResolvedValue(undefined);
    apiMocks.reindexDocument.mockResolvedValue(documentSummary);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("renders document-list metadata without per-row detail requests", async () => {
    render(<DocumentsPage />);

    expect(await screen.findAllByText("12")).toHaveLength(2);
    expect(apiMocks.getDocuments).toHaveBeenCalledTimes(1);
    expect(apiMocks.getDocument).not.toHaveBeenCalled();
  });

  it("refreshes the hydrated list after deleting a document", async () => {
    render(<DocumentsPage />);

    const deleteButton = (await screen.findAllByRole("button", { name: "Delete quarterly-report.pdf" }))[0];
    fireEvent.click(deleteButton);

    await waitFor(() => expect(apiMocks.deleteDocument).toHaveBeenCalledWith("doc-1"));
    await waitFor(() => expect(apiMocks.getDocuments).toHaveBeenCalledTimes(2));
    expect(apiMocks.getDocument).not.toHaveBeenCalled();
  });

  it("refreshes the hydrated list after reindexing a document", async () => {
    render(<DocumentsPage />);

    const reindexButton = (await screen.findAllByRole("button", { name: "Reindex quarterly-report.pdf" }))[0];
    fireEvent.click(reindexButton);

    await waitFor(() => expect(apiMocks.reindexDocument).toHaveBeenCalledWith("doc-1"));
    await waitFor(() => expect(apiMocks.getDocuments).toHaveBeenCalledTimes(2));
    expect(apiMocks.getDocument).not.toHaveBeenCalled();
  });

  it("polls for updates while a document is processing", async () => {
    apiMocks.getDocuments.mockResolvedValue([{ ...documentSummary, status: "embedding" }]);
    apiMocks.getDocument.mockResolvedValue({ ...documentDetail, status: "embedding" });
    apiMocks.getDocumentStatus.mockResolvedValue({
      document_id: "doc-1",
      filename: "quarterly-report.pdf",
      status: "embedding",
      active_stage: "embed",
      progress_percent: 80,
      message: "Embedding evidence chunks for semantic search.",
      page_count: 12,
      chunk_count: 48,
      embedded_chunk_count: 24,
      ocr_page_count: 0,
      stages: [],
    });

    render(<DocumentsPage />);

    expect(await screen.findAllByText("Embedding evidence chunks for semantic search.")).toHaveLength(2);
    expect(apiMocks.getDocumentStatus).toHaveBeenCalledWith("doc-1");
    expect(apiMocks.getDocument).not.toHaveBeenCalled();

    await waitFor(() => expect(apiMocks.getDocuments).toHaveBeenCalledTimes(2), { timeout: 2500 });
  }, 5000);
});
