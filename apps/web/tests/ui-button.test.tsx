import { render, screen } from "@testing-library/react";
import { Search } from "lucide-react";
import { describe, expect, it } from "vitest";

import { Button } from "@/components/ui/button";

describe("Button", () => {
  it("shows loading state and keeps the accessible name", () => {
    render(<Button isLoading>Search</Button>);

    expect(screen.getByRole("button", { name: /Search/ })).toBeDisabled();
    expect(screen.getByText("Search")).toBeInTheDocument();
  });

  it("supports icon buttons with interactive states", () => {
    render(<Button leftIcon={<Search aria-hidden="true" />}>Ask documents</Button>);

    expect(screen.getByRole("button", { name: "Ask documents" })).toHaveClass("transition");
    expect(screen.getByRole("button", { name: "Ask documents" })).toHaveClass("active:translate-y-px");
  });
});
