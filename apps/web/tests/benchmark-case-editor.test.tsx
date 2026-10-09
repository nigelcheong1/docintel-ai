import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { BenchmarkCaseEditor } from "@/components/benchmark-case-editor";
import * as api from "@/lib/document-evaluation";
import { benchmarkCase, benchmarkDocument } from "./document-evaluation-fixtures";

vi.mock("@/lib/document-evaluation", () => ({ saveDocumentCase: vi.fn(), reviewDocumentCase: vi.fn() }));
vi.mock("@/lib/api", () => ({
  getDocumentPages: vi.fn(async () => [{ page_number: 3, image_url: "/documents/doc-1/pages/3/image" }]),
  getDocumentChunks: vi.fn(async () => [{ id: "chunk-3", page_number: 3, text: "2092 works retained." }]),
}));

describe("BenchmarkCaseEditor", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.saveDocumentCase).mockResolvedValue(benchmarkCase);
    vi.mocked(api.reviewDocumentCase).mockResolvedValue({ ...benchmarkCase, review_state: "reviewed", availability: "ready" });
  });
  const setup = (initialCase = benchmarkCase) => render(<BenchmarkCaseEditor suiteId="suite-1" documents={[benchmarkDocument]} initialCase={initialCase} onSaved={vi.fn()} onCancel={vi.fn()} />);
  it("saves a draft without approving it and requires source preview before explicit review", async () => {
    setup();
    expect(screen.getByRole("combobox", { name: "Document" })).toHaveValue("doc-1");
    expect(screen.getByRole("button", { name: "Mark reviewed" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Save draft" }));
    await waitFor(() => expect(api.saveDocumentCase).toHaveBeenCalled());
    expect(api.reviewDocumentCase).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Preview anchor 1" }));
    expect(await screen.findByRole("dialog", { name: "Source viewer" })).toBeInTheDocument();
    expect(screen.getByRole("img")).toHaveAttribute("src", "http://localhost:8000/documents/doc-1/pages/3/image");
    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    fireEvent.click(screen.getByRole("button", { name: "Mark reviewed" }));
    await waitFor(() => expect(api.reviewDocumentCase).toHaveBeenCalledWith("suite-1", "case-1", 1));
    expect(await screen.findByText("Reviewed")).toBeInTheDocument();
  });
  it("edits facts, alternatives, anchors, tags and rationale; changed reviewed cases need saving again", async () => {
    setup({ ...benchmarkCase, review_state: "reviewed", availability: "ready" });
    fireEvent.change(screen.getByLabelText("Expected fact 1"), { target: { value: "2366" } });
    fireEvent.change(screen.getByLabelText("Alternatives 1"), { target: { value: "2,366\ntwo thousand three hundred sixty-six" } });
    fireEvent.change(screen.getByLabelText("Quote 1"), { target: { value: "2366 records." } });
    fireEvent.change(screen.getByLabelText("Tags"), { target: { value: "table, multi-part" } });
    fireEvent.change(screen.getByLabelText("Review rationale"), { target: { value: "Checked both sources." } });
    expect(screen.getByRole("button", { name: "Mark reviewed" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Save draft" }));
    await waitFor(() => expect(api.saveDocumentCase).toHaveBeenCalledWith("suite-1", expect.objectContaining({
      facts: [{ pattern: "2366", alternatives: ["2,366", "two thousand three hundred sixty-six"] }],
      anchors: [{ page_number: 3, quote: "2366 records." }], tags: ["table", "multi-part"], review_rationale: "Checked both sources.",
    }), "case-1"));
  });
  it("requires a negative rationale and explicit whole-document scope review", async () => {
    setup({ ...benchmarkCase, expected_outcome: "insufficient_evidence", facts: [], anchors: [], review_rationale: "", availability: "stale" });
    expect(screen.getByText("Stale")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Mark reviewed" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Open document scope" }));
    expect(await screen.findByRole("dialog", { name: "Source viewer" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    fireEvent.click(screen.getByLabelText("I reviewed the whole document scope"));
    expect(screen.getByRole("button", { name: "Mark reviewed" })).toBeDisabled();
  });
  it("shows server validation failure instead of a false review success", async () => {
    vi.mocked(api.saveDocumentCase).mockRejectedValue(new Error("Document is not indexed."));
    setup();
    fireEvent.click(screen.getByRole("button", { name: "Save draft" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Document is not indexed.");
  });
  it("updates rather than duplicates a newly saved case after further edits", async () => {
    render(<BenchmarkCaseEditor suiteId="suite-1" documents={[benchmarkDocument]} onSaved={vi.fn()} onCancel={vi.fn()} />);
    fireEvent.change(screen.getByLabelText("Question"), { target: { value: "How many records?" } });
    fireEvent.click(screen.getByRole("button", { name: "Save draft" }));
    await screen.findByText("Draft");
    fireEvent.change(screen.getByLabelText("Question"), { target: { value: "How many retained records?" } });
    fireEvent.click(screen.getByRole("button", { name: "Save draft" }));
    await waitFor(() => expect(api.saveDocumentCase).toHaveBeenLastCalledWith("suite-1", expect.objectContaining({ question: "How many retained records?" }), "case-1"));
  });
  it("keeps delimiters while typing tags and removes blank alternatives from the saved payload", async () => {
    setup();
    fireEvent.change(screen.getByLabelText("Tags"), { target: { value: "table," } });
    expect(screen.getByLabelText("Tags")).toHaveValue("table,");
    fireEvent.change(screen.getByLabelText("Alternatives 1"), { target: { value: "2,092\n" } });
    fireEvent.click(screen.getByRole("button", { name: "Save draft" }));
    await waitFor(() => expect(api.saveDocumentCase).toHaveBeenLastCalledWith("suite-1", expect.objectContaining({ facts: [{ pattern: "2092", alternatives: ["2,092"] }], tags: ["table"] }), "case-1"));
  });
});
