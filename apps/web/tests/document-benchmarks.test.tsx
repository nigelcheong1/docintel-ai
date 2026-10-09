import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { DocumentBenchmarks } from "@/components/document-benchmarks";
import * as api from "@/lib/document-evaluation";
import { benchmarkDocument, benchmarkSuite } from "./document-evaluation-fixtures";

vi.mock("@/lib/document-evaluation", () => ({ listDocumentSuites: vi.fn(), createDocumentSuite: vi.fn(), getDocumentSuite: vi.fn(), updateDocumentSuite: vi.fn(), deleteDocumentSuite: vi.fn(), deleteDocumentCase: vi.fn() }));
vi.mock("@/lib/api", () => ({ getDocuments: vi.fn(async () => [benchmarkDocument]) }));
describe("DocumentBenchmarks", () => {
  beforeEach(() => {
    vi.clearAllMocks(); localStorage.clear();
    vi.mocked(api.listDocumentSuites).mockResolvedValue([benchmarkSuite]);
    vi.mocked(api.getDocumentSuite).mockResolvedValue(benchmarkSuite);
    vi.mocked(api.createDocumentSuite).mockResolvedValue(benchmarkSuite);
  });
  it("creates a suite from the empty state without fabricated cases", async () => {
    vi.mocked(api.listDocumentSuites).mockResolvedValue([]);
    render(<DocumentBenchmarks />);
    expect(await screen.findByText("No benchmark suites yet.")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Suite name"), { target: { value: "Research checks" } });
    fireEvent.click(screen.getByRole("button", { name: "Create suite" }));
    await waitFor(() => expect(api.createDocumentSuite).toHaveBeenCalledWith("Research checks"));
    expect(await screen.findByText("How many records were retained?")).toBeInTheDocument();
  });
  it("shows case readiness and disables run for draft-only suites", async () => {
    render(<DocumentBenchmarks />);
    expect(await screen.findByText("Draft")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Run benchmark" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Delete suite" }));
    expect(api.deleteDocumentSuite).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Confirm delete suite" }));
    await waitFor(() => expect(api.deleteDocumentSuite).toHaveBeenCalledWith("suite-1"));
  });
  it("surfaces loading failures with a retry action", async () => {
    vi.mocked(api.listDocumentSuites).mockRejectedValue(new Error("Backend unavailable"));
    render(<DocumentBenchmarks />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Backend unavailable");
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });
});
