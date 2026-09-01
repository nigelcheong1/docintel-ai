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

const goldenEvaluation = {
  name: "universal-document-qa-golden",
  summary: {
    total_cases: 13,
    passed_cases: 13,
    failed_cases: 0,
    pass_rate: 1,
    answerable_cases: 12,
    abstention_cases: 1,
    document_types: {
      contract: 2,
      invoice: 2,
      report: 2,
      research_paper: 5,
      resume: 2,
    },
    quality_dimensions: {
      answer_quality: 12,
      abstention_safety: 1,
      parse_quality: 1,
    },
  },
  cases: [
    {
      case_id: "research-methods",
      document_name: "h2r-paper.pdf",
      document_type: "research_paper",
      question: "What methods are used?",
      expected_status: "answerable",
      actual_status: "answerable",
      expected_terms: ["vision-language", "encoder"],
      query_intent: "methods",
      confidence: "strong",
      citation_count: 2,
      answer_preview: "Joint vision-language encoder architecture uses a visual encoder.",
      quality_reason: "Document-aware methods answer built from matching sections.",
      passed: true,
      failure_reasons: [],
    },
    {
      case_id: "research-hard-negative-total-due",
      document_name: "h2r-paper.pdf",
      document_type: "research_paper",
      question: "What total amount is due?",
      expected_status: "insufficient_evidence",
      actual_status: "insufficient_evidence",
      expected_terms: [],
      query_intent: "amounts",
      confidence: "weak",
      citation_count: 0,
      answer_preview: null,
      quality_reason: "This document is classified as a research paper, so invoice totals are not expected.",
      passed: true,
      failure_reasons: [],
    },
  ],
};

describe("EvaluationPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("loads existing evaluation runs from the backend", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: true, json: async () => [evaluationRun] })
      .mockResolvedValueOnce({ ok: true, json: async () => goldenEvaluation });
    vi.stubGlobal("fetch", fetchMock);

    render(<EvaluationPage />);

    expect(await screen.findByText("local-retrieval-benchmark")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/eval/runs", { cache: "no-store" });
    expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/eval/golden", { cache: "no-store" });
  });

  it("shows the universal document QA golden evaluation", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: true, json: async () => [] })
      .mockResolvedValueOnce({ ok: true, json: async () => goldenEvaluation });
    vi.stubGlobal("fetch", fetchMock);

    render(<EvaluationPage />);

    expect(await screen.findByRole("heading", { name: "Universal document QA" })).toBeInTheDocument();
    expect(screen.getByText("Quality coverage")).toBeInTheDocument();
    expect(screen.getByText("Abstention safety")).toBeInTheDocument();
    expect(screen.getByText("13 cases")).toBeInTheDocument();
    expect(screen.getByText("100%")).toBeInTheDocument();
    expect(screen.getByText("Research paper 5")).toBeInTheDocument();
    expect(screen.getByText("research-methods")).toBeInTheDocument();
    expect(screen.getByText("What total amount is due?")).toBeInTheDocument();
  });

  it("keeps the golden QA panel visible when retrieval run history fails", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: false, text: async () => "Retrieval history unavailable" })
      .mockResolvedValueOnce({ ok: true, json: async () => goldenEvaluation });
    vi.stubGlobal("fetch", fetchMock);

    render(<EvaluationPage />);

    expect(await screen.findByRole("heading", { name: "Universal document QA" })).toBeInTheDocument();
    expect(screen.getByText("Retrieval history unavailable")).toBeInTheDocument();
  });

  it("keeps retrieval run history visible when golden QA fails", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: true, json: async () => [evaluationRun] })
      .mockResolvedValueOnce({ ok: false, text: async () => "Golden QA unavailable" });
    vi.stubGlobal("fetch", fetchMock);

    render(<EvaluationPage />);

    expect(await screen.findByText("local-retrieval-benchmark")).toBeInTheDocument();
    expect(screen.getByText("Golden QA unavailable")).toBeInTheDocument();
  });

  it("creates a local evaluation run from the page action", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: true, json: async () => [] })
      .mockResolvedValueOnce({ ok: true, json: async () => goldenEvaluation })
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
