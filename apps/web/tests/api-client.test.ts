import { afterEach, describe, expect, it, vi } from "vitest";

import { deleteDocument, getDocument, getDocuments, reindexDocument, searchDocuments } from "@/lib/api";

describe("api client", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("fetches documents from the configured backend", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [{ id: "doc-1", filename: "sample.pdf", mime_type: "application/pdf", status: "indexed" }],
    });
    vi.stubGlobal("fetch", fetchMock);

    const documents = await getDocuments();

    expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/documents", { cache: "no-store" });
    expect(documents[0].filename).toBe("sample.pdf");
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
      json: async () => ({ query: "invoice", hits: [] }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await searchDocuments("invoice", 5);

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/search",
      expect.objectContaining({ method: "POST" }),
    );
    expect(result.query).toBe("invoice");
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
