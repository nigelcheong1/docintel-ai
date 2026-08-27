import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import EvaluationPage from "@/app/evaluation/page";

const evaluationRun = {
  id: "eval-1",
  name: "local-retrieval-benchmark",
  model_name: "BAAI/bge-small-en-v1.5",
  metrics: { evaluated_questions: 2, hit_rate_at_5: 0.5, mean_reciprocal_rank: 0.25 },
  created_at: "2026-08-27T00:00:00Z",
};

describe("EvaluationPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("loads existing evaluation runs from the backend", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [evaluationRun],
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<EvaluationPage />);

    expect(await screen.findByText("local-retrieval-benchmark")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/eval/runs", { cache: "no-store" });
  });

  it("creates a local evaluation run from the page action", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: true, json: async () => [] })
      .mockResolvedValueOnce({ ok: true, json: async () => evaluationRun });
    vi.stubGlobal("fetch", fetchMock);

    render(<EvaluationPage />);
    const button = await screen.findByRole("button", { name: "Run evaluation" });
    fireEvent.click(button);

    await waitFor(() => expect(screen.getByText("local-retrieval-benchmark")).toBeInTheDocument());
    expect(fetchMock).toHaveBeenLastCalledWith(
      "http://localhost:8000/eval/runs",
      expect.objectContaining({ method: "POST" }),
    );
  });
});
