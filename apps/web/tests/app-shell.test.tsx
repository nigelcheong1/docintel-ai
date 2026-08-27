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
});
