import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SearchPage from "@/app/search/page";

const apiMocks = vi.hoisted(() => ({
  getDocuments: vi.fn(),
  getDocumentProfile: vi.fn(),
  searchDocuments: vi.fn(),
}));

vi.mock("@/lib/api", () => apiMocks);

const successfulResponse = {
  query: "invoice total",
  document_type: "invoice",
  query_intent: "amounts",
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
  quality: {
    status: "answerable",
    confidence: "strong",
    reason: "Answer built from 1 cited evidence chunk.",
    evidence_count: 1,
    best_score: 0.87,
    best_source_score: 0.83,
    best_keyword_overlap: 1,
    best_section_intent: 1,
    suggested_questions: [],
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
    apiMocks.getDocumentProfile.mockResolvedValue(null);
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

  it("uses an interactive search action", async () => {
    render(<SearchPage />);

    expect(await screen.findByRole("button", { name: "Search" })).toHaveClass("transition");
    expect(screen.getByRole("button", { name: "Search" })).toHaveClass("active:translate-y-px");
  });

  it("loads a selected document profile and lets profile suggestions fill the query", async () => {
    apiMocks.getDocuments.mockResolvedValue([
      { id: "doc-1", filename: "paper.pdf", mime_type: "application/pdf", status: "indexed" },
    ]);
    apiMocks.searchDocuments.mockResolvedValue(successfulResponse);
    apiMocks.getDocumentProfile.mockResolvedValue({
      document_id: "doc-1",
      filename: "paper.pdf",
      document_type: "research_paper",
      title: "Language Guided HRI",
      overview: "ABSTRACT This paper studies human robot interaction.",
      sections: [],
      key_dates: [],
      key_numbers: [],
      key_entities: [],
      suggested_questions: ["What is this document about?"],
    });

    render(<SearchPage />);

    fireEvent.change(await screen.findByRole("combobox", { name: "Search scope" }), { target: { value: "doc-1" } });

    expect(await screen.findByText("Research paper")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "What is this document about?" }));

    expect(screen.getByRole("textbox", { name: "Search query" })).toHaveValue("What is this document about?");
    await waitFor(() =>
      expect(apiMocks.searchDocuments).toHaveBeenCalledWith("What is this document about?", 5, "doc-1"),
    );
  });

  it("only offers indexed documents as search scope options", async () => {
    apiMocks.getDocuments.mockResolvedValue([
      { id: "doc-1", filename: "resume.pdf", mime_type: "application/pdf", status: "indexed" },
      { id: "doc-2", filename: "uploading.pdf", mime_type: "application/pdf", status: "processing" },
      { id: "doc-3", filename: "failed.pdf", mime_type: "application/pdf", status: "failed" },
    ]);

    render(<SearchPage />);

    const scope = await screen.findByRole("combobox", { name: "Search scope" });

    expect(screen.getByRole("option", { name: "resume.pdf" })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "uploading.pdf" })).not.toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "failed.pdf" })).not.toBeInTheDocument();
    expect(scope).toHaveValue("");
  });

  it("clears visible results when the search scope changes", async () => {
    apiMocks.getDocuments.mockResolvedValue([
      { id: "doc-1", filename: "invoice.pdf", mime_type: "application/pdf", status: "indexed" },
      { id: "doc-2", filename: "contract.pdf", mime_type: "application/pdf", status: "indexed" },
    ]);
    apiMocks.searchDocuments.mockResolvedValue(successfulResponse);

    render(<SearchPage />);

    const input = screen.getByRole("textbox", { name: "Search query" });
    fireEvent.change(input, { target: { value: "invoice total" } });
    fireEvent.submit(input.closest("form")!);
    expect(await screen.findByText("The invoice total is 1250 Malaysian Ringgit.")).toBeInTheDocument();

    fireEvent.change(await screen.findByRole("combobox", { name: "Search scope" }), { target: { value: "doc-2" } });

    expect(screen.queryByText("The invoice total is 1250 Malaysian Ringgit.")).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "invoice.pdf" })).not.toBeInTheDocument();
  });

  it("ignores an in-flight result after the search scope changes", async () => {
    const pendingSearch = deferred<typeof successfulResponse>();
    apiMocks.getDocuments.mockResolvedValue([
      { id: "doc-1", filename: "invoice.pdf", mime_type: "application/pdf", status: "indexed" },
      { id: "doc-2", filename: "contract.pdf", mime_type: "application/pdf", status: "indexed" },
    ]);
    apiMocks.searchDocuments.mockReturnValueOnce(pendingSearch.promise);

    render(<SearchPage />);

    const scope = await screen.findByRole("combobox", { name: "Search scope" });
    const input = screen.getByRole("textbox", { name: "Search query" });
    const searchButton = screen.getByRole("button", { name: "Search" });
    fireEvent.change(scope, { target: { value: "doc-1" } });
    fireEvent.change(input, { target: { value: "invoice total" } });
    fireEvent.submit(input.closest("form")!);
    expect(searchButton).toBeDisabled();

    fireEvent.change(scope, { target: { value: "doc-2" } });
    await act(async () => pendingSearch.resolve(successfulResponse));

    expect(screen.queryByText("The invoice total is 1250 Malaysian Ringgit.")).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "invoice.pdf" })).not.toBeInTheDocument();
    expect(searchButton).toBeEnabled();
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

  it("renders answer-quality abstentions and lets suggested questions fill the query", async () => {
    apiMocks.searchDocuments.mockResolvedValueOnce({
      query: "How does invoice payment work?",
      answer: null,
      quality: {
        status: "insufficient_evidence",
        confidence: "weak",
        reason: "The retrieved documents do not contain enough matching evidence to answer this question.",
        evidence_count: 0,
        best_score: 0.34,
        best_source_score: 0.46,
        best_keyword_overlap: 0,
        best_section_intent: 0,
        suggested_questions: ["What technical skills are mentioned?"],
      },
      hits: [
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
      ],
    }).mockResolvedValueOnce(successfulResponse);

    render(<SearchPage />);

    const input = screen.getByRole("textbox", { name: "Search query" });
    fireEvent.change(input, { target: { value: "How does invoice payment work?" } });
    fireEvent.submit(input.closest("form")!);

    expect(await screen.findByRole("heading", { name: "Not enough evidence" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "What technical skills are mentioned?" }));

    expect(input).toHaveValue("What technical skills are mentioned?");
    await waitFor(() =>
      expect(apiMocks.searchDocuments).toHaveBeenLastCalledWith("What technical skills are mentioned?", 5, undefined),
    );
  });
});
