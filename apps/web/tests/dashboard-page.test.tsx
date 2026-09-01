import { render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import DashboardPage from "@/app/page";

describe("DashboardPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("loads real document and evaluation summaries with workflow links", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => [
          { id: "doc-1", filename: "invoice.pdf", mime_type: "application/pdf", status: "indexed" },
          { id: "doc-2", filename: "scan.png", mime_type: "image/png", status: "deferred_ocr" },
        ],
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => [
          {
            id: "eval-1",
            name: "local-retrieval-benchmark",
            model_name: "BAAI/bge-small-en-v1.5",
            metrics: { evaluated_questions: 1 },
            created_at: "2026-08-27T00:00:00Z",
          },
        ],
      });
    vi.stubGlobal("fetch", fetchMock);

    render(<DashboardPage />);

    expect(await screen.findByText("Workspace intelligence")).toBeInTheDocument();
    expect(screen.getByText("Ready for cited search")).toBeInTheDocument();
    expect((await screen.findAllByText("invoice.pdf")).length).toBeGreaterThan(0);
    expect(within(screen.getByTestId("document-count")).getByText("2")).toBeInTheDocument();
    expect(within(screen.getByTestId("evaluation-count")).getByText("1")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Ask documents/ })).toHaveAttribute("href", "/search");
    expect(screen.getByRole("link", { name: /Upload documents/ })).toHaveAttribute("href", "/documents");
    expect(screen.getByRole("link", { name: /Search evidence/ })).toHaveAttribute("href", "/search");
  });

  it("summarizes parse quality warnings from indexed documents", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce({
          ok: true,
          json: async () => [
            {
              id: "doc-1",
              filename: "scan-heavy.pdf",
              mime_type: "application/pdf",
              status: "indexed",
              parse_quality: {
                page_count: 4,
                text_page_count: 1,
                empty_page_count: 3,
                total_characters: 120,
                average_characters_per_page: 30,
                low_text_page_ratio: 0.75,
                scanned_likelihood: "high",
                warnings: ["This PDF has very little extractable text and may need OCR."],
              },
            },
          ],
        })
        .mockResolvedValueOnce({ ok: true, json: async () => [] }),
    );

    render(<DashboardPage />);

    expect(await within(screen.getByTestId("quality-warning-count")).findByText("1")).toBeInTheDocument();
  });
});
