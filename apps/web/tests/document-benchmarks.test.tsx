import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { DocumentBenchmarks } from "@/components/document-benchmarks";
import * as api from "@/lib/document-evaluation";
import { benchmarkDocument, benchmarkSuite, benchmarkRun } from "./document-evaluation-fixtures";

vi.mock("@/lib/document-evaluation", () => ({ listDocumentSuites: vi.fn(), createDocumentSuite: vi.fn(), getDocumentSuite: vi.fn(), updateDocumentSuite: vi.fn(), deleteDocumentSuite: vi.fn(), deleteDocumentCase: vi.fn(), listDocumentRuns: vi.fn(), createDocumentRun: vi.fn() }));
vi.mock("@/components/benchmark-run-results", () => ({ BenchmarkRunResults: ({ runId }: { runId: string }) => <p>Saved results {runId}</p> }));
vi.mock("@/lib/api", () => ({ getDocuments: vi.fn(async () => [benchmarkDocument]) }));
describe("DocumentBenchmarks", () => {
  beforeEach(() => {
    vi.clearAllMocks(); localStorage.clear();
    vi.mocked(api.listDocumentSuites).mockResolvedValue([benchmarkSuite]);
    vi.mocked(api.getDocumentSuite).mockResolvedValue(benchmarkSuite);
    vi.mocked(api.createDocumentSuite).mockResolvedValue(benchmarkSuite);
    vi.mocked(api.listDocumentRuns).mockResolvedValue([]);
    vi.mocked(api.createDocumentRun).mockResolvedValue(benchmarkRun);
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
  it("waits for reviewed cases before starting and restores the selected persisted run on return", async () => {
    const reviewedSuite = { ...benchmarkSuite, reviewed_count: 1, cases: benchmarkSuite.cases.map((item) => ({ ...item, review_state: "reviewed" as const, availability: "ready" as const })) };
    let resolveSuite!: (value: typeof reviewedSuite) => void;
    vi.mocked(api.getDocumentSuite).mockReturnValueOnce(new Promise((resolve) => { resolveSuite = resolve; }));
    const view = render(<DocumentBenchmarks />);
    const runButton = await screen.findByRole("button", { name: "Run benchmark" });
    expect(runButton).toBeDisabled();
    fireEvent.click(runButton);
    expect(api.createDocumentRun).not.toHaveBeenCalled();
    await act(async () => { resolveSuite(reviewedSuite); });
    await waitFor(() => expect(runButton).toBeEnabled());
    fireEvent.click(runButton);
    await waitFor(() => expect(api.createDocumentRun).toHaveBeenCalledWith("suite-1"));
    expect(await screen.findByText("Saved results run-1")).toBeInTheDocument();
    view.unmount();
    vi.mocked(api.listDocumentRuns).mockResolvedValue([benchmarkRun]);
    render(<DocumentBenchmarks />);
    expect(await screen.findByText("Saved results run-1")).toBeInTheDocument();
  });
  it("surfaces an actionable globally-busy error without a false new run", async () => {
    vi.mocked(api.getDocumentSuite).mockResolvedValue({ ...benchmarkSuite, cases: benchmarkSuite.cases.map((item) => ({ ...item, review_state: "reviewed", availability: "ready" })) });
    vi.mocked(api.createDocumentRun).mockRejectedValue(new Error("A benchmark is already active. Wait or cancel it."));
    render(<DocumentBenchmarks />);
    await screen.findByText("Reviewed");
    fireEvent.click(screen.getByRole("button", { name: "Run benchmark" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Wait or cancel it.");
    expect(screen.queryByText("Saved results run-1")).not.toBeInTheDocument();
  });
});
