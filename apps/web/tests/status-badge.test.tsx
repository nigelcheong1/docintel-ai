import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StatusBadge } from "@/components/status-badge";

describe("StatusBadge", () => {
  it("renders indexed status text", () => {
    render(<StatusBadge status="indexed" />);

    expect(screen.getByText("Indexed")).toHaveClass("bg-emerald-50");
  });

  it("renders deferred OCR status text", () => {
    render(<StatusBadge status="deferred_ocr" />);

    expect(screen.getByText("OCR deferred")).toHaveClass("bg-amber-50");
  });

  it("renders OCR processing status text", () => {
    render(<StatusBadge status="ocr_processing" />);

    expect(screen.getByText("OCR running")).toHaveClass("bg-teal-50");
  });
});
