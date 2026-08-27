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

    expect((await screen.findAllByText("invoice.pdf")).length).toBeGreaterThan(0);
    expect(within(screen.getByTestId("document-count")).getByText("2")).toBeInTheDocument();
    expect(within(screen.getByTestId("evaluation-count")).getByText("1")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Upload documents/ })).toHaveAttribute("href", "/documents");
    expect(screen.getByRole("link", { name: /Search evidence/ })).toHaveAttribute("href", "/search");
  });
});
