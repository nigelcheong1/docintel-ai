import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { BenchmarkCaseEditor } from "@/components/benchmark-case-editor";
import * as sources from "@/lib/api";
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
  it("does not restore a saved version over edits made while the request was pending", async () => {
    let finish!: (value: typeof benchmarkCase) => void;
    vi.mocked(api.saveDocumentCase).mockImplementationOnce(() => new Promise((resolve) => { finish = resolve; }));
    setup();
    fireEvent.click(screen.getByRole("button", { name: "Save draft" }));
    fireEvent.change(screen.getByLabelText("Question"), { target: { value: "A different current question?" } });
    await act(async () => finish(benchmarkCase));
    fireEvent.click(screen.getByRole("button", { name: "Preview anchor 1" }));
    await screen.findByRole("dialog", { name: "Source viewer" });
    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(screen.getByLabelText("Question")).toHaveValue("A different current question?");
    expect(screen.getByRole("button", { name: "Mark reviewed" })).toBeDisabled();
    expect(screen.getByText("Unsaved draft")).toBeInTheDocument();
  });
  it("identifies outcome-specific required fields without requiring optional negative anchors", () => {
    const view = setup();
    expect(screen.getByText("Required for review")).toBeInTheDocument();
    expect(screen.getByLabelText("Expected fact 1")).toBeRequired();
    expect(screen.getByLabelText("Quote 1")).toBeRequired();
    expect(screen.getByLabelText("Review rationale")).not.toBeRequired();
    fireEvent.click(screen.getByRole("radio", { name: "Not enough evidence" }));
    expect(screen.getByLabelText("Review rationale")).toBeRequired();
    expect(screen.getByLabelText("I reviewed the whole document scope")).toBeRequired();
    expect(screen.queryByLabelText("Expected fact 1")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Tags")).not.toBeRequired();
    view.unmount();
  });
  it("shows missing positive prerequisites before a disabled review button can be clicked", () => {
    render(<BenchmarkCaseEditor suiteId="suite-1" documents={[benchmarkDocument]} onSaved={vi.fn()} onCancel={vi.fn()} />);
    const checklist = screen.getByRole("region", { name: "Review prerequisites" });
    expect(checklist).toHaveTextContent("Enter a question.");
    expect(checklist).toHaveTextContent("Add at least one expected fact.");
    expect(checklist).toHaveTextContent("Add at least one evidence anchor.");
    expect(checklist).toHaveTextContent("Save the current draft.");
    expect(screen.getByRole("button", { name: "Mark reviewed" })).toBeDisabled();
  });
  it("rejects whitespace-only questions locally and focuses the missing required field", async () => {
    setup();
    fireEvent.change(screen.getByLabelText("Question"), { target: { value: "   " } });
    fireEvent.submit(screen.getByRole("button", { name: "Save draft" }).closest("form")!);
    expect(api.saveDocumentCase).not.toHaveBeenCalled();
    expect(screen.getByLabelText("Question")).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByLabelText("Question")).toHaveFocus();
    expect(screen.getByRole("alert")).toHaveTextContent("Enter a question.");
  });
  it("allows a valid incomplete draft while keeping missing review requirements visible", async () => {
    vi.mocked(api.saveDocumentCase).mockResolvedValue({ ...benchmarkCase, facts: [], anchors: [] });
    render(<BenchmarkCaseEditor suiteId="suite-1" documents={[benchmarkDocument]} onSaved={vi.fn()} onCancel={vi.fn()} />);
    fireEvent.change(screen.getByLabelText("Question"), { target: { value: benchmarkCase.question } });
    fireEvent.click(screen.getByRole("button", { name: "Save draft" }));
    expect(await screen.findByText("Draft")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Review prerequisites" })).toHaveTextContent("Add at least one expected fact.");
    expect(screen.getByRole("button", { name: "Mark reviewed" })).toBeDisabled();
    expect(api.reviewDocumentCase).not.toHaveBeenCalled();
  });
  it("gates incomplete fact/anchor rows and prevents previewing empty evidence", async () => {
    setup();
    fireEvent.change(screen.getByLabelText("Expected fact 1"), { target: { value: " " } });
    fireEvent.change(screen.getByLabelText("Page 1"), { target: { value: "1.5" } });
    fireEvent.change(screen.getByLabelText("Quote 1"), { target: { value: " " } });
    fireEvent.submit(screen.getByRole("button", { name: "Save draft" }).closest("form")!);
    expect(api.saveDocumentCase).not.toHaveBeenCalled();
    expect(screen.getByLabelText("Expected fact 1")).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByLabelText("Page 1")).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByLabelText("Quote 1")).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByLabelText("Alternatives 1")).not.toBeRequired();
    expect(screen.getByRole("region", { name: "Review prerequisites" })).toHaveTextContent("Enter expected fact 1.");
    expect(screen.getByRole("button", { name: "Preview anchor 1" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Mark reviewed" })).toBeDisabled();
  });
  it("shows a negative rationale error on blur and tracks scope confirmation independently", async () => {
    setup({ ...benchmarkCase, expected_outcome: "insufficient_evidence", facts: [], anchors: [], review_rationale: "" });
    fireEvent.blur(screen.getByLabelText("Review rationale"));
    expect(screen.getByLabelText("Review rationale")).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByRole("alert")).toHaveTextContent("Add a scope-review rationale.");
    expect(screen.getByRole("region", { name: "Review prerequisites" })).toHaveTextContent("Inspect the document scope.");
    fireEvent.click(screen.getByRole("button", { name: "Open document scope" }));
    await screen.findByRole("dialog", { name: "Source viewer" });
    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(screen.getByRole("region", { name: "Review prerequisites" })).toHaveTextContent("Confirm the document scope review.");
    expect(screen.getByRole("button", { name: "Mark reviewed" })).toBeDisabled();
  });
  it("enables review only after every positive requirement is complete, and resets it after edits", async () => {
    setup();
    fireEvent.click(screen.getByRole("button", { name: "Preview anchor 1" }));
    await screen.findByRole("dialog", { name: "Source viewer" });
    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(screen.getByRole("region", { name: "Review prerequisites" })).toHaveTextContent("Ready for review");
    expect(screen.getByRole("button", { name: "Mark reviewed" })).toBeEnabled();
    fireEvent.change(screen.getByLabelText("Question"), { target: { value: "Changed question?" } });
    expect(screen.getByRole("region", { name: "Review prerequisites" })).toHaveTextContent("Save the current draft.");
    expect(screen.getByRole("button", { name: "Mark reviewed" })).toBeDisabled();
  });
  it("shows source preview errors as an unmet prerequisite instead of claiming completion", async () => {
    vi.mocked(sources.getDocumentPages).mockRejectedValueOnce(new Error("Source file missing."));
    setup();
    fireEvent.click(screen.getByRole("button", { name: "Preview anchor 1" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Source file missing.");
    expect(screen.getByRole("region", { name: "Review prerequisites" })).toHaveTextContent("Preview every evidence anchor.");
    expect(screen.getByRole("button", { name: "Mark reviewed" })).toBeDisabled();
  });
});
