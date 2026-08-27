import { describe, expect, it, vi } from "vitest";

import { getDocuments, searchDocuments } from "@/lib/api";

describe("api client", () => {
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
});
