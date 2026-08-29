import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SearchPage from "@/app/search/page";

const apiMocks = vi.hoisted(() => ({
  getDocuments: vi.fn(),
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

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((promiseResolve) => {
    resolve = promiseResolve;
  });
  return { promise, resolve };
}

describe("SearchPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiMocks.getDocuments.mockResolvedValue([]);
  });

  it("loads documents and searches within the selected document", async () => {
    apiMocks.getDocuments.mockResolvedValue([
      { id: "doc-1", filename: "resume.pdf", mime_type: "application/pdf", status: "indexed" },
    ]);
    apiMocks.searchDocuments.mockResolvedValue(successfulResponse);

    render(<SearchPage />);

    fireEvent.change(await screen.findByRole("combobox", { name: "Search scope" }), { target: { value: "doc-1" } });
    fireEvent.change(screen.getByRole("textbox", { name: "Search query" }), { target: { value: "technical skills" } });
    fireEvent.submit(screen.getByRole("textbox", { name: "Search query" }).closest("form")!);

    await waitFor(() => expect(apiMocks.searchDocuments).toHaveBeenCalledWith("technical skills", 5, "doc-1"));
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

  it("ignores stale results and loading completion from an older search", async () => {
    const olderSearch = deferred<typeof successfulResponse>();
    const newerSearch = deferred<typeof successfulResponse>();
    const olderResponse = {
      ...successfulResponse,
      query: "older query",
      answer: { ...successfulResponse.answer, summary: "Older search result." },
    };
    const newerResponse = {
      ...successfulResponse,
      query: "newer query",
      answer: { ...successfulResponse.answer, summary: "Newer search result." },
    };
    apiMocks.searchDocuments.mockReturnValueOnce(olderSearch.promise).mockReturnValueOnce(newerSearch.promise);

    render(<SearchPage />);

    const input = screen.getByRole("textbox", { name: "Search query" });
    const form = input.closest("form");
    const searchButton = screen.getByRole("button", { name: "Search" });
    expect(form).not.toBeNull();

    fireEvent.change(input, { target: { value: "older query" } });
    fireEvent.submit(form!);
    fireEvent.change(input, { target: { value: "newer query" } });
    fireEvent.submit(form!);

    await act(async () => olderSearch.resolve(olderResponse));

    expect(screen.queryByText("Older search result.")).not.toBeInTheDocument();
    expect(searchButton).toBeDisabled();

    await act(async () => newerSearch.resolve(newerResponse));

    expect(screen.getByText("Newer search result.")).toBeInTheDocument();
    expect(searchButton).toBeEnabled();
  });
});
