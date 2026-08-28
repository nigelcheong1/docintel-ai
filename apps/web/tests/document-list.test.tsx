import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DocumentList } from "@/components/document-list";

describe("DocumentList", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

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

  it("visibly locks actions on every row while one document action is pending", () => {
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
          },
          {
            id: "doc-2",
            filename: "annual-report.pdf",
            mime_type: "application/pdf",
            status: "indexed",
          },
        ]}
        onDelete={vi.fn().mockResolvedValue(undefined)}
        onReindex={onReindex}
      />,
    );

    fireEvent.click(screen.getAllByRole("button", { name: "Reindex quarterly-report.pdf" })[0]);

    for (const button of screen.getAllByRole("button", { name: /^(Reindex|Delete) / })) {
      expect(button).toBeDisabled();
    }

    resolveReindex?.();
  });

  it("shows deleting state only on the pending delete control", () => {
    let resolveDelete: (() => void) | undefined;
    const onDelete = vi.fn(
      () => new Promise<void>((resolve) => {
        resolveDelete = resolve;
      }),
    );
    vi.spyOn(window, "confirm").mockReturnValue(true);

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
        onDelete={onDelete}
        onReindex={vi.fn().mockResolvedValue(undefined)}
      />,
    );

    const deleteButton = screen.getAllByRole("button", { name: "Delete quarterly-report.pdf" })[0];
    const reindexButton = screen.getAllByRole("button", { name: "Reindex quarterly-report.pdf" })[0];
    fireEvent.click(deleteButton);

    expect(deleteButton).toHaveTextContent("Deleting...");
    expect(reindexButton).toHaveTextContent("Reindex");

    resolveDelete?.();
  });

  it("does not offer reindex for image documents", () => {
    render(
      <DocumentList
        documents={[
          {
            id: "doc-image",
            filename: "scan.png",
            mime_type: "image/png",
            status: "deferred_ocr",
          },
        ]}
        onDelete={vi.fn().mockResolvedValue(undefined)}
        onReindex={vi.fn().mockResolvedValue(undefined)}
      />,
    );

    expect(screen.queryByRole("button", { name: "Reindex scan.png" })).not.toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Delete scan.png" })).toHaveLength(2);
  });

  it("requires confirmation before permanently deleting a document", () => {
    const onDelete = vi.fn().mockResolvedValue(undefined);
    vi.spyOn(window, "confirm").mockReturnValue(false);

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
        onDelete={onDelete}
      />,
    );

    fireEvent.click(screen.getAllByRole("button", { name: "Delete quarterly-report.pdf" })[0]);

    expect(window.confirm).toHaveBeenCalledWith("Permanently delete quarterly-report.pdf?");
    expect(onDelete).not.toHaveBeenCalled();
  });

  it("shows a failed action message and lets the user try again", async () => {
    const onReindex = vi.fn().mockRejectedValue(new Error("Reindexing failed."));

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
        onReindex={onReindex}
      />,
    );

    const reindexButton = screen.getAllByRole("button", { name: "Reindex quarterly-report.pdf" })[0];
    fireEvent.click(reindexButton);

    expect(await screen.findByRole("alert")).toHaveTextContent("Reindexing failed.");
    await waitFor(() => expect(reindexButton).toBeEnabled());
  });

  it("renders only the actions that have callbacks", () => {
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
        onDelete={vi.fn().mockResolvedValue(undefined)}
      />,
    );

    expect(screen.getAllByRole("button", { name: "Delete quarterly-report.pdf" })).toHaveLength(2);
    expect(screen.queryByRole("button", { name: "Reindex quarterly-report.pdf" })).not.toBeInTheDocument();
  });
});
