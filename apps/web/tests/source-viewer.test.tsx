import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SourceViewer } from "@/components/source-viewer";

describe("SourceViewer", () => {
  it("renders API page images through the backend and portals above the app shell", () => {
    const { container } = render(
      <div data-testid="app-content">
        <SourceViewer
          source={{
            chunk_id: "chunk-1",
            document_id: "doc-1",
            document_filename: "DRL Final Report.pdf",
            page_number: 1,
            page_image_url: "/documents/doc-1/pages/1/image",
            snippet: "The project uses PPO training in Unity ML-Agents.",
          }}
          onClose={() => undefined}
        />
      </div>,
    );

    const dialog = screen.getByRole("dialog", { name: "Source viewer" });
    const image = screen.getByRole("img", { name: "Page 1 source preview for DRL Final Report.pdf" });

    expect(image).toHaveAttribute("src", "http://localhost:8000/documents/doc-1/pages/1/image");
    expect(container).not.toContainElement(dialog);
    expect(document.body).toContainElement(dialog);
  });
});
