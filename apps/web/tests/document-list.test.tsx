import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

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

  it("omits document action controls when action handlers are unavailable", () => {
    render(
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

    expect(screen.queryByRole("button", { name: "Reindex quarterly-report.pdf" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Delete quarterly-report.pdf" })).not.toBeInTheDocument();
  });

  it("shows document metadata and action controls in both layouts", () => {
    const onDelete = vi.fn().mockResolvedValue(undefined);
    const onReindex = vi.fn().mockResolvedValue(undefined);

    const { container } = render(
      <DocumentList
        documents={[
          {
            id: "doc-1",
            filename: "quarterly-report.pdf",
            mime_type: "application/pdf",
            status: "indexed",
            page_count: 12,
            chunk_count: 48,
            updated_at: "2026-08-28T03:30:00Z",
          },
        ]}
        onDelete={onDelete}
        onReindex={onReindex}
      />,
    );

    const mobileList = container.querySelector<HTMLDivElement>(".md\\:hidden");
    const desktopTable = container.querySelector<HTMLDivElement>(".hidden.md\\:block");

    if (!mobileList || !desktopTable) {
      throw new Error("Expected responsive document layouts.");
    }

    for (const layout of [mobileList, desktopTable]) {
      expect(within(layout).getByText("12")).toBeInTheDocument();
      expect(within(layout).getByText("48")).toBeInTheDocument();
      expect(within(layout).getByText("Aug 28, 2026", { exact: false })).toBeInTheDocument();
      expect(within(layout).getByRole("button", { name: "Reindex quarterly-report.pdf" })).toBeInTheDocument();
      expect(within(layout).getByRole("button", { name: "Delete quarterly-report.pdf" })).toBeInTheDocument();
    }
  });

  it("locks document actions while a reindex operation is pending", () => {
    let resolveReindex: (() => void) | undefined;
    const onReindex = vi.fn(
      () => new Promise<void>((resolve) => {
        resolveReindex = resolve;
      }),
    );

    render(
      <DocumentList
        documents={[
          {
            id: "doc-1",
            filename: "quarterly-report.pdf",
            mime_type: "application/pdf",
            status: "indexed",
            page_count: 12,
            chunk_count: 48,
          },
        ]}
        onDelete={vi.fn().mockResolvedValue(undefined)}
        onReindex={onReindex}
      />,
    );

    const reindexButton = screen.getAllByRole("button", { name: "Reindex quarterly-report.pdf" })[0];
    const deleteButton = screen.getAllByRole("button", { name: "Delete quarterly-report.pdf" })[0];
    fireEvent.click(reindexButton);

    expect(onReindex).toHaveBeenCalledWith("doc-1");
    expect(reindexButton).toBeDisabled();
    expect(deleteButton).toBeDisabled();
    expect(reindexButton).toHaveTextContent("Reindexing...");

    resolveReindex?.();
  });
});
