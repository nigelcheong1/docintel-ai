import { render, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DocumentList } from "@/components/document-list";

describe("DocumentList", () => {
  it("provides a stacked document view on small screens", () => {
    const { container } = render(
      <DocumentList
        documents={[
          {
            id: "doc-1",
            filename: "quarterly-report.pdf",
            mime_type: "application/pdf",
            status: "indexed",
          },
        ]}
      />,
    );

    const mobileList = container.querySelector<HTMLDivElement>(".md\\:hidden");

    if (!mobileList) {
      throw new Error("Expected a mobile document list.");
    }

    expect(within(mobileList).getByText("quarterly-report.pdf")).toBeInTheDocument();
    expect(within(mobileList).getByText("Status")).toBeInTheDocument();
    expect(within(mobileList).getByText("Type")).toBeInTheDocument();
  });
});
