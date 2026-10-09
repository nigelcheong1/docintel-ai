import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { EvaluationMetric } from "@/components/evaluation-metric";

describe("EvaluationMetric", () => {
  it("does not turn an untested subset into a perfect score", () => {
    render(<EvaluationMetric label="Table cases" measurement={{value:null,numerator:0,denominator:0,unit:"ratio",scope:"Reviewed table cases"}} />);
    expect(screen.getByText("Not evaluated")).toBeInTheDocument();
    expect(screen.queryByText("100%")).not.toBeInTheDocument();
  });
  it("shows the denominator and scope", () => {
    render(<EvaluationMetric label="Anchor recall" measurement={{value:0.5,numerator:1,denominator:2,unit:"ratio",scope:"Required reviewed anchors"}} />);
    expect(screen.getByText("50%")).toBeInTheDocument();
    expect(screen.getByText("1 / 2")).toBeInTheDocument();
    expect(screen.getByText("Required reviewed anchors")).toBeInTheDocument();
  });
  it("preserves fractional numerators of case-average metrics", () => {
    render(<EvaluationMetric label="Fixture recall" measurement={{value:0.75,numerator:1.5,denominator:2,unit:"ratio",scope:"Case averages"}} />);
    expect(screen.getByText("1.5 / 2")).toBeInTheDocument();
  });
});
