import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AppShell } from "@/components/app-shell";

describe("AppShell", () => {
  it("provides compact navigation for mobile screens", () => {
    render(<AppShell>Content</AppShell>);

    const navigation = screen.getByRole("navigation", { name: "Mobile navigation" });
    expect(navigation).toHaveClass("md:hidden");
    expect(screen.getAllByRole("link", { name: /Documents/ }).length).toBeGreaterThan(1);
  });

  it("renders the DocIntel AI logo as a home link", () => {
    render(<AppShell>Content</AppShell>);

    expect(screen.getAllByLabelText("DocIntel AI home").length).toBeGreaterThan(0);
    expect(screen.getAllByText("DocIntel").length).toBeGreaterThan(0);
    expect(screen.getAllByText("AI").length).toBeGreaterThan(0);
  });
});
