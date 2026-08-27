import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { EvaluationSummary } from "@/components/evaluation-summary";

describe("EvaluationSummary", () => {
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
            metrics: { hit_rate_at_5: 1, mean_reciprocal_rank: 0.333 },
            created_at: "2026-08-27T00:00:00Z",
          },
        ]}
      />,
    );

    expect(screen.getByText("sample-retrieval-eval")).toBeInTheDocument();
    expect(screen.getByText("hit rate at 5")).toBeInTheDocument();
    expect(screen.getByText("1.00")).toBeInTheDocument();
    expect(screen.getByText("mean reciprocal rank")).toBeInTheDocument();
    expect(screen.getByText("0.33")).toBeInTheDocument();
  });
});
