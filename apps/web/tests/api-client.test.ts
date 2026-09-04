import { afterEach, describe, expect, it, vi } from "vitest";

import {
  deleteDocument,
  getDocument,
  getDocumentChunks,
  getDocumentPages,
  getDocumentProfile,
  getDocuments,
  getGoldenEval,
  reindexDocument,
  searchDocuments,
} from "@/lib/api";

describe("api client", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("fetches documents from the configured backend", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [
        {
          id: "doc-1",
          filename: "sample.pdf",
          mime_type: "application/pdf",
          status: "indexed",
          parse_quality: {
            page_count: 2,
            text_page_count: 2,
            empty_page_count: 0,
            total_characters: 2400,
            average_characters_per_page: 1200,
            low_text_page_ratio: 0,
            scanned_likelihood: "low",
            warnings: [],
          },
        },
      ],
    });
    vi.stubGlobal("fetch", fetchMock);

    const documents = await getDocuments();

    expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/documents", { cache: "no-store" });
    expect(documents[0].filename).toBe("sample.pdf");
    expect(documents[0].parse_quality?.scanned_likelihood).toBe("low");
    expect(documents[0].parse_quality?.warnings).toEqual([]);
  });

  it("fetches document metadata from the document detail endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        id: "doc-1",
        filename: "sample.pdf",
        mime_type: "application/pdf",
        status: "indexed",
        page_count: 12,
        chunk_count: 48,
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const document = await getDocument("doc-1");

    expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/documents/doc-1", { cache: "no-store" });
    expect(document).toMatchObject({ page_count: 12, chunk_count: 48 });
  });

  it("fetches document intelligence profiles", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        document_id: "doc-1",
        filename: "paper.pdf",
        document_type: "research_paper",
        title: "Language Guided HRI",
        overview: "ABSTRACT This paper studies HRI.",
        sections: [],
        key_dates: [],
        key_numbers: [],
        key_entities: [],
        suggested_questions: ["What is this document about?"],
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const profile = await getDocumentProfile("doc-1");

    expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/documents/doc-1/profile", { cache: "no-store" });
    expect(profile.document_type).toBe("research_paper");
    expect(profile.suggested_questions).toEqual(["What is this document about?"]);
  });

  it("fetches document page diagnostics", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [
        {
          document_id: "doc-1",
          page_number: 1,
          text_source: "ocr",
          text_preview: "OCR text preview",
          character_count: 1600,
          chunk_count: 3,
          token_estimate: 260,
          ocr_engine: "tesseract",
          ocr_confidence: 88.5,
          ocr_duration_ms: 45,
        },
      ],
    });
    vi.stubGlobal("fetch", fetchMock);

    const pages = await getDocumentPages("doc-1");

    expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/documents/doc-1/pages", { cache: "no-store" });
    expect(pages[0]).toMatchObject({ page_number: 1, text_source: "ocr", chunk_count: 3 });
    expect(pages[0].ocr_confidence).toBe(88.5);
  });

  it("fetches document chunks for evidence review", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [
        {
          id: "chunk-1",
          document_id: "doc-1",
          page_number: 2,
          chunk_index: 0,
          text: "The document states the total due.",
          token_estimate: 8,
        },
      ],
    });
    vi.stubGlobal("fetch", fetchMock);

    const chunks = await getDocumentChunks("doc-1");

    expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/documents/doc-1/chunks", { cache: "no-store" });
    expect(chunks[0]).toMatchObject({ id: "chunk-1", page_number: 2, token_estimate: 8 });
  });

  it("deletes a document without attempting to parse the empty response", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", fetchMock);

    await expect(deleteDocument("doc-1")).resolves.toBeUndefined();

    expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/documents/doc-1", { method: "DELETE" });
  });

  it("reindexes a document and returns its updated state", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: "doc-1", filename: "sample.pdf", mime_type: "application/pdf", status: "indexed" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const document = await reindexDocument("doc-1");

    expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/documents/doc-1/reindex", { method: "POST" });
    expect(document.status).toBe("indexed");
  });

  it("posts search requests", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        query: "invoice",
        document_type: "invoice",
        query_intent: "amounts",
        hits: [],
        answer: null,
        quality: {
          status: "insufficient_evidence",
          confidence: "weak",
          reason: "No indexed evidence was retrieved for this question.",
          evidence_count: 0,
          best_score: 0,
          best_source_score: 0,
          best_keyword_overlap: 0,
          best_section_intent: 0,
          suggested_questions: [],
        },
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await searchDocuments("invoice", 5);

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/search",
      expect.objectContaining({ method: "POST" }),
    );
    expect(result.query).toBe("invoice");
    expect(result.document_type).toBe("invoice");
    expect(result.query_intent).toBe("amounts");
    expect(result.quality.status).toBe("insufficient_evidence");
  });

  it("posts search requests scoped to a selected document", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        query: "invoice",
        hits: [],
        answer: null,
        quality: {
          status: "insufficient_evidence",
          confidence: "weak",
          reason: "No indexed evidence was retrieved for this question.",
          evidence_count: 0,
          best_score: 0,
          best_source_score: 0,
          best_keyword_overlap: 0,
          best_section_intent: 0,
          suggested_questions: [],
        },
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await searchDocuments("invoice", 5, "doc-1");

    expect(JSON.parse(String(fetchMock.mock.calls[0][1]?.body))).toEqual({
      query: "invoice",
      top_k: 5,
      document_id: "doc-1",
    });
  });

  it("fetches the golden document QA evaluation", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        name: "universal-document-qa-golden",
        summary: {
          total_cases: 13,
          passed_cases: 13,
          failed_cases: 0,
          pass_rate: 1,
          answerable_cases: 12,
          abstention_cases: 1,
          document_types: { research_paper: 5 },
          quality_dimensions: { answer_quality: 12, abstention_safety: 1, parse_quality: 1 },
        },
        cases: [],
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await getGoldenEval();

    expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/eval/golden", { cache: "no-store" });
    expect(result.summary.pass_rate).toBe(1);
    expect(result.summary.quality_dimensions.answer_quality).toBe(12);
    expect(result.summary.quality_dimensions.abstention_safety).toBe(1);
  });

  it("surfaces JSON detail from failed backend responses", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 413,
        text: async () => JSON.stringify({ detail: "File is larger than 20 MB." }),
      }),
    );

    await expect(getDocuments()).rejects.toEqual(new Error("File is larger than 20 MB."));
  });

  it("falls back to plain text for non-JSON backend errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 502,
        text: async () => "Backend unavailable",
      }),
    );

    await expect(getDocuments()).rejects.toEqual(new Error("Backend unavailable"));
  });
});
