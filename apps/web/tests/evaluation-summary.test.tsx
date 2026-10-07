import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { EvaluationSummary } from "@/components/evaluation-summary";

describe("EvaluationSummary", () => {
  it("renders measured verified metrics from the fixture benchmark", () => {
    render(<EvaluationSummary runs={[]} golden={{
      name: "universal-document-qa-golden",
      summary: {
        total_cases: 1, passed_cases: 1, failed_cases: 0, pass_rate: 1,
        answerable_cases: 1, abstention_cases: 0, document_types: {}, quality_dimensions: {},
        verified_metrics: { retrieval_recall_at_5: 0.75, hallucination_risk: 0.1, verifier_pass_rate: 0.9 },
      }, cases: [],
    }} />);

    expect(screen.getByRole("heading", { name: "Verified Answers benchmark" })).toBeInTheDocument();
    expect(screen.getByText("Retrieval recall at 5")).toBeInTheDocument();
    expect(screen.getByText("75%")).toBeInTheDocument();
    expect(screen.getByText("10%")).toBeInTheDocument();
  });
  it("renders an empty state when no runs are recorded", () => {
    render(<EvaluationSummary runs={[]} />);

    expect(screen.getByText("No evaluation runs recorded.")).toBeInTheDocument();
  });

  it("renders metric labels and rounded values for evaluation runs", () => {
    render(
      <EvaluationSummary
        runs={[
          {
            id: "eval-1",
            name: "sample-retrieval-eval",
            model_name: "BAAI/bge-small-en-v1.5",
            metrics: { evaluated_questions: 2, hit_rate_at_5: 1, mean_reciprocal_rank: 0.333 },
            created_at: "2026-08-27T00:00:00Z",
          },
        ]}
      />,
    );

    expect(screen.getByText("sample-retrieval-eval")).toBeInTheDocument();
    expect(screen.getByText("evaluated questions")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("hit rate at 5")).toBeInTheDocument();
    expect(screen.getByText("1.00")).toBeInTheDocument();
    expect(screen.getByText("mean reciprocal rank")).toBeInTheDocument();
    expect(screen.getByText("0.33")).toBeInTheDocument();
  });

  it("renders golden QA quality coverage dimensions", () => {
    render(
      <EvaluationSummary
        runs={[]}
        golden={{
          name: "universal-document-qa-golden",
          summary: {
            total_cases: 14,
            passed_cases: 14,
            failed_cases: 0,
            pass_rate: 1,
            answerable_cases: 12,
            abstention_cases: 3,
            document_types: { research_paper: 5, parse_quality: 1, ocr_readiness: 2 },
            quality_dimensions: {
              answer_quality: 12,
              abstention_safety: 1,
              citation_accuracy: 1,
              hallucination_risk: 1,
              multi_hop_qa: 1,
              parse_quality: 1,
              ocr_readiness: 2,
              table_qa: 1,
              verified_answers: 1,
            },
          },
          cases: [],
        }}
      />,
    );

    expect(screen.getByText("Quality coverage")).toBeInTheDocument();
    expect(screen.getByText("Abstention safety")).toBeInTheDocument();
    expect(screen.getByText("Citation accuracy")).toBeInTheDocument();
    expect(screen.getByText("Hallucination risk")).toBeInTheDocument();
    expect(screen.getByText("Multi-hop QA")).toBeInTheDocument();
    expect(screen.getByText("OCR readiness")).toBeInTheDocument();
    expect(screen.getByText("Table QA")).toBeInTheDocument();
    expect(screen.getByText("Verified Answers")).toBeInTheDocument();
    expect(screen.getByText("All passing")).toBeInTheDocument();
  });
});
