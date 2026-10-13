import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { BenchmarkRunResults } from "@/components/benchmark-run-results";
import * as api from "@/lib/document-evaluation";
import type { DocumentEvalRun, DocumentEvalResult } from "@/lib/types";
import { benchmarkResult, benchmarkRun } from "./document-evaluation-fixtures";

vi.mock("@/lib/document-evaluation", () => ({ getDocumentRun: vi.fn(), getDocumentRunResults: vi.fn(), cancelDocumentRun: vi.fn(), assessDocumentResult: vi.fn() }));
const flush = async () => { await act(async () => { await Promise.resolve(); }); };
describe("BenchmarkRunResults", () => {
  beforeEach(() => {
    vi.useFakeTimers(); vi.clearAllMocks();
    vi.mocked(api.getDocumentRun).mockResolvedValue(benchmarkRun);
    vi.mocked(api.getDocumentRunResults).mockResolvedValue([benchmarkResult]);
    vi.mocked(api.cancelDocumentRun).mockResolvedValue({ ...benchmarkRun, cancel_requested: true });
  });
  afterEach(() => vi.useRealTimers());
  it("polls incremental saved results every 2 seconds and stops at completion and unmount", async () => {
    const onRunUpdated = vi.fn();
    const view = render(<BenchmarkRunResults runId="run-1" onRunUpdated={onRunUpdated} />); await flush();
    expect(screen.getByText("1 / 2 cases finished")).toBeInTheDocument();
    expect(onRunUpdated).toHaveBeenLastCalledWith(benchmarkRun);
    vi.mocked(api.getDocumentRun).mockResolvedValue({ ...benchmarkRun, status: "completed", completed_cases: 2, passed_count: 2 });
    await act(async () => vi.advanceTimersByTimeAsync(2000));
    expect(screen.getByText("2 / 2 cases finished")).toBeInTheDocument();
    expect(onRunUpdated).toHaveBeenLastCalledWith(expect.objectContaining({ status: "completed", completed_cases: 2, passed_count: 2 }));
    const calls = vi.mocked(api.getDocumentRun).mock.calls.length;
    await act(async () => vi.advanceTimersByTimeAsync(6000));
    expect(api.getDocumentRun).toHaveBeenCalledTimes(calls);
    view.unmount(); expect(vi.getTimerCount()).toBe(0);
  });
  it("cancels between cases and keeps the already persisted result visible", async () => {
    const onRunUpdated = vi.fn();
    render(<BenchmarkRunResults runId="run-1" onRunUpdated={onRunUpdated} />); await flush();
    vi.mocked(api.getDocumentRun).mockReturnValueOnce(new Promise(() => {}));
    fireEvent.click(screen.getByRole("button", { name: "Cancel run" })); await flush();
    expect(api.cancelDocumentRun).toHaveBeenCalledWith("run-1");
    expect(screen.getByText("Cancellation requested")).toBeInTheDocument();
    expect(onRunUpdated).toHaveBeenLastCalledWith(expect.objectContaining({ id: "run-1", cancel_requested: true }));
    expect(screen.getByText(benchmarkResult.case_snapshot.question)).toBeInTheDocument();
  });
  it("retains results after a polling failure and retries", async () => {
    const onRunUpdated = vi.fn();
    render(<BenchmarkRunResults runId="run-1" onRunUpdated={onRunUpdated} />); await flush();
    vi.mocked(api.getDocumentRun).mockRejectedValueOnce(new Error("Connection lost"));
    await act(async () => vi.advanceTimersByTimeAsync(2000));
    expect(screen.getByRole("alert")).toHaveTextContent("Connection lost");
    expect(screen.getByText(benchmarkResult.case_snapshot.question)).toBeInTheDocument();
    expect(onRunUpdated).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: "Retry run refresh" })); await flush();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(onRunUpdated).toHaveBeenCalledTimes(2);
  });
  it("allows cancelling again when cancellation fails after a same-run polling retry", async () => {
    let rejectCancel!: (reason: Error) => void;
    vi.mocked(api.cancelDocumentRun).mockReturnValueOnce(new Promise((_resolve, reject) => { rejectCancel = reject; }));
    render(<BenchmarkRunResults runId="run-1" />); await flush();
    fireEvent.click(screen.getByRole("button", { name: "Cancel run" }));
    vi.mocked(api.getDocumentRun).mockRejectedValueOnce(new Error("Connection lost"));
    await act(async () => vi.advanceTimersByTimeAsync(2000));
    fireEvent.click(screen.getByRole("button", { name: "Retry run refresh" })); await flush();
    await act(async () => { rejectCancel(new Error("Cancellation failed")); });
    expect(screen.getByRole("alert")).toHaveTextContent("Cancellation failed");
    expect(screen.getByRole("button", { name: "Cancel run" })).toBeEnabled();
  });
  it.each(["navigation", "unmount"])("ignores late polling results after %s", async (destination) => {
    let resolveResults!: (items: DocumentEvalResult[]) => void;
    vi.mocked(api.getDocumentRunResults).mockReturnValueOnce(new Promise((resolve) => { resolveResults = resolve; }));
    const onRunUpdated = vi.fn();
    const view = render(<BenchmarkRunResults runId="run-1" onRunUpdated={onRunUpdated} />); await flush();
    const nextRun = { ...benchmarkRun, id: "run-2", status: "completed" as const, completed_cases: 2 };
    if (destination === "navigation") {
      vi.mocked(api.getDocumentRun).mockResolvedValue(nextRun);
      view.rerender(<BenchmarkRunResults runId="run-2" onRunUpdated={onRunUpdated} />); await flush();
      expect(screen.getByText("2 / 2 cases finished")).toBeInTheDocument();
    } else view.unmount();
    onRunUpdated.mockClear();
    await act(async () => { resolveResults([benchmarkResult]); });
    expect(onRunUpdated).not.toHaveBeenCalled();
    expect(vi.getTimerCount()).toBe(0);
  });
  it.each([
    ["navigation", "success"], ["navigation", "failure"], ["unmount", "success"], ["unmount", "failure"],
  ])("ignores late cancellation %s/%s", async (destination, outcome) => {
    let resolveCancel!: (item: DocumentEvalRun) => void;
    let rejectCancel!: (reason: Error) => void;
    vi.mocked(api.cancelDocumentRun).mockReturnValueOnce(new Promise((resolve, reject) => { resolveCancel = resolve; rejectCancel = reject; }));
    const onRunUpdated = vi.fn();
    const view = render(<BenchmarkRunResults runId="run-1" onRunUpdated={onRunUpdated} />); await flush();
    fireEvent.click(screen.getByRole("button", { name: "Cancel run" }));
    const nextRun = { ...benchmarkRun, id: "run-2", status: "completed" as const, completed_cases: 2 };
    if (destination === "navigation") {
      vi.mocked(api.getDocumentRun).mockResolvedValue(nextRun);
      view.rerender(<BenchmarkRunResults runId="run-2" onRunUpdated={onRunUpdated} />); await flush();
    } else view.unmount();
    onRunUpdated.mockClear();
    const calls = vi.mocked(api.getDocumentRun).mock.calls.length;
    await act(async () => {
      if (outcome === "success") resolveCancel({ ...benchmarkRun, status: "cancelled", cancel_requested: true });
      else rejectCancel(new Error("Old cancellation failed"));
    });
    expect(onRunUpdated).not.toHaveBeenCalled();
    expect(api.getDocumentRun).toHaveBeenCalledTimes(calls);
    expect(vi.getTimerCount()).toBe(0);
    if (destination === "navigation") {
      expect(screen.getByText("2 / 2 cases finished")).toBeInTheDocument();
      expect(screen.queryByRole("alert")).not.toBeInTheDocument();
      expect(screen.queryByText("Cancellation requested")).not.toBeInTheDocument();
    }
  });
  it("restores persisted progress on remount and clears active polling on unmount", async () => {
    const view = render(<BenchmarkRunResults runId="run-1" />); await flush();
    view.unmount(); expect(vi.getTimerCount()).toBe(0);
    render(<BenchmarkRunResults runId="run-1" />); await flush();
    expect(screen.getByText("1 / 2 cases finished")).toBeInTheDocument();
  });
  it("shows honest scope, fallback, null subset metrics and historical expectations", async () => {
    render(<BenchmarkRunResults runId="run-1" />); await flush();
    expect(screen.queryByText("All passing")).not.toBeInTheDocument();
    expect(screen.getAllByText(/Lexical/).length).toBeGreaterThan(0);
    expect(screen.getByText("Embedding provider unavailable")).toBeInTheDocument();
    expect(screen.getByText("Not evaluated")).toBeInTheDocument();
    expect(screen.getByText(/Reviewed version 1/)).toBeInTheDocument();
    expect(screen.getByText("2,092")).toBeInTheDocument();
    expect(screen.getByText("Candidates before evidence selection")).toBeInTheDocument();
    expect(screen.getByText("Selected evidence pack")).toBeInTheDocument();
  });
  it("filters errors, unavailable sources and pending human review independently", async () => {
    vi.mocked(api.getDocumentRunResults).mockResolvedValue([
      benchmarkResult,
      { ...benchmarkResult, id: "error-1", status: "error", case_snapshot: { ...benchmarkResult.case_snapshot, question: "Timeout case" }, failure_reasons: ["Request timed out"] },
      { ...benchmarkResult, id: "unavailable-1", status: "unavailable", case_snapshot: { ...benchmarkResult.case_snapshot, question: "Missing file case" }, failure_reasons: ["Source file missing"] },
    ]);
    render(<BenchmarkRunResults runId="run-1" />); await flush();
    fireEvent.click(screen.getByRole("button", { name: "Errors" }));
    expect(screen.getByText("Timeout case")).toBeInTheDocument(); expect(screen.queryByText("Missing file case")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Unavailable" }));
    expect(screen.getByText("Missing file case")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Needs human review" }));
    expect(screen.getByText("Timeout case")).toBeInTheDocument();
  });
  it("saves a separate human assessment without changing automatic pass", async () => {
    vi.mocked(api.assessDocumentResult).mockResolvedValue({ ...benchmarkResult, human_assessment: "incorrect", assessment_note: "Ambiguous source" });
    render(<BenchmarkRunResults runId="run-1" />); await flush();
    fireEvent.change(screen.getByLabelText("Human assessment"), { target: { value: "incorrect" } });
    fireEvent.change(screen.getByLabelText("Assessment note"), { target: { value: "Ambiguous source" } });
    fireEvent.click(screen.getByRole("button", { name: "Save assessment" })); await flush();
    expect(api.assessDocumentResult).toHaveBeenCalledWith("run-1", "result-1", "incorrect", "Ambiguous source");
    expect(screen.getByText("Automatic checks passed")).toBeInTheDocument();
    expect(screen.getByLabelText("Human assessment")).toHaveValue("incorrect");
  });
});
