import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StatusBadge } from "@/components/status-badge";

describe("StatusBadge", () => {
  it("renders indexed status text", () => {
    render(<StatusBadge status="indexed" />);

    expect(screen.getByText("Indexed")).toBeInTheDocument();
  });

  it("renders deferred OCR status text", () => {
    render(<StatusBadge status="deferred_ocr" />);

    expect(screen.getByText("OCR deferred")).toBeInTheDocument();
  });
});
